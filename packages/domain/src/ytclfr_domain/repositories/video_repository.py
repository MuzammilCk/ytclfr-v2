"""Repository interface for source videos."""

from typing import Protocol
from uuid import UUID

from ytclfr_domain.entities.video_record import VideoRecord


class VideoRepository(Protocol):
    """Persistence contract for video metadata records."""

    def create(self, video: VideoRecord) -> VideoRecord:
        """Persist a new video record."""

    def get(self, video_id: UUID) -> VideoRecord | None:
        """Fetch one video record by identifier."""
