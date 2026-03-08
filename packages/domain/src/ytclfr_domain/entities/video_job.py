"""Domain entity for video processing jobs."""

from dataclasses import dataclass
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
