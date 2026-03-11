"""Repository interface for source videos.

Extended with update_status so that the application layer can update
video processing state without reaching into ORM models directly.
"""

from typing import Protocol
from uuid import UUID

from ytclfr_domain.entities.video_record import VideoRecord


class VideoRepository(Protocol):
    """Persistence contract for video metadata records."""

    def create(self, video: VideoRecord) -> VideoRecord:
        """Persist a new video record."""

    def get(self, video_id: UUID) -> VideoRecord | None:
        """Fetch one video record by identifier."""

    def update_status(
        self,
        video_id: UUID,
        status: str,
        *,
        storage_path: str | None = None,
        title: str | None = None,
    ) -> None:
        """Update video processing status and optional metadata fields.

        Args:
            video_id: Identifier of the video to update.
            status: New status string — use VideoStatus enum values.
            storage_path: Optional local storage path once download completes.
            title: Optional resolved video title from yt-dlp metadata.
        """
