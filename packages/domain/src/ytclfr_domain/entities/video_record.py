"""Domain entity for persisted source videos."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(slots=True)
class VideoRecord:
    """Represents one source video persisted for processing."""

    video_id: UUID
    source_url: str
    status: str
    created_at: datetime
    updated_at: datetime
    title: str | None = None
    description: str | None = None
