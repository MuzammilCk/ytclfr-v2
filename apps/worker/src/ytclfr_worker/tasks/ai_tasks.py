"""Celery tasks for AI parsing stages.

Delegates AI parsing to ParseAIUseCase.
State transitions use JobLifecycleService via VideoStatus enum.
"""

from typing import Any

from celery import shared_task

from ytclfr_contracts.task_models import OCRTaskResult, ParseTextTaskResult
from ytclfr_core.logging.logger import get_logger
from ytclfr_domain.value_objects.video_status import VideoStatus
from ytclfr_worker.tasks.task_support import (
    get_job_lifecycle_service,
    get_parse_ai_use_case,
    run_coroutine_sync,
    retry_or_fail,
)

logger = get_logger(__name__)


@shared_task(bind=True, name="ytclfr.pipeline.parse_text", max_retries=3)
def parse_text(self, task_payload: dict[str, Any]) -> dict[str, Any]:
    """Parse OCR text using OpenRouter and emit parsed payload."""
    payload = OCRTaskResult.model_validate(task_payload)
    lifecycle = get_job_lifecycle_service()
    try:
        lifecycle.update_video_status(payload.video_id, VideoStatus.PARSING_TEXT)

        parsed_payload = run_coroutine_sync(
            get_parse_ai_use_case().execute(payload.ocr_text)
        )

        lifecycle.update_video_status(payload.video_id, VideoStatus.TEXT_PARSED)

        stage_result = ParseTextTaskResult(
            job_id=payload.job_id,
            video_id=payload.video_id,
            video_url=payload.video_url,
            title=payload.title,
            job_dir=payload.job_dir,
            ocr_text=payload.ocr_text,
            parsed_payload=parsed_payload,
        )
        logger.info(
            "AI parse stage completed.", extra={"job_id": str(payload.job_id)}
        )
        return stage_result.model_dump(mode="json")

    except Exception as exc:
        logger.exception(
            "AI parse stage failed.", extra={"job_id": str(payload.job_id)}
        )
        retry_or_fail(
            task=self, exc=exc, job_id=str(payload.job_id), stage="parse_text"
        )
