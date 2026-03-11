"""Application service for managing job and video lifecycle state transitions.

This service consolidates mark_job_running / mark_job_failed /
mark_job_completed / update_video_status, which were previously scattered
as standalone functions in the worker task_support module.

Centralising them here:
- Makes the business logic unit-testable without Celery.
- Removes direct ORM-model access from the delivery layer.
- Publishes real-time status events via the EventPublisher protocol so
  the SSE endpoint can stream them to connected browsers.
"""

from __future__ import annotations

from uuid import UUID

from ytclfr_core.errors.exceptions import RepositoryError
from ytclfr_core.logging.logger import get_logger
from ytclfr_core.utils.time_utils import utc_now
from ytclfr_domain.repositories.event_publisher import EventPublisher
from ytclfr_domain.repositories.job_repository import JobRepository
from ytclfr_domain.repositories.video_repository import VideoRepository
from ytclfr_domain.value_objects.job_status import JobStatus
from ytclfr_domain.value_objects.video_status import VideoStatus

logger = get_logger(__name__)


class JobLifecycleService:
    """Coordinate job and video state transitions throughout the pipeline.

    All state mutations go through the repository contracts, keeping the
    service decoupled from SQLAlchemy and from the Celery delivery layer.
    """

    def __init__(
        self,
        job_repository: JobRepository,
        video_repository: VideoRepository,
        event_publisher: EventPublisher,
    ) -> None:
        self._jobs = job_repository
        self._videos = video_repository
        self._events = event_publisher

    # ------------------------------------------------------------------
    # Job transitions
    # ------------------------------------------------------------------

    def mark_running(self, job_id: UUID) -> None:
        """Transition job to RUNNING and linked video to PROCESSING.

        Increments attempt counter and records started_at on first attempt.

        Raises:
            RepositoryError: If the job does not exist.
        """
        now = utc_now()
        job = self._jobs.get(job_id)
        if job is None:
            raise RepositoryError(f"Job not found: {job_id}")

        job.status = JobStatus.RUNNING
        job.error_message = None
        job.updated_at = now
        job.attempts = (job.attempts or 0) + 1
        if job.started_at is None:
            job.started_at = now

        self._jobs.update(job)

        if job.video_id is not None:
            self._videos.update_status(job.video_id, VideoStatus.PROCESSING)

        self._publish(job_id=job_id, status=JobStatus.RUNNING, video_id=job.video_id)
        logger.info("Job marked RUNNING.", extra={"job_id": str(job_id), "attempt": job.attempts})

    def mark_completed(self, job_id: UUID) -> None:
        """Transition job to COMPLETED and linked video to COMPLETED.

        Raises:
            RepositoryError: If the job does not exist.
        """
        now = utc_now()
        job = self._jobs.get(job_id)
        if job is None:
            raise RepositoryError(f"Job not found: {job_id}")

        job.status = JobStatus.COMPLETED
        job.error_message = None
        job.completed_at = now
        job.updated_at = now

        self._jobs.update(job)

        if job.video_id is not None:
            self._videos.update_status(job.video_id, VideoStatus.COMPLETED)

        self._publish(job_id=job_id, status=JobStatus.COMPLETED, video_id=job.video_id)
        logger.info("Job marked COMPLETED.", extra={"job_id": str(job_id)})

    def mark_failed(self, job_id: UUID, error_message: str) -> None:
        """Transition job to FAILED and linked video to FAILED.

        Args:
            job_id: Job to mark as failed.
            error_message: Human-readable failure reason (truncated to 4000 chars).

        Raises:
            RepositoryError: If the job does not exist.
        """
        now = utc_now()
        job = self._jobs.get(job_id)
        if job is None:
            raise RepositoryError(f"Job not found: {job_id}")

        truncated = error_message[:4000] if error_message else ""
        job.status = JobStatus.FAILED
        job.error_message = truncated
        job.completed_at = now
        job.updated_at = now

        self._jobs.update(job)

        if job.video_id is not None:
            self._videos.update_status(job.video_id, VideoStatus.FAILED)

        self._publish(
            job_id=job_id,
            status=JobStatus.FAILED,
            video_id=job.video_id,
            error_message=truncated,
        )
        logger.error(
            "Job marked FAILED.",
            extra={"job_id": str(job_id), "error_message": truncated[:200]},
        )

    # ------------------------------------------------------------------
    # Video stage transitions
    # ------------------------------------------------------------------

    def update_video_status(
        self,
        video_id: UUID,
        status: VideoStatus,
        *,
        storage_path: str | None = None,
        title: str | None = None,
    ) -> None:
        """Update the video record's stage status and optional metadata.

        Args:
            video_id: Video to update.
            status: New VideoStatus value.
            storage_path: Set when the video file has been stored locally.
            title: Set when the title is resolved from yt-dlp metadata.
        """
        self._videos.update_status(
            video_id,
            status.value,
            storage_path=storage_path,
            title=title,
        )
        logger.debug(
            "Video status updated.",
            extra={"video_id": str(video_id), "status": status.value},
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _publish(
        self,
        *,
        job_id: UUID,
        status: JobStatus,
        video_id: UUID | None,
        error_message: str | None = None,
    ) -> None:
        """Publish a lifecycle event, swallowing failures gracefully."""
        try:
            self._events.publish_job_event(
                job_id=job_id,
                status=status.value,
                video_id=video_id,
                error_message=error_message,
            )
        except Exception:
            # Event publishing is best-effort; never block the pipeline.
            logger.warning(
                "Failed to publish job event — continuing.",
                extra={"job_id": str(job_id), "status": status.value},
            )
