"""Use case for OCR extraction from video frames.

Replaces the stub implementation with a real one that delegates to the
PaddleOCR engine and text cleaner adapters injected at construction time.
This keeps the use case unit-testable by swapping adapters for fakes.
"""

from __future__ import annotations

from pathlib import Path

from ytclfr_core.errors.exceptions import OCRProcessingError
from ytclfr_core.logging.logger import get_logger
from ytclfr_infra.ocr.ocr_engine import OCRFrameInput, OCRLine, PaddleOCREngine
from ytclfr_infra.ocr.text_cleaner import TextCleaner, TextCleaningResult

logger = get_logger(__name__)


class RunOCRUseCase:
    """Extract and normalise text from a list of frame images.

    Adapter dependencies are injected so tests can supply lightweight fakes
    without needing a real PaddleOCR installation.
    """

    def __init__(self, ocr_engine: PaddleOCREngine, text_cleaner: TextCleaner) -> None:
        self._engine = ocr_engine
        self._cleaner = text_cleaner

    def execute(
        self,
        frame_inputs: list[OCRFrameInput],
    ) -> tuple[list[OCRLine], TextCleaningResult]:
        """Run OCR on the provided frames and return raw lines plus cleaned result.

        Args:
            frame_inputs: Timestamped frame image descriptors.

        Returns:
            A tuple of (raw_ocr_lines, cleaning_result) so callers can
            access both the unfiltered lines (for DB persistence) and the
            deduplicated text (for AI parsing).

        Raises:
            OCRProcessingError: If the engine fails or frame paths are missing.
        """
        if not frame_inputs:
            logger.warning("RunOCRUseCase called with empty frame list.")
            return [], TextCleaningResult(
                cleaned_text="",
                cleaned_lines=[],
                duplicate_matches=[],
                dropped_line_count=0,
            )

        try:
            ocr_lines = self._engine.extract_from_frames(frame_inputs)
        except OCRProcessingError:
            raise
        except Exception as exc:
            raise OCRProcessingError("OCR extraction failed unexpectedly.") from exc

        merged_text = "\n".join(
            line.text for line in ocr_lines if line.text.strip()
        )
        try:
            cleaning_result = self._cleaner.clean_text(merged_text)
        except Exception as exc:
            raise OCRProcessingError("Text cleaning failed unexpectedly.") from exc

        logger.info(
            "OCR use case completed.",
            extra={
                "raw_line_count": len(ocr_lines),
                "cleaned_line_count": len(cleaning_result.cleaned_lines),
                "duplicate_count": len(cleaning_result.duplicate_matches),
                "dropped_count": cleaning_result.dropped_line_count,
            },
        )
        return ocr_lines, cleaning_result
