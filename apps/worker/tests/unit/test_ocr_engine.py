"""Unit tests for Paddle OCR engine normalization and filtering."""

from pathlib import Path

import pytest

from ytclfr_core.errors.exceptions import OCRProcessingError
from ytclfr_infra.ocr.ocr_engine import OCRFrameInput, PaddleOCREngine


class _FakeOCR:
    """Minimal fake OCR client for deterministic tests."""

    def __init__(self, payload: list[object]) -> None:
        self._payload = payload

    def ocr(self, image_path: str) -> list[object]:
        _ = image_path
        return self._payload


def _build_engine_for_test(payload: list[object], min_confidence: float = 0.5) -> PaddleOCREngine:
    """Create engine instance without external PaddleOCR dependency."""
    engine = PaddleOCREngine.__new__(PaddleOCREngine)
    engine._ocr = _FakeOCR(payload)
    engine._batch_size = 8
    engine._min_confidence = min_confidence
    return engine


def test_extract_from_frames_filters_low_confidence(tmp_path: Path) -> None:
    """Engine should ignore lines below configured confidence threshold."""
    image_path = tmp_path / "frame.jpg"
    image_path.write_bytes(b"fake-image-bytes")
    payload = [
        [
            [None, ("HIGH_TEXT", 0.92)],
            [None, ("LOW_TEXT", 0.21)],
        ]
    ]
    engine = _build_engine_for_test(payload=payload, min_confidence=0.5)

    lines = engine.extract_from_frames(
        [OCRFrameInput(image_path=image_path, timestamp_seconds=12.5)]
    )

    assert len(lines) == 1
    assert lines[0].text == "HIGH_TEXT"
    assert lines[0].confidence == pytest.approx(0.92)
    assert lines[0].timestamp_seconds == pytest.approx(12.5)


def test_iter_text_confidence_pairs_supports_new_api_shape() -> None:
    """Engine should parse PaddleOCR v3 dictionary output shape."""
    engine = _build_engine_for_test(payload=[], min_confidence=0.0)
    result = [
        {
            "rec_texts": ["Alpha", " ", "Beta"],
            "rec_scores": [0.81, 0.72, 0.94],
        }
    ]

    pairs = engine._iter_text_confidence_pairs(result)

    assert pairs == [("Alpha", 0.81), ("Beta", 0.94)]


def test_extract_from_frames_raises_for_missing_image(tmp_path: Path) -> None:
    """Engine should fail fast when frame image path does not exist."""
    engine = _build_engine_for_test(payload=[], min_confidence=0.0)
    missing = tmp_path / "missing.jpg"

    with pytest.raises(OCRProcessingError):
        engine.extract_from_frames([OCRFrameInput(image_path=missing, timestamp_seconds=0.0)])

