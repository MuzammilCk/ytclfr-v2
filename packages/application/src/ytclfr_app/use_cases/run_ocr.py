"""Use case boundary for OCR extraction."""

from pathlib import Path

from ytclfr_core.errors.exceptions import OCRProcessingError
from ytclfr_domain.entities.ocr_segment import OCRSegment


class RunOCRUseCase:
    """Extract text segments from frame images."""

    def execute(self, frame_paths: list[Path]) -> list[OCRSegment]:
        """Placeholder implementation for OCR use case."""
        try:
            _ = frame_paths
            return []
        except Exception as exc:
            raise OCRProcessingError("OCR extraction failed.") from exc
