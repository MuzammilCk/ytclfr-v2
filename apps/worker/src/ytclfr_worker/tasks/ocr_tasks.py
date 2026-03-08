"""Celery tasks for OCR stages."""

from pathlib import Path
from typing import Any

from celery import shared_task

from ytclfr_contracts.task_models import ExtractFramesTaskResult, OCRTaskResult
from ytclfr_core.logging.logger import get_logger
from ytclfr_infra.ocr.ocr_engine import OCRFrameInput
from ytclfr_worker.tasks.task_support import (
    get_worker_settings,
    get_ocr_engine,
    get_text_cleaner,
    persist_ocr_results,
    retry_or_fail,
    update_video_status,
)

logger = get_logger(__name__)


@shared_task(bind=True, name="ytclfr.pipeline.run_ocr", max_retries=3)
def run_ocr(self, task_payload: dict[str, Any]) -> dict[str, Any]:
    """Run OCR on extracted frames and persist OCR rows."""
    payload = ExtractFramesTaskResult.model_validate(task_payload)
    try:
        settings = get_worker_settings()
        update_video_status(video_id=payload.video_id, status="RUNNING_OCR")
        frame_inputs = [
            OCRFrameInput(
                image_path=Path(frame.image_path),
                timestamp_seconds=frame.timestamp_seconds,
            )
            for frame in payload.frames
        ]
        ocr_lines = get_ocr_engine().extract_from_frames(frame_inputs)
        merged_text = persist_ocr_results(
            job_id=payload.job_id,
            frame_refs=[frame.model_dump(mode="json") for frame in payload.frames],
            ocr_lines=ocr_lines,
            min_confidence=settings.ocr_min_confidence,
        )
        cleaned = get_text_cleaner().clean_text(merged_text)
        update_video_status(video_id=payload.video_id, status="OCR_COMPLETED")
        stage_result = OCRTaskResult(
            job_id=payload.job_id,
            video_id=payload.video_id,
            video_url=payload.video_url,
            title=payload.title,
            job_dir=payload.job_dir,
            ocr_text=cleaned.cleaned_text,
        )
        logger.info(
            "OCR stage completed.",
            extra={
                "job_id": str(payload.job_id),
                "line_count": len(cleaned.cleaned_lines),
                "duplicate_count": len(cleaned.duplicate_matches),
                "dropped_line_count": cleaned.dropped_line_count,
            },
        )
        return stage_result.model_dump(mode="json")
    except Exception as exc:
        logger.exception("OCR stage failed.", extra={"job_id": str(payload.job_id)})
        retry_or_fail(task=self, exc=exc, job_id=str(payload.job_id), stage="run_ocr")
        raise
