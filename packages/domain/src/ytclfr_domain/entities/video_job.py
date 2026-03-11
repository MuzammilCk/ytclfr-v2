"""Domain entity for video processing jobs.

Extended with started_at, completed_at, and attempts so that the
JobLifecycleService can update lifecycle timestamps through the
repository interface rather than reaching into ORM models directly.
"""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from ytclfr_domain.value_objects.job_status import JobStatus


@dataclass(slots=True)
class VideoJob:
    """Represents a video processing job tracked by the system."""

    job_id: UUID
    video_id: UUID | None
    video_url: str
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    attempts: int = 0
