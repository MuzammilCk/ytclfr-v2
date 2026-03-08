"""OCR package exports."""

from ytclfr_infra.ocr.ocr_engine import OCRFrameInput, OCRLine, PaddleOCREngine
from ytclfr_infra.ocr.text_cleaner import DuplicateMatch, TextCleaner, TextCleaningResult

__all__ = [
    "OCRFrameInput",
    "OCRLine",
    "PaddleOCREngine",
    "DuplicateMatch",
    "TextCleaner",
    "TextCleaningResult",
]
