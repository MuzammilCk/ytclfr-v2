"""Celery task orchestration for end-to-end pipeline."""

from typing import Any

from celery import chain, shared_task

from ytclfr_contracts.task_models import PipelineTaskPayload
from ytclfr_core.logging.logger import get_logger
from ytclfr_worker.tasks.ai_tasks import parse_text
from ytclfr_worker.tasks.ocr_tasks import run_ocr
from ytclfr_worker.tasks.output_tasks import generate_output
from ytclfr_worker.tasks.task_support import mark_job_failed, mark_job_running
from ytclfr_worker.tasks.video_tasks import download_video, extract_frames

logger = get_logger(__name__)


@shared_task(bind=True, name="ytclfr.pipeline.run", max_retries=3)
def run_pipeline(self, job_id: str) -> dict[str, Any]:
    """Schedule independent stage tasks as a chained workflow."""
    payload = PipelineTaskPayload(job_id=job_id)
    try:
        mark_job_running(job_id=str(payload.job_id))
        workflow = chain(
            download_video.s(str(payload.job_id)),
            extract_frames.s(),
            run_ocr.s(),
            parse_text.s(),
            generate_output.s(),
        )
        async_result = workflow.apply_async()
        logger.info(
            "Pipeline workflow scheduled.",
            extra={"job_id": str(payload.job_id), "workflow_id": async_result.id},
        )
        return {"job_id": str(payload.job_id), "workflow_id": async_result.id}
    except Exception as exc:
        logger.exception("Pipeline orchestration failed.", extra={"job_id": str(payload.job_id)})
        mark_job_failed(job_id=str(payload.job_id), error_message=f"pipeline orchestration failed: {exc}")
        raise
