#Requires -Version 5.1
<#
.SYNOPSIS
    YTCLFR full Windows development environment setup.
    Checks whether each tool/dependency already exists before installing.

.USAGE
    # Open PowerShell as Administrator, then run:
    Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned -Force
    .\setup-ytclfr.ps1

    # Or run with a custom project root:
    .\setup-ytclfr.ps1 -ProjectRoot "C:\projects\ytclfr"
#>

param(
    [string]$ProjectRoot = "D:\facts\ytclfr"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

function Write-Step  { param([string]$msg) Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Write-Ok    { param([string]$msg) Write-Host "  [OK]     $msg" -ForegroundColor Green }
function Write-Skip  { param([string]$msg) Write-Host "  [SKIP]   $msg" -ForegroundColor Yellow }
function Write-Fail  { param([string]$msg) Write-Host "  [ERROR]  $msg" -ForegroundColor Red }
function Write-Info  { param([string]$msg) Write-Host "  [INFO]   $msg" -ForegroundColor Gray }

function Test-Command {
    param([string]$Name)
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Test-WingetPackage {
    param([string]$PackageId)
    $result = winget list --id $PackageId --exact 2>$null
    return ($LASTEXITCODE -eq 0 -and $result -match $PackageId)
}

function Install-WingetPackage {
    param(
        [string]$PackageId,
        [string]$CommandCheck   # binary name to check in PATH (optional)
    )
    if ($CommandCheck -and (Test-Command $CommandCheck)) {
        Write-Skip "$PackageId  ($CommandCheck already in PATH)"
        return
    }
    if (Test-WingetPackage $PackageId) {
        Write-Skip "$PackageId  (already installed via winget)"
        return
    }
    Write-Info "Installing $PackageId ..."
    winget install --id $PackageId --silent --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "winget install $PackageId failed (exit $LASTEXITCODE)"
        throw "Install failed: $PackageId"
    }
    Write-Ok "$PackageId installed."
}

function Invoke-Cmd {
    # NOTE: parameter is named $CmdArgs (not $Args) to avoid collision with
    # PowerShell's automatic $Args variable, which caused splatting failures.
    param([string]$Cmd, [string[]]$CmdArgs, [string]$WorkDir = $PWD)
    Push-Location $WorkDir
    try {
        & $Cmd @CmdArgs
        if ($LASTEXITCODE -ne 0) { throw "Command failed: $Cmd $CmdArgs (exit $LASTEXITCODE)" }
    } finally {
        Pop-Location
    }
}

function Get-PythonExe {
    <#
    .SYNOPSIS
        Resolve the Python 3.13 executable path.
        Returns a hashtable: @{ UseLauncher=$true/$false; Exe="..." }
    #>

    # 1. Try the Windows Python Launcher (py.exe) — most reliable on Windows.
    if (Test-Command "py") {
        $ver = & py -3.13 --version 2>&1
        if ($LASTEXITCODE -eq 0 -and $ver -match "Python 3\.13") {
            Write-Info "Resolved Python 3.13 via Windows Launcher (py -3.13): $ver"
            return @{ UseLauncher = $true; Exe = "py" }
        }
    }

    # 2. `python` in PATH.
    if (Test-Command "python") {
        $ver = & python --version 2>&1
        if ($ver -match "Python 3\.13") {
            Write-Info "Resolved Python 3.13 via PATH: $ver"
            return @{ UseLauncher = $false; Exe = "python" }
        }
    }

    # 3. Well-known install paths (user and system).
    $candidates = @(
        "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe",
        "C:\Python313\python.exe",
        "C:\Program Files\Python313\python.exe",
        "$env:ProgramFiles\Python313\python.exe"
    )
    foreach ($path in $candidates) {
        if (Test-Path $path) {
            $ver = & $path --version 2>&1
            if ($ver -match "Python 3\.13") {
                Write-Info "Resolved Python 3.13 at: $path ($ver)"
                return @{ UseLauncher = $false; Exe = $path }
            }
        }
    }

    # 4. Not found — give actionable instructions.
    Write-Fail "Python 3.13 not found."
    Write-Info "Install it with:"
    Write-Info "  winget install --id Python.Python.3.13 --silent --accept-package-agreements --accept-source-agreements"
    Write-Info "Then close and reopen this terminal, and re-run the script."
    throw "Python 3.13 is required but was not found."
}

# ---------------------------------------------------------------------------
# Step 1 — Prerequisites via winget
# ---------------------------------------------------------------------------

Write-Step "STEP 1 — Install prerequisites"

if (-not (Test-Command "winget")) {
    Write-Fail "winget not found. Install 'App Installer' from the Microsoft Store first."
    exit 1
}
Write-Ok "winget available"

Install-WingetPackage -PackageId "Python.Python.3.13" -CommandCheck "python"
Install-WingetPackage -PackageId "PostgreSQL.PostgreSQL.16" -CommandCheck "psql"
Install-WingetPackage -PackageId "Gyan.FFmpeg"              -CommandCheck "ffmpeg"
Install-WingetPackage -PackageId "yt-dlp.yt-dlp"           -CommandCheck "yt-dlp"
Install-WingetPackage -PackageId "OpenJS.NodeJS.LTS"        -CommandCheck "node"

# Refresh PATH so newly installed binaries are visible in this session.
$env:PATH = [System.Environment]::GetEnvironmentVariable("PATH","Machine") + ";" +
            [System.Environment]::GetEnvironmentVariable("PATH","User")

# Verify critical binaries are now resolvable.
foreach ($bin in @("psql","ffmpeg","yt-dlp","node","npm")) {
    if (Test-Command $bin) {
        $ver = (& $bin --version 2>&1 | Select-Object -First 1)
        Write-Ok "$bin   →   $ver"
    } else {
        Write-Fail "$bin not found in PATH after install. Restart this terminal and re-run."
        exit 1
    }
}

# ---------------------------------------------------------------------------
# Step 2 — WSL + Redis
# ---------------------------------------------------------------------------

Write-Step "STEP 2 — WSL + Redis"

if (-not (Get-Command "wsl" -ErrorAction SilentlyContinue)) {
    Write-Fail "wsl.exe not found. Enable Windows Subsystem for Linux in Windows Features first."
    exit 1
}

$wslListRaw = (wsl --list --quiet 2>$null) -join "`n"
$wslListClean = $wslListRaw -replace "`0", ""
$ubuntuInstalled = $wslListClean -match "Ubuntu"

if ($ubuntuInstalled) {
    Write-Skip "WSL Ubuntu already installed"
} else {
    Write-Info "Ubuntu not found in WSL. Installing (this may take several minutes)..."
    wsl --install -d Ubuntu --no-launch
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "wsl --install failed. Try running 'wsl --install -d Ubuntu' manually, then re-run this script."
        exit 1
    }
    Write-Ok "WSL Ubuntu installed."
    Write-Info "You may need to reboot. After reboot, open Ubuntu once to set up your Linux username,"
    Write-Info "then re-run this script."
    exit 0
}

$redisReachable = $false
try {
    $tcpClient = New-Object System.Net.Sockets.TcpClient
    $tcpClient.Connect("127.0.0.1", 6379)
    $tcpClient.Close()
    $redisReachable = $true
} catch { }

if ($redisReachable) {
    Write-Skip "Redis already listening on 127.0.0.1:6379"
} else {
    Write-Info "Starting Redis inside WSL Ubuntu (non-interactive)..."
    wsl -d Ubuntu --exec bash -c "
        set -e
        if ! command -v redis-server > /dev/null 2>&1; then
            sudo apt-get update -qq
            sudo apt-get install -y -qq redis-server
        fi
        if ! sudo service redis-server status > /dev/null 2>&1; then
            sudo service redis-server start
        fi
    "
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "Failed to start Redis inside WSL. Run these manually inside Ubuntu:"
        Write-Info "  sudo apt install -y redis-server"
        Write-Info "  sudo service redis-server start"
        exit 1
    }

    Start-Sleep -Seconds 2
    try {
        $tcpClient2 = New-Object System.Net.Sockets.TcpClient
        $tcpClient2.Connect("127.0.0.1", 6379)
        $tcpClient2.Close()
        Write-Ok "Redis is now reachable on 127.0.0.1:6379"
    } catch {
        Write-Fail "Redis still not reachable after start attempt. Check WSL networking."
        exit 1
    }
}

# ---------------------------------------------------------------------------
# Step 3 — PostgreSQL database + user
# ---------------------------------------------------------------------------

Write-Step "STEP 3 — PostgreSQL database and user"

if (-not $env:YTCLFR_DB_PASSWORD) {
    $secPwd = Read-Host "Enter a strong password for the PostgreSQL 'ytclfr' user" -AsSecureString
    $env:YTCLFR_DB_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
        [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secPwd)
    )
}
$dbPassword = $env:YTCLFR_DB_PASSWORD

$dbExists = $false
try {
    $result = & psql -U postgres -tAc "SELECT 1 FROM pg_database WHERE datname='ytclfr'" 2>$null
    $dbExists = ($result.Trim() -eq "1")
} catch { }

if ($dbExists) {
    Write-Skip "Database 'ytclfr' already exists"
    # Always sync the user password so it matches what was entered above,
    # keeping the PG user and .env DATABASE_URL in sync on every run.
    Write-Info "Syncing 'ytclfr' user password..."
    $syncSql = @"
DO `$`$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'ytclfr') THEN
    CREATE USER ytclfr WITH PASSWORD '$dbPassword';
  ELSE
    ALTER USER ytclfr WITH PASSWORD '$dbPassword';
  END IF;
END
`$`$;
GRANT ALL PRIVILEGES ON DATABASE ytclfr TO ytclfr;
"@
    $syncSql | & psql -U postgres
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "Failed to sync 'ytclfr' password. Check your postgres superuser credentials."
        exit 1
    }
    Write-Ok "Password synced."
} else {
    Write-Info "Creating PostgreSQL user and database..."
    $sql = @"
DO `$`$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'ytclfr') THEN
    CREATE USER ytclfr WITH PASSWORD '$dbPassword';
  ELSE
    ALTER USER ytclfr WITH PASSWORD '$dbPassword';
  END IF;
END
`$`$;
CREATE DATABASE ytclfr OWNER ytclfr;
GRANT ALL PRIVILEGES ON DATABASE ytclfr TO ytclfr;
"@
    $sql | & psql -U postgres
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "Failed to create database/user. Check your postgres superuser credentials."
        exit 1
    }
    Write-Ok "Database 'ytclfr' and user created."
}

# ---------------------------------------------------------------------------
# Step 4 — Python virtual environment + packages
# ---------------------------------------------------------------------------

Write-Step "STEP 4 — Python virtual environment"

if (-not (Test-Path $ProjectRoot)) {
    Write-Fail "Project root not found: $ProjectRoot"
    Write-Info "Clone the repo first: git clone <repo-url> $ProjectRoot"
    exit 1
}

$venvPath     = Join-Path $ProjectRoot ".venv"
$venvPython   = Join-Path $venvPath "Scripts\python.exe"
$venvPip      = Join-Path $venvPath "Scripts\pip.exe"
$venvActivate = Join-Path $venvPath "Scripts\Activate.ps1"

if (Test-Path $venvPython) {
    Write-Skip "Virtual environment already exists at $venvPath"
} else {
    Write-Info "Resolving Python 3.13..."
    $py = Get-PythonExe   # throws if not found

    Write-Info "Creating virtual environment with Python 3.13..."

    # FIX: Call Python directly — do NOT use Invoke-Cmd / argument splatting.
    # Python 3.13's new REPL interceptor breaks when arguments are passed via
    # PowerShell's @Args splatting, causing Python to drop into an interactive
    # shell instead of executing -m venv. Direct invocation avoids this.
    if ($py.UseLauncher) {
        & py -3.13 -m venv $venvPath
    } else {
        & $py.Exe -m venv $venvPath
    }

    if ($LASTEXITCODE -ne 0) {
        Write-Fail "Failed to create virtual environment (exit $LASTEXITCODE)"
        exit 1
    }

    # Verify the venv was actually created with Python 3.13.
    $venvVer = & $venvPython --version 2>&1
    if ($venvVer -notmatch "Python 3\.13") {
        Write-Fail "Virtual environment Python version is not 3.13: $venvVer"
        Write-Info "Delete $venvPath and re-run after confirming Python 3.13 is installed."
        exit 1
    }
    Write-Ok "Virtual environment created: $venvVer"
}

Write-Info "Upgrading pip..."
& $venvPython -m pip install --upgrade pip --quiet
if ($LASTEXITCODE -ne 0) { Write-Fail "pip upgrade failed"; exit 1 }

# Install the project in editable mode.
Write-Info "Installing project packages..."
try {
    & $venvPip install -e ".[all]" --quiet
    if ($LASTEXITCODE -ne 0) { throw "pip install [all] failed" }
    Write-Ok "Python packages installed."
} catch {
    Write-Info "Retrying without [all] extra..."
    & $venvPip install -e "." --quiet
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "pip install failed. Check pyproject.toml dependencies."
        exit 1
    }
    Write-Ok "Python packages installed (no extras)."
}

# Verify key packages are importable.
foreach ($pkg in @("fastapi","celery","alembic","redis","slowapi")) {
    $check = & $venvPython -c "import $pkg; print($pkg.__version__)" 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Ok "$pkg $check"
    } else {
        Write-Fail "$pkg not importable — check your pyproject.toml dependencies."
    }
}

# PaddleOCR check (heavy dep, may not be installed without [all] extra)
$paddleCheck = & $venvPython -c "import paddleocr; print(paddleocr.__version__)" 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Ok "paddleocr $paddleCheck"
} else {
    Write-Info "paddleocr not installed (requires [all] extra or manual pip install paddleocr)."
}

# ---------------------------------------------------------------------------
# Step 5 — .env file
# ---------------------------------------------------------------------------

Write-Step "STEP 5 — Environment file"

$envFile    = Join-Path $ProjectRoot ".env"
$envExample = Join-Path $ProjectRoot ".env.example"

if (Test-Path $envFile) {
    Write-Skip ".env already exists — not overwriting"
} else {
    if (-not (Test-Path $envExample)) {
        Write-Fail ".env.example not found at $envExample"
        exit 1
    }
    Copy-Item $envExample $envFile
    Write-Ok ".env created from .env.example"
}

$envContent = Get-Content $envFile -Raw

function Set-EnvVar {
    param([string]$Content, [string]$Key, [string]$Value)
    if ($Content -match "(?m)^$Key=") {
        return $Content -replace "(?m)^$Key=.*", "$Key=$Value"
    } else {
        return $Content + "`n$Key=$Value"
    }
}

$envContent = Set-EnvVar $envContent "DATABASE_URL"           "postgresql+psycopg://ytclfr:$dbPassword@localhost:5432/ytclfr"
$envContent = Set-EnvVar $envContent "REDIS_URL"              "redis://localhost:6379/0"
$envContent = Set-EnvVar $envContent "CELERY_BROKER_URL"      "redis://localhost:6379/0"
$envContent = Set-EnvVar $envContent "CELERY_RESULT_BACKEND"  "redis://localhost:6379/1"
$envContent = Set-EnvVar $envContent "CORS_ALLOWED_ORIGINS"   '["http://localhost:3000"]'
$envContent = Set-EnvVar $envContent "YT_DLP_BIN"             "yt-dlp"
$envContent = Set-EnvVar $envContent "FFMPEG_BIN"             "ffmpeg"

Set-Content $envFile $envContent -NoNewline
Write-Ok ".env populated with local defaults."

Write-Info ""
Write-Info "  >>> You still need to set these manually in .env: <<<"
Write-Info "      OPENROUTER_API_KEY=<your key>"
Write-Info "      SPOTIFY_CLIENT_ID=<your client id>"
Write-Info "      SPOTIFY_CLIENT_SECRET=<your client secret>"
Write-Info ""

# ---------------------------------------------------------------------------
# Step 6 — Alembic migrations
# ---------------------------------------------------------------------------

Write-Step "STEP 6 — Database migrations"

$alembic = Join-Path $venvPath "Scripts\alembic.exe"
if (-not (Test-Path $alembic)) {
    Write-Fail "alembic not found at $alembic — did package install succeed?"
    exit 1
}

Push-Location $ProjectRoot
try {
    $currentRev = & $alembic current 2>&1
    Write-Info "Current alembic revision: $currentRev"
    & $alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw "alembic upgrade head failed" }
    Write-Ok "Migrations applied."
} finally {
    Pop-Location
}

# ---------------------------------------------------------------------------
# Step 7 — Frontend npm install
# ---------------------------------------------------------------------------

Write-Step "STEP 7 — Frontend dependencies"

$frontendDir    = Join-Path $ProjectRoot "apps\frontend"
$frontendEnv    = Join-Path $frontendDir ".env.local"
$frontendEnvEx  = Join-Path $frontendDir ".env.example"
$nodeModulesDir = Join-Path $frontendDir "node_modules"

if (-not (Test-Path $frontendDir)) {
    Write-Fail "Frontend directory not found: $frontendDir"
    exit 1
}

if (Test-Path $frontendEnv) {
    Write-Skip ".env.local already exists"
} else {
    if (Test-Path $frontendEnvEx) {
        Copy-Item $frontendEnvEx $frontendEnv
        Write-Ok ".env.local created from .env.example"
    } else {
        "NEXT_PUBLIC_API_BASE_URL=http://localhost:8000" | Set-Content $frontendEnv
        Write-Ok ".env.local created with default API URL"
    }
}

$feEnv = Get-Content $frontendEnv -Raw
$feEnv = Set-EnvVar $feEnv "NEXT_PUBLIC_API_BASE_URL" "http://localhost:8000"
Set-Content $frontendEnv $feEnv -NoNewline

if (Test-Path $nodeModulesDir) {
    Write-Skip "node_modules already present — skipping npm install"
} else {
    Write-Info "Running npm install..."
    Invoke-Cmd "npm" @("install","--prefer-offline") -WorkDir $frontendDir
    Write-Ok "npm packages installed."
}

# ---------------------------------------------------------------------------
# Step 8 — Smoke test
# ---------------------------------------------------------------------------

Write-Step "STEP 8 — Smoke test (requires API to be running)"

Write-Info "The API is NOT started automatically by this script."
Write-Info "Open three separate terminals and run:"
Write-Info ""
Write-Info "  Terminal 1 (API):"
Write-Info "    cd $ProjectRoot"
Write-Info "    .\.venv\Scripts\Activate.ps1"
Write-Info "    uvicorn ytclfr_api.main:app --host 0.0.0.0 --port 8000 --reload"
Write-Info ""
Write-Info "  Terminal 2 (Worker):"
Write-Info "    cd $ProjectRoot"
Write-Info "    .\.venv\Scripts\Activate.ps1"
Write-Info "    celery -A ytclfr_worker.worker:celery_app worker --loglevel=INFO --pool=solo"
Write-Info "    (--pool=solo is required on Windows)"
Write-Info ""
Write-Info "  Terminal 3 (Frontend):"
Write-Info "    cd $frontendDir"
Write-Info "    npm run dev"
Write-Info ""
Write-Info "Then test with:"
Write-Info '    curl http://localhost:8000/api/v1/health'
Write-Info '    # Expected: {"status":"ok","checks":{"db":true,"redis":true},...}'
Write-Info ""

try {
    $response = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/health" `
                                  -Method GET -TimeoutSec 3 -ErrorAction Stop
    $statusOk = $response.status -eq "ok"
    if ($statusOk) {
        Write-Ok "Health check passed: $($response | ConvertTo-Json -Compress)"
    } else {
        Write-Fail "Health check returned degraded: $($response | ConvertTo-Json -Compress)"
    }
} catch {
    Write-Info "API not running yet — start it manually using the commands above."
}

Write-Host ""
Write-Host "Setup complete." -ForegroundColor Green