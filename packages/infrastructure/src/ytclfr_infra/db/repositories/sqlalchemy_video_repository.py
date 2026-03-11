"""SQLAlchemy implementation of the video repository contract.

Extended with update_status so that JobLifecycleService and individual
pipeline tasks can update video processing state through the repository
interface rather than reaching into ORM models directly.
"""

from uuid import UUID

from sqlalchemy.orm import Session, sessionmaker

from ytclfr_core.errors.exceptions import RepositoryError
from ytclfr_core.utils.time_utils import utc_now
from ytclfr_domain.entities.video_record import VideoRecord
from ytclfr_domain.repositories.video_repository import VideoRepository
from ytclfr_infra.db.models import VideoModel
from ytclfr_infra.db.session import session_scope


class SQLAlchemyVideoRepository(VideoRepository):
    """Persist and retrieve video metadata with SQLAlchemy."""

    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory

    def create(self, video: VideoRecord) -> VideoRecord:
        """Create and persist a new video record."""
        model = VideoModel(
            id=video.video_id,
            source_url=video.source_url,
            status=video.status,
            title=video.title,
            description=video.description,
            created_at=video.created_at,
            updated_at=video.updated_at,
        )
        try:
            with session_scope(self._factory) as session:
                session.add(model)
            return video
        except Exception as exc:
            raise RepositoryError("Failed to create video in database.") from exc

    def get(self, video_id: UUID) -> VideoRecord | None:
        """Fetch one video by identifier."""
        try:
            with session_scope(self._factory) as session:
                model = session.get(VideoModel, video_id)
                if model is None:
                    return None
                return self._to_entity(model)
        except Exception as exc:
            raise RepositoryError("Failed to fetch video from database.") from exc

    def update_status(
        self,
        video_id: UUID,
        status: str,
        *,
        storage_path: str | None = None,
        title: str | None = None,
    ) -> None:
        """Update video processing status and optional metadata.

        Args:
            video_id: Video to update.
            status: New status string. Use VideoStatus enum values.
            storage_path: Local path to the downloaded video file.
            title: Resolved video title from yt-dlp.

        Raises:
            RepositoryError: If the video does not exist or the update fails.
        """
        try:
            with session_scope(self._factory) as session:
                model = session.get(VideoModel, video_id)
                if model is None:
                    raise RepositoryError(f"Video not found for status update: {video_id}")
                model.status = status
                model.updated_at = utc_now()
                if storage_path is not None:
                    model.storage_path = storage_path
                if title is not None and title.strip():
                    model.title = title.strip()
        except RepositoryError:
            raise
        except Exception as exc:
            raise RepositoryError(
                f"Failed to update video status for {video_id}."
            ) from exc

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_entity(model: VideoModel) -> VideoRecord:
        """Map an ORM model row to a domain entity."""
        return VideoRecord(
            video_id=model.id,
            source_url=model.source_url,
            status=model.status,
            title=model.title,
            description=model.description,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
