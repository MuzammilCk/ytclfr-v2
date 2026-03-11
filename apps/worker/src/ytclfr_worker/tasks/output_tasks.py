"""Celery task for final output persistence stage.

Delegates to ActionEngine for output generation, PersistOutputUseCase for
idempotent DB persistence, and JobLifecycleService for job completion.
"""

from typing import Any

from celery import shared_task

from ytclfr_contracts.task_models import GenerateOutputTaskResult, ParseTextTaskResult
from ytclfr_core.logging.logger import get_logger
from ytclfr_domain.value_objects.video_status import VideoStatus
from ytclfr_worker.tasks.task_support import (
    get_action_engine,
    get_job_lifecycle_service,
    get_persist_output_use_case,
    run_coroutine_sync,
    retry_or_fail,
)

logger = get_logger(__name__)


@shared_task(bind=True, name="ytclfr.pipeline.generate_output", max_retries=3)
def generate_output(self, task_payload: dict[str, Any]) -> dict[str, Any]:
    """Persist parsed content, run action generation, and mark job completed."""
    payload = ParseTextTaskResult.model_validate(task_payload)
    lifecycle = get_job_lifecycle_service()
    try:
        lifecycle.update_video_status(payload.video_id, VideoStatus.GENERATING_OUTPUT)

        action_output = run_coroutine_sync(
            get_action_engine().generate(
                parsed_payload=payload.parsed_payload,
                video_title=payload.title,
            )
        )

        # Merge action_output into the payload so it is stored in raw_response.
        enriched_payload = {**payload.parsed_payload, "action_output": action_output}

        # Idempotent upsert - safe on task retries.
        get_persist_output_use_case().execute(
            job_id=payload.job_id,
            video_id=payload.video_id,
            parsed_payload=enriched_payload,
        )

        lifecycle.mark_completed(payload.job_id)

        result = GenerateOutputTaskResult(
            job_id=payload.job_id,
            video_id=payload.video_id,
            status="COMPLETED",
        )
        logger.info(
            "Generate output stage completed.",
            extra={
                "job_id": str(payload.job_id),
                "action_type": action_output.get("action_type"),
                "action_status": action_output.get("status"),
            },
        )
        return result.model_dump(mode="json")

    except Exception as exc:
        logger.exception(
            "Generate output stage failed.", extra={"job_id": str(payload.job_id)}
        )
        retry_or_fail(
            task=self,
            exc=exc,
            job_id=str(payload.job_id),
            stage="generate_output",
        )
