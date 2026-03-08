"""SQLAlchemy implementation of the video repository contract."""

from uuid import UUID

from sqlalchemy.orm import Session, sessionmaker

from ytclfr_core.errors.exceptions import RepositoryError
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
                return VideoRecord(
                    video_id=model.id,
                    source_url=model.source_url,
                    status=model.status,
                    title=model.title,
                    description=model.description,
                    created_at=model.created_at,
                    updated_at=model.updated_at,
                )
        except Exception as exc:
            raise RepositoryError("Failed to fetch video from database.") from exc
