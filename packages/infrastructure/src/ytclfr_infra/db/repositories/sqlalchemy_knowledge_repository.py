"""SQLAlchemy implementation of the knowledge repository contract."""

from uuid import UUID

from sqlalchemy.orm import Session, sessionmaker

from ytclfr_core.errors.exceptions import RepositoryError
from ytclfr_domain.entities.knowledge_item import KnowledgeItem
from ytclfr_domain.repositories.knowledge_repository import KnowledgeRepository
from ytclfr_infra.db.models import JobModel, ParsedContentModel
from ytclfr_infra.db.session import session_scope


class SQLAlchemyKnowledgeRepository(KnowledgeRepository):
    """Persist and fetch structured knowledge items."""

    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory

    def save_items(self, job_id: UUID, items: list[KnowledgeItem]) -> None:
        """Replace knowledge items for one job."""
        try:
            with session_scope(self._factory) as session:
                job = session.get(JobModel, job_id)
                if job is None:
                    raise RepositoryError(f"Job not found for parsed content save: {job_id}")
                session.query(ParsedContentModel).filter(ParsedContentModel.job_id == job_id).delete()
                for item in items:
                    session.add(
                        ParsedContentModel(
                            job_id=job_id,
                            video_id=job.video_id,
                            content_type="SUMMARY",
                            title=item.title,
                            summary=item.description,
                            tags=item.tags,
                            entities=[],
                        )
                    )
        except Exception as exc:
            raise RepositoryError("Failed to save knowledge items.") from exc

    def get_items(self, job_id: UUID) -> list[KnowledgeItem]:
        """Fetch knowledge items by job identifier."""
        try:
            with session_scope(self._factory) as session:
                rows = (
                    session.query(ParsedContentModel)
                    .filter(ParsedContentModel.job_id == job_id)
                    .order_by(ParsedContentModel.created_at.asc())
                    .all()
                )
                return [
                    KnowledgeItem(
                        title=row.title or "Untitled",
                        description=row.summary or "",
                        tags=[str(tag) for tag in (row.tags or []) if str(tag).strip()],
                    )
                    for row in rows
                ]
        except Exception as exc:
            raise RepositoryError("Failed to fetch knowledge items.") from exc

    def get_items_by_video_id(self, video_id: UUID) -> list[KnowledgeItem]:
        """Fetch knowledge items by video identifier."""
        try:
            with session_scope(self._factory) as session:
                rows = (
                    session.query(ParsedContentModel)
                    .filter(ParsedContentModel.video_id == video_id)
                    .order_by(ParsedContentModel.created_at.asc())
                    .all()
                )
                return [
                    KnowledgeItem(
                        title=row.title or "Untitled",
                        description=row.summary or "",
                        tags=[str(tag) for tag in (row.tags or []) if str(tag).strip()],
                    )
                    for row in rows
                ]
        except Exception as exc:
            raise RepositoryError("Failed to fetch video knowledge items.") from exc
