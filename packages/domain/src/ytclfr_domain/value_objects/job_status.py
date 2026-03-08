"""Domain value object for job lifecycle states."""

from enum import StrEnum


class JobStatus(StrEnum):
    """Allowed processing states for a video job."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
