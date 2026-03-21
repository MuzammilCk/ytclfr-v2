"""YouTube video downloader implemented with yt-dlp subprocess execution."""

import json
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from ytclfr_core.errors.exceptions import VideoProcessingError


@dataclass(slots=True)
class DownloadResult:
    """Metadata describing a downloaded video artifact."""

    video_path: Path
    title: str
    source_url: str
    duration_seconds: int
    metadata: dict


class YouTubeDownloader:
    """Download YouTube videos with validation, metadata checks, and timeout handling."""

    def __init__(
        self,
        yt_dlp_binary: str = "yt-dlp",
        max_duration_seconds: int = 3600,
        timeout_seconds: int = 1800,
        cookies_from_browser: str | None = "brave",
        cookie_file: Path | None = None,
        retry_without_cookies: bool = True,
    ) -> None:
        if max_duration_seconds <= 0:
            raise VideoProcessingError("max_duration_seconds must be greater than zero.")
        if timeout_seconds <= 0:
            raise VideoProcessingError("timeout_seconds must be greater than zero.")
        self._yt_dlp_binary = yt_dlp_binary
        self._max_duration_seconds = max_duration_seconds
        self._timeout_seconds = timeout_seconds
        self._cookies_from_browser = cookies_from_browser.strip() if cookies_from_browser else None
        self._cookie_file = Path(cookie_file) if cookie_file is not None else None
        self._retry_without_cookies = retry_without_cookies

    def download(self, video_url: str, output_dir: Path) -> DownloadResult:
        """Validate URL, enforce duration limits, download video, and return artifact metadata."""
        self._validate_youtube_url(video_url)
        metadata = self._extract_metadata(video_url=video_url)
        duration = int(metadata.get("duration") or 0)
        if duration <= 0:
            raise VideoProcessingError("Unable to determine video duration.")
        if duration > self._max_duration_seconds:
            raise VideoProcessingError(
                f"Video duration {duration}s exceeds limit {self._max_duration_seconds}s."
            )

        output_dir.mkdir(parents=True, exist_ok=True)
        output_template = output_dir / "%(id)s.%(ext)s"
        stdout = self._run_yt_dlp_command(
            [
                self._yt_dlp_binary,
                "--no-playlist",
                "--merge-output-format",
                "mp4",
                "-f",
                "mp4/bestvideo+bestaudio/best",
                "--output",
                str(output_template),
                "--print",
                "after_move:filepath",
                video_url,
            ],
            timeout_seconds=self._timeout_seconds,
        )

        video_id = str(metadata.get("id") or "").strip()
        video_path = self._resolve_downloaded_path(
            output_dir=output_dir,
            stdout=stdout,
            video_id=video_id,
        )
        if video_path is None:
            raise VideoProcessingError("yt-dlp did not produce an output file path.")

        return DownloadResult(
            video_path=video_path,
            title=str(metadata.get("title") or ""),
            source_url=video_url,
            duration_seconds=duration,
            metadata=metadata,
        )

    def _extract_metadata(self, video_url: str) -> dict:
        """Fetch metadata from yt-dlp without downloading media."""
        stdout = self._run_yt_dlp_command(
            [
                self._yt_dlp_binary,
                "--no-playlist",
                "--skip-download",
                "--dump-single-json",
                video_url,
            ],
            timeout_seconds=120,
        )
        try:
            parsed = json.loads(stdout)
            if not isinstance(parsed, dict):
                raise VideoProcessingError("yt-dlp metadata output is not a JSON object.")
            return parsed
        except json.JSONDecodeError as exc:
            raise VideoProcessingError("Failed to parse yt-dlp metadata JSON output.") from exc

    def _run_yt_dlp_command(self, command: list[str], timeout_seconds: int) -> str:
        """Run yt-dlp with configured authentication and fallback on cookie copy failures."""
        auth_args = self._build_auth_args()
        if not auth_args:
            return self._run_command(command, timeout_seconds=timeout_seconds)

        try:
            return self._run_command(
                self._inject_auth_args(command=command, auth_args=auth_args),
                timeout_seconds=timeout_seconds,
            )
        except VideoProcessingError as exc:
            if not self._should_retry_without_cookies(exc):
                raise
            return self._run_command(command, timeout_seconds=timeout_seconds)

    def _build_auth_args(self) -> list[str]:
        """Build optional yt-dlp cookie arguments from configuration."""
        if self._cookie_file is not None:
            return ["--cookies", str(self._cookie_file)]
        if self._cookies_from_browser is not None:
            return ["--cookies-from-browser", self._cookies_from_browser]
        return []

    def _inject_auth_args(self, command: list[str], auth_args: list[str]) -> list[str]:
        """Insert authentication args immediately after the yt-dlp binary."""
        return [command[0], *auth_args, *command[1:]]

    def _should_retry_without_cookies(self, exc: VideoProcessingError) -> bool:
        """Return whether auth-specific failure should retry without cookie arguments."""
        if not self._retry_without_cookies:
            return False
        message = str(exc).lower()
        if "could not copy" in message and "cookie database" in message:
            return True
        if "permission denied" in message:
            return True
        return False

    def _resolve_downloaded_path(self, output_dir: Path, stdout: str, video_id: str) -> Path | None:
        """Resolve final downloaded file path from command output or directory scan."""
        candidates = [line.strip() for line in stdout.splitlines() if line.strip()]
        for candidate in reversed(candidates):
            candidate_path = Path(candidate)
            if candidate_path.exists():
                return candidate_path

        if video_id:
            matches = sorted(output_dir.glob(f"{video_id}.*"))
            for match in matches:
                if match.is_file():
                    return match
        return None

    def _validate_youtube_url(self, video_url: str) -> None:
        """Validate that URL is a supported YouTube watch/shorts URL."""
        parsed = urlparse(video_url.strip())
        if parsed.scheme not in {"http", "https"}:
            raise VideoProcessingError("YouTube URL must start with http or https.")

        host = (parsed.hostname or "").lower()
        allowed_hosts = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}
        if host not in allowed_hosts:
            raise VideoProcessingError("Only youtube.com and youtu.be URLs are supported.")

        if host == "youtu.be":
            if not parsed.path.strip("/"):
                raise VideoProcessingError("Short YouTube URL must include a video id.")
            return

        if parsed.path.startswith("/shorts/"):
            if not parsed.path.removeprefix("/shorts/").strip("/"):
                raise VideoProcessingError("Shorts URL must include a video id.")
            return

        if parsed.path != "/watch":
            raise VideoProcessingError("YouTube URL must use /watch or /shorts path.")

        video_id = parse_qs(parsed.query).get("v", [""])[0].strip()
        if not video_id:
            raise VideoProcessingError("YouTube watch URL must include v query parameter.")

    def _run_command(self, command: list[str], timeout_seconds: int) -> str:
        """Run yt-dlp subprocess and classify common failure modes."""
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
                cwd=tempfile.gettempdir(),
            )
        except FileNotFoundError as exc:
            raise VideoProcessingError(
                f"yt-dlp binary not found: {self._yt_dlp_binary}"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise VideoProcessingError("yt-dlp command timed out.") from exc
        except OSError as exc:
            raise VideoProcessingError(f"Failed to execute yt-dlp command: {exc}") from exc

        if completed.returncode != 0:
            stderr = (completed.stderr or "").strip()
            lower_error = stderr.lower()
            if any(
                token in lower_error
                for token in [
                    "timed out",
                    "unable to download webpage",
                    "network is unreachable",
                    "connection refused",
                    "temporary failure",
                    "name or service not known",
                ]
            ):
                raise VideoProcessingError(f"Network failure while running yt-dlp: {stderr}")
            if any(
                token in lower_error
                for token in [
                    "unsupported url",
                    "unsupported",
                    "video unavailable",
                    "private video",
                    "this video is unavailable",
                    "not available",
                ]
            ):
                raise VideoProcessingError(f"Unsupported or unavailable YouTube video: {stderr}")
            raise VideoProcessingError(f"yt-dlp command failed: {stderr}")

        return completed.stdout or ""
