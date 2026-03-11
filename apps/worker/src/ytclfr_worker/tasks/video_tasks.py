"""Celery tasks for video download and frame extraction stages.

Stage tasks delegate state transitions to JobLifecycleService via the
task_support getter. VideoStatus enum replaces bare string literals.
"""

from pathlib import Path
from typing import Any

from celery import shared_task

from ytclfr_contracts.task_models import (
    DownloadVideoTaskResult,
    ExtractFramesTaskResult,
    PipelineTaskPayload,
)
from ytclfr_core.logging.logger import get_logger
from ytclfr_domain.value_objects.video_status import VideoStatus
from ytclfr_worker.tasks.task_support import (
    get_downloader,
    get_frame_extractor,
    get_job_lifecycle_service,
    get_job_work_dir,
    load_job_context,
    persist_frames,
    retry_or_fail,
)

logger = get_logger(__name__)


@shared_task(bind=True, name="ytclfr.pipeline.download_video", max_retries=3)
def download_video(self, job_id: str) -> dict[str, Any]:
    """Download source video and emit normalised pipeline payload."""
    payload = PipelineTaskPayload(job_id=job_id)
    lifecycle = get_job_lifecycle_service()
    try:
        job_uuid, video_id, video_url = load_job_context(str(payload.job_id))

        lifecycle.update_video_status(video_id, VideoStatus.DOWNLOADING)

        work_dir = get_job_work_dir(job_uuid)
        result = get_downloader().download(
            video_url=video_url, output_dir=work_dir / "video"
        )

        lifecycle.update_video_status(
            video_id,
            VideoStatus.DOWNLOADED,
            storage_path=str(result.video_path),
            title=result.title or None,
        )

        stage_result = DownloadVideoTaskResult(
            job_id=job_uuid,
            video_id=video_id,
            video_url=video_url,
            title=result.title or None,
            job_dir=str(work_dir),
            video_path=str(result.video_path),
        )
        logger.info("Download stage completed.", extra={"job_id": str(job_uuid)})
        return stage_result.model_dump(mode="json")

    except Exception as exc:
        logger.exception(
            "Download stage failed.", extra={"job_id": str(payload.job_id)}
        )
        retry_or_fail(task=self, exc=exc, job_id=str(payload.job_id), stage="download_video")


@shared_task(bind=True, name="ytclfr.pipeline.extract_frames", max_retries=3)
def extract_frames(self, task_payload: dict[str, Any]) -> dict[str, Any]:
    """Extract frames from downloaded video and persist frame rows."""
    payload = DownloadVideoTaskResult.model_validate(task_payload)
    lifecycle = get_job_lifecycle_service()
    try:
        lifecycle.update_video_status(payload.video_id, VideoStatus.EXTRACTING_FRAMES)

        frames_dir = Path(payload.job_dir) / "frames"
        result = get_frame_extractor().extract_frames(
            video_path=Path(payload.video_path),
            output_dir=frames_dir,
        )
        frame_refs = persist_frames(video_id=payload.video_id, frames=result.frames)

        lifecycle.update_video_status(payload.video_id, VideoStatus.FRAMES_EXTRACTED)

        stage_result = ExtractFramesTaskResult(
            job_id=payload.job_id,
            video_id=payload.video_id,
            video_url=payload.video_url,
            title=payload.title,
            job_dir=payload.job_dir,
            video_path=payload.video_path,
            fps=1,
            frames=frame_refs,
        )
        logger.info(
            "Frame extraction stage completed.",
            extra={
                "job_id": str(payload.job_id),
                "frames": len(frame_refs),
                "scene_change_count": result.scene_change_count,
                "interval_count": result.interval_count,
            },
        )
        return stage_result.model_dump(mode="json")

    except Exception as exc:
        logger.exception(
            "Frame extraction stage failed.", extra={"job_id": str(payload.job_id)}
        )
        retry_or_fail(
            task=self, exc=exc, job_id=str(payload.job_id), stage="extract_frames"
        )
