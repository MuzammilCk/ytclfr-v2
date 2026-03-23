"""Frame extraction module using FFmpeg and PySceneDetect."""
from dataclasses import dataclass
from pathlib import Path

from ytclfr_core.errors.exceptions import VideoProcessingError
from ytclfr_infra.execution.command_runner import CommandRunner


@dataclass(slots=True)
class ExtractedFrame:
    """Metadata for one extracted frame artifact."""

    image_path: Path
    timestamp_seconds: float
    source_type: str


@dataclass(slots=True)
class FrameExtractionResult:
    """Result bundle for extracted frames."""

    frames: list[ExtractedFrame]
    scene_change_count: int
    interval_count: int


class FrameExtractor:
    """Extract frames at scene changes and fixed intervals."""

    def __init__(
        self,
        ffmpeg_binary: str,
        command_runner: CommandRunner,
        interval_seconds: int = 2,
        scene_threshold: float = 27.0,
    ) -> None:
        if interval_seconds <= 0:
            raise VideoProcessingError("interval_seconds must be greater than zero.")
        if scene_threshold <= 0:
            raise VideoProcessingError("scene_threshold must be greater than zero.")
        self._ffmpeg_binary = ffmpeg_binary
        self._command_runner = command_runner
        self._interval_seconds = interval_seconds
        self._scene_threshold = scene_threshold

    def extract_frames(self, video_path: Path, output_dir: Path) -> FrameExtractionResult:
        """Extract one frame per scene change plus one frame every N seconds."""
        if not video_path.exists() or not video_path.is_file():
            raise VideoProcessingError(f"Video file does not exist: {video_path}")

        scene_dir = output_dir / "scene_changes"
        interval_dir = output_dir / "interval_2s"
        scene_dir.mkdir(parents=True, exist_ok=True)
        interval_dir.mkdir(parents=True, exist_ok=True)

        try:
            scene_timestamps = self._detect_scene_timestamps(video_path)
        except Exception:
            # Scene detection is best-effort; fall back to interval-only.
            scene_timestamps = [0.0]
        duration_seconds = self._probe_duration_seconds(video_path)
        interval_timestamps = self._build_interval_timestamps(duration_seconds)

        timestamp_sources: dict[int, set[str]] = {}
        for ts in scene_timestamps:
            key = self._timestamp_key(ts)
            timestamp_sources.setdefault(key, set()).add("scene_change")
        for ts in interval_timestamps:
            key = self._timestamp_key(ts)
            timestamp_sources.setdefault(key, set()).add("interval_2s")

        extracted_frames: list[ExtractedFrame] = []
        max_seek_seconds = max(0.0, duration_seconds - 0.04)
        for idx, key in enumerate(sorted(timestamp_sources.keys())):
            timestamp_seconds = key / 1000.0
            sources = timestamp_sources[key]
            if "scene_change" in sources:
                target_dir = scene_dir
            else:
                target_dir = interval_dir
            filename = f"frame_{idx:06d}_{key:010d}ms.jpg"
            target_path = target_dir / filename
            # Guard against EOF seeks where ffmpeg cannot decode a frame packet.
            seek_seconds = min(timestamp_seconds, max_seek_seconds)
            self._extract_single_frame(
                video_path=video_path,
                timestamp_seconds=seek_seconds,
                output_path=target_path,
            )
            extracted_frames.append(
                ExtractedFrame(
                    image_path=target_path,
                    timestamp_seconds=timestamp_seconds,
                    source_type="+".join(sorted(sources)),
                )
            )

        return FrameExtractionResult(
            frames=extracted_frames,
            scene_change_count=len(scene_timestamps),
            interval_count=len(interval_timestamps),
        )

    def _detect_scene_timestamps(self, video_path: Path) -> list[float]:
        """Detect scene boundary timestamps using PySceneDetect."""
        try:
            from scenedetect import SceneManager, open_video
            from scenedetect.detectors import ContentDetector
        except ModuleNotFoundError as exc:
            raise VideoProcessingError("PySceneDetect is not installed.") from exc

        try:
            video = open_video(str(video_path))
            scene_manager = SceneManager()
            scene_manager.add_detector(ContentDetector(threshold=self._scene_threshold))
            scene_manager.detect_scenes(video, show_progress=False)
            scenes = scene_manager.get_scene_list()
            timestamps = [max(0.0, float(start.get_seconds())) for start, _ in scenes]
            if 0.0 not in timestamps:
                timestamps.append(0.0)
            return sorted(set(timestamps))
        except Exception as exc:
            raise VideoProcessingError("Scene detection failed with PySceneDetect.") from exc

    def _build_interval_timestamps(self, duration_seconds: float) -> list[float]:
        """Build interval-based timestamps including zero."""
        if duration_seconds <= 0:
            return [0.0]
        timestamps: list[float] = []
        interval = float(self._interval_seconds)
        current = 0.0
        while current <= duration_seconds:
            timestamps.append(round(current, 3))
            current += interval
        return sorted(set(max(0.0, ts) for ts in timestamps))

    def _probe_duration_seconds(self, video_path: Path) -> float:
        """Probe media duration using ffprobe."""
        ffprobe_binary = self._resolve_ffprobe_binary(self._ffmpeg_binary)
        command = [
            ffprobe_binary,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(video_path),
        ]
        try:
            result = self._command_runner.run_sync(command)
            duration = float(result.stdout.strip())
            if duration <= 0:
                raise ValueError("Duration must be positive.")
            return duration
        except Exception as exc:
            raise VideoProcessingError("Failed to probe video duration with ffprobe.") from exc

    def _extract_single_frame(
        self,
        video_path: Path,
        timestamp_seconds: float,
        output_path: Path,
    ) -> None:
        """Extract one frame image at the provided timestamp."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        command = [
            self._ffmpeg_binary,
            "-y",
            "-ss",
            f"{max(0.0, timestamp_seconds):.3f}",
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(output_path),
        ]
        try:
            self._command_runner.run_sync(command)
            if not output_path.exists():
                raise VideoProcessingError(f"Frame file missing after extraction: {output_path}")
        except Exception as exc:
            raise VideoProcessingError(
                f"Failed to extract frame at {timestamp_seconds:.3f}s."
            ) from exc

    def _timestamp_key(self, timestamp_seconds: float) -> int:
        """Convert seconds to integer milliseconds key."""
        return int(round(max(0.0, timestamp_seconds) * 1000))

    def _resolve_ffprobe_binary(self, ffmpeg_binary: str) -> str:
        """Resolve ffprobe binary name from configured ffmpeg binary."""
        binary_name = Path(ffmpeg_binary).name.lower()
        if binary_name.startswith("ffmpeg"):
            return str(Path(ffmpeg_binary).with_name("ffprobe"))
        return "ffprobe"
