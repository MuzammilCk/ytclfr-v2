"""Unit tests for yt-dlp download fallback behavior."""

import subprocess
from pathlib import Path

import pytest

from ytclfr_core.errors.exceptions import VideoProcessingError
from ytclfr_infra.video.video_downloader import YouTubeDownloader


def test_extract_metadata_retries_without_browser_cookies_on_copy_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Metadata fetch should retry without browser cookies when the DB copy is locked."""
    downloader = YouTubeDownloader(cookies_from_browser="brave", retry_without_cookies=True)
    observed_commands: list[list[str]] = []

    def fake_run(
        command: list[str],
        *,
        capture_output: bool,
        text: bool,
        timeout: int,
        check: bool,
        cwd: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        _ = (capture_output, text, timeout, check, cwd)
        observed_commands.append(command)
        if "--cookies-from-browser" in command:
            return subprocess.CompletedProcess(
                args=command,
                returncode=1,
                stdout="",
                stderr=(
                    "ERROR: Could not copy Chrome cookie database. "
                    "See https://github.com/yt-dlp/yt-dlp/issues/7271 for more info"
                ),
            )
        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout='{"id":"abc123","title":"Demo","duration":90}',
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    metadata = downloader._extract_metadata("https://www.youtube.com/watch?v=abc123")

    assert metadata["id"] == "abc123"
    assert len(observed_commands) == 2
    assert "--cookies-from-browser" in observed_commands[0]
    assert "--cookies-from-browser" not in observed_commands[1]


def test_download_retries_without_browser_cookies_on_copy_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Video download should retry without browser cookies when cookie DB copying fails."""
    downloader = YouTubeDownloader(cookies_from_browser="brave", retry_without_cookies=True)
    video_id = "abc123"
    target_path = tmp_path / "video" / f"{video_id}.mp4"
    observed_commands: list[list[str]] = []

    monkeypatch.setattr(
        downloader,
        "_extract_metadata",
        lambda video_url: {"id": video_id, "title": "Demo", "duration": 90},
    )

    def fake_run(
        command: list[str],
        *,
        capture_output: bool,
        text: bool,
        timeout: int,
        check: bool,
        cwd: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        _ = (capture_output, text, timeout, check, cwd)
        observed_commands.append(command)
        if "--cookies-from-browser" in command:
            return subprocess.CompletedProcess(
                args=command,
                returncode=1,
                stdout="",
                stderr=(
                    "ERROR: Could not copy Chrome cookie database. "
                    "See https://github.com/yt-dlp/yt-dlp/issues/7271 for more info"
                ),
            )

        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(b"video")
        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout=f"{target_path}\n",
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = downloader.download(
        video_url="https://www.youtube.com/watch?v=abc123",
        output_dir=tmp_path / "video",
    )

    assert result.video_path == target_path
    assert result.title == "Demo"
    assert len(observed_commands) == 2
    assert "--cookies-from-browser" in observed_commands[0]
    assert "--cookies-from-browser" not in observed_commands[1]


def test_extract_metadata_preserves_cookie_copy_error_when_fallback_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cookie-copy failures should still surface when fallback is explicitly disabled."""
    downloader = YouTubeDownloader(cookies_from_browser="brave", retry_without_cookies=False)

    def fake_run(
        command: list[str],
        *,
        capture_output: bool,
        text: bool,
        timeout: int,
        check: bool,
        cwd: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        _ = (command, capture_output, text, timeout, check, cwd)
        return subprocess.CompletedProcess(
            args=command,
            returncode=1,
            stdout="",
            stderr="ERROR: Could not copy Chrome cookie database.",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(VideoProcessingError, match="Could not copy Chrome cookie database"):
        downloader._extract_metadata("https://www.youtube.com/watch?v=abc123")


def test_429_rate_limit_classified_as_retryable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """HTTP 429 from YouTube should raise a retryable error, not a network failure."""
    downloader = YouTubeDownloader(
        cookies_from_browser=None,
        retry_without_cookies=False,
        extractor_args=None,
        sleep_interval=0,
        max_sleep_interval=0,
    )

    def fake_run(
        command: list[str],
        *,
        capture_output: bool,
        text: bool,
        timeout: int,
        check: bool,
        cwd: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        _ = (command, capture_output, text, timeout, check, cwd)
        return subprocess.CompletedProcess(
            args=command,
            returncode=1,
            stdout="",
            stderr=(
                "ERROR: unable to download webpage: HTTP Error 429: Too Many Requests\n"
                "Sign in to confirm you're not a bot"
            ),
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(VideoProcessingError, match="rate-limited or bot-detected"):
        downloader._extract_metadata("https://www.youtube.com/watch?v=abc123")


def test_global_args_injected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Extractor args and sleep intervals should appear in the command."""
    downloader = YouTubeDownloader(
        cookies_from_browser=None,
        retry_without_cookies=False,
        extractor_args="player_client=tv",
        sleep_interval=2,
        max_sleep_interval=5,
    )
    observed_commands: list[list[str]] = []

    def fake_run(
        command: list[str],
        *,
        capture_output: bool,
        text: bool,
        timeout: int,
        check: bool,
        cwd: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        _ = (capture_output, text, timeout, check, cwd)
        observed_commands.append(command)
        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout='{"id":"abc123","title":"Demo","duration":90}',
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    downloader._extract_metadata("https://www.youtube.com/watch?v=abc123")

    cmd = observed_commands[0]
    assert "--extractor-args" in cmd
    ea_idx = cmd.index("--extractor-args")
    assert cmd[ea_idx + 1] == "youtube:player_client=tv"
    assert "--sleep-interval" in cmd
    assert "--max-sleep-interval" in cmd
