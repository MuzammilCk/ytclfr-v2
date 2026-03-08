"""Backward-compatible OCR module re-export."""

from ytclfr_infra.ocr.ocr_engine import OCRFrameInput, OCRLine, PaddleOCREngine

__all__ = ["OCRFrameInput", "OCRLine", "PaddleOCREngine"]
