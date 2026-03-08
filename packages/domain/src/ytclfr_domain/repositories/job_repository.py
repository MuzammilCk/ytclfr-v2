"""Repository interface for video jobs."""

from typing import Protocol
from uuid import UUID

from ytclfr_domain.entities.video_job import VideoJob


class JobRepository(Protocol):
    """Persistence contract for job lifecycle operations."""

    def create(self, job: VideoJob) -> VideoJob:
        """Persist a new job."""

    def get(self, job_id: UUID) -> VideoJob | None:
        """Fetch one job by identifier."""

    def update(self, job: VideoJob) -> VideoJob:
        """Persist state changes for an existing job."""
