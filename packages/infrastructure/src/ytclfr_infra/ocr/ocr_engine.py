"""OCR engine implementation using PaddleOCR."""

import os

# Must be set BEFORE paddle is imported anywhere in the process.
# Fixes PaddlePaddle >=3.3 crash: "ConvertPirAttribute2RuntimeAttribute
# not support [pir::ArrayAttribute<pir::DoubleAttribute>]"
os.environ.setdefault("FLAGS_enable_pir_in_executor", "0")
os.environ.setdefault("FLAGS_enable_pir_api", "0")
os.environ.setdefault("FLAGS_use_mkldnn", "0")

from dataclasses import dataclass
from pathlib import Path

from ytclfr_core.errors.exceptions import OCRProcessingError


@dataclass(slots=True)
class OCRFrameInput:
    """Single frame input for OCR execution."""

    image_path: Path
    timestamp_seconds: float


@dataclass(slots=True)
class OCRLine:
    """Single OCR line output with source timestamp."""

    timestamp_seconds: float
    text: str
    confidence: float
    source_image: Path


class PaddleOCREngine:
    """Run PaddleOCR for frame images with validation and filtering."""

    def __init__(
        self,
        language: str = "en",
        use_gpu: bool = False,
        batch_size: int = 8,
        min_confidence: float = 0.5,
    ) -> None:
        if batch_size <= 0:
            raise OCRProcessingError("OCR batch_size must be greater than zero.")
        if min_confidence < 0.0 or min_confidence > 1.0:
            raise OCRProcessingError("OCR min_confidence must be between 0.0 and 1.0.")
        try:
            from paddleocr import PaddleOCR
        except ModuleNotFoundError as exc:
            raise OCRProcessingError("PaddleOCR is not installed.") from exc
        try:
            self._ocr = self._build_ocr_client(
                paddle_ocr_cls=PaddleOCR,
                language=language,
                use_gpu=use_gpu,
            )
        except Exception as exc:
            raise OCRProcessingError("Failed to initialize PaddleOCR.") from exc
        self._batch_size = int(batch_size)
        self._min_confidence = float(min_confidence)

    def extract(self, image_paths: list[Path]) -> list[OCRLine]:
        """Backward-compatible OCR extraction from image paths only."""
        frame_inputs = [
            OCRFrameInput(image_path=Path(path), timestamp_seconds=0.0)
            for path in image_paths
        ]
        return self.extract_from_frames(frame_inputs)

    def extract_from_frames(self, frames: list[OCRFrameInput]) -> list[OCRLine]:
        """Run OCR for timestamped frame images using fixed-size batches."""
        if not frames:
            return []
        normalized_frames: list[OCRFrameInput] = []
        for frame in frames:
            image_path = Path(frame.image_path)
            if not image_path.exists() or not image_path.is_file():
                raise OCRProcessingError(f"Frame image does not exist: {image_path}")
            normalized_frames.append(
                OCRFrameInput(
                    image_path=image_path,
                    timestamp_seconds=max(0.0, float(frame.timestamp_seconds)),
                )
            )

        lines: list[OCRLine] = []
        try:
            for batch_start in range(0, len(normalized_frames), self._batch_size):
                batch = normalized_frames[batch_start : batch_start + self._batch_size]
                for frame in batch:
                    lines.extend(self._extract_one(frame))
            return lines
        except OCRProcessingError:
            raise
        except Exception as exc:
            raise OCRProcessingError("PaddleOCR extraction failed.") from exc

    def _extract_one(self, frame: OCRFrameInput) -> list[OCRLine]:
        """Run OCR for one image and map PaddleOCR output into typed rows."""
        try:
            result = self._ocr.ocr(str(frame.image_path))
        except Exception as exc:
            raise OCRProcessingError(f"PaddleOCR failed for image: {frame.image_path}") from exc

        lines: list[OCRLine] = []
        for text, confidence in self._iter_text_confidence_pairs(result):
            if confidence < self._min_confidence:
                continue
            lines.append(
                OCRLine(
                    timestamp_seconds=frame.timestamp_seconds,
                    text=text,
                    confidence=min(max(confidence, 0.0), 1.0),
                    source_image=frame.image_path,
                )
            )
        return lines

    def _build_ocr_client(
        self,
        paddle_ocr_cls: type,
        language: str,
        use_gpu: bool,
    ) -> object:
        """Build PaddleOCR instance with compatibility for multiple versions."""
        device = "gpu" if use_gpu else "cpu"
        try:
            return paddle_ocr_cls(
                use_angle_cls=True,
                lang=language,
                device=device,
                enable_mkldnn=False,
            )
        except Exception as first_exc:
            message = str(first_exc).lower()
            if "unknown argument: device" not in message and "unknown argument: enable_mkldnn" not in message:
                raise
            try:
                return paddle_ocr_cls(
                    use_angle_cls=True,
                    lang=language,
                    use_gpu=use_gpu,
                )
            except Exception:
                return paddle_ocr_cls(use_angle_cls=True, lang=language)

    def _iter_text_confidence_pairs(self, result: object) -> list[tuple[str, float]]:
        """Normalize PaddleOCR outputs from old/new APIs into text-confidence tuples."""
        pairs: list[tuple[str, float]] = []
        for page in result or []:
            if isinstance(page, dict):
                texts = page.get("rec_texts") or []
                scores = page.get("rec_scores") or []
                for idx, raw_text in enumerate(texts):
                    text = str(raw_text).strip()
                    if not text:
                        continue
                    raw_score = scores[idx] if idx < len(scores) else 0.0
                    pairs.append((text, float(raw_score)))
                continue

            for item in page or []:
                if len(item) < 2:
                    continue
                text_conf = item[1]
                if not isinstance(text_conf, (list, tuple)) or len(text_conf) < 2:
                    continue
                text = str(text_conf[0]).strip()
                if not text:
                    continue
                pairs.append((text, float(text_conf[1])))
        return pairs
