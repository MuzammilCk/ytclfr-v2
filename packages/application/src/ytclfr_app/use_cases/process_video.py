"""Use case boundary for video download and frame extraction."""

from pathlib import Path
from uuid import UUID

from ytclfr_core.errors.exceptions import VideoProcessingError


class ProcessVideoUseCase:
    """Process raw video input into OCR-ready frames."""

    def execute(self, job_id: UUID, video_url: str, output_dir: Path) -> list[Path]:
        """Placeholder implementation for pipeline composition."""
        try:
            _ = (job_id, video_url, output_dir)
            return []
        except Exception as exc:
            raise VideoProcessingError("Video processing failed.") from exc
