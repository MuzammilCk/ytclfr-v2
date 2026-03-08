"""Celery task for final output persistence stage."""

import asyncio
from typing import Any

from celery import shared_task

from ytclfr_contracts.task_models import GenerateOutputTaskResult, ParseTextTaskResult
from ytclfr_core.logging.logger import get_logger
from ytclfr_worker.tasks.task_support import (
    get_action_engine,
    mark_job_completed,
    persist_parsed_output,
    retry_or_fail,
    update_video_status,
)

logger = get_logger(__name__)


@shared_task(bind=True, name="ytclfr.pipeline.generate_output", max_retries=3)
def generate_output(self, task_payload: dict[str, Any]) -> dict[str, Any]:
    """Persist parsed content and mark pipeline as completed."""
    payload = ParseTextTaskResult.model_validate(task_payload)
    try:
        update_video_status(video_id=payload.video_id, status="GENERATING_OUTPUT")
        action_output = asyncio.run(
            get_action_engine().generate(
                parsed_payload=payload.parsed_payload,
                video_title=payload.title,
            )
        )
        enriched_payload = dict(payload.parsed_payload)
        enriched_payload["action_output"] = action_output
        persist_parsed_output(
            job_id=payload.job_id,
            video_id=payload.video_id,
            parsed_payload=enriched_payload,
        )
        mark_job_completed(job_id=str(payload.job_id))
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
        logger.exception("Generate output stage failed.", extra={"job_id": str(payload.job_id)})
        retry_or_fail(task=self, exc=exc, job_id=str(payload.job_id), stage="generate_output")
        raise
