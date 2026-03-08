"""Video frame extraction adapter based on ffmpeg CLI."""

from dataclasses import dataclass
from pathlib import Path

from ytclfr_core.errors.exceptions import VideoProcessingError
from ytclfr_infra.execution.command_runner import CommandRunner


@dataclass(slots=True)
class FrameExtractionResult:
    """Result of frame extraction from a video file."""

    frame_paths: list[Path]


class FFmpegProcessor:
    """Extract frames from video files using ffmpeg."""

    def __init__(self, ffmpeg_binary: str, command_runner: CommandRunner) -> None:
        self._ffmpeg_binary = ffmpeg_binary
        self._command_runner = command_runner

    def extract_frames(self, video_path: Path, output_dir: Path, fps: int) -> FrameExtractionResult:
        """Extract image frames at a fixed FPS and return generated frame paths."""
        if fps <= 0:
            raise VideoProcessingError("Frame extraction FPS must be > 0.")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_template = output_dir / "frame_%06d.jpg"
        command = [
            self._ffmpeg_binary,
            "-y",
            "-i",
            str(video_path),
            "-vf",
            f"fps={fps}",
            str(output_template),
        ]
        try:
            self._command_runner.run_sync(command)
            return FrameExtractionResult(frame_paths=sorted(output_dir.glob("frame_*.jpg")))
        except Exception as exc:
            raise VideoProcessingError("Failed to extract video frames with ffmpeg.") from exc
