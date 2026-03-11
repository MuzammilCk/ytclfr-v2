"""Celery tasks for OCR stages.

Delegates OCR extraction and text cleaning to RunOCRUseCase.
State transitions use JobLifecycleService via VideoStatus enum.
"""

from pathlib import Path
from typing import Any

from celery import shared_task

from ytclfr_contracts.task_models import ExtractFramesTaskResult, OCRTaskResult
from ytclfr_core.logging.logger import get_logger
from ytclfr_domain.value_objects.video_status import VideoStatus
from ytclfr_infra.ocr.ocr_engine import OCRFrameInput
from ytclfr_worker.tasks.task_support import (
    get_job_lifecycle_service,
    get_run_ocr_use_case,
    get_worker_settings,
    persist_ocr_results,
    retry_or_fail,
)

logger = get_logger(__name__)


@shared_task(bind=True, name="ytclfr.pipeline.run_ocr", max_retries=3)
def run_ocr(self, task_payload: dict[str, Any]) -> dict[str, Any]:
    """Run OCR on extracted frames and persist OCR rows."""
    payload = ExtractFramesTaskResult.model_validate(task_payload)
    lifecycle = get_job_lifecycle_service()
    try:
        settings = get_worker_settings()
        lifecycle.update_video_status(payload.video_id, VideoStatus.RUNNING_OCR)

        frame_inputs = [
            OCRFrameInput(
                image_path=Path(frame.image_path),
                timestamp_seconds=frame.timestamp_seconds,
            )
            for frame in payload.frames
        ]

        ocr_lines, cleaning_result = get_run_ocr_use_case().execute(frame_inputs)

        # Persist raw OCR rows for audit/debugging.
        persist_ocr_results(
            job_id=payload.job_id,
            frame_refs=[frame.model_dump(mode="json") for frame in payload.frames],
            ocr_lines=ocr_lines,
            min_confidence=settings.ocr_min_confidence,
        )

        lifecycle.update_video_status(payload.video_id, VideoStatus.OCR_COMPLETED)

        stage_result = OCRTaskResult(
            job_id=payload.job_id,
            video_id=payload.video_id,
            video_url=payload.video_url,
            title=payload.title,
            job_dir=payload.job_dir,
            ocr_text=cleaning_result.cleaned_text,
        )
        logger.info(
            "OCR stage completed.",
            extra={
                "job_id": str(payload.job_id),
                "line_count": len(cleaning_result.cleaned_lines),
                "duplicate_count": len(cleaning_result.duplicate_matches),
                "dropped_line_count": cleaning_result.dropped_line_count,
            },
        )
        return stage_result.model_dump(mode="json")

    except Exception as exc:
        logger.exception("OCR stage failed.", extra={"job_id": str(payload.job_id)})
        retry_or_fail(task=self, exc=exc, job_id=str(payload.job_id), stage="run_ocr")
