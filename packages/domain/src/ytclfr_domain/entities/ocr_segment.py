"""Domain entity for OCR extraction segments."""

from dataclasses import dataclass


@dataclass(slots=True)
class OCRSegment:
    """Represents one OCR text segment and confidence value."""

    text: str
    confidence: float
