"""Use case for retrieving parsed result by video id."""

from uuid import UUID

from ytclfr_core.errors.exceptions import RepositoryError
from ytclfr_domain.entities.knowledge_item import KnowledgeItem
from ytclfr_domain.repositories.knowledge_repository import KnowledgeRepository


class FetchVideoResultUseCase:
    """Fetch parsed content associated with a video record."""

    def __init__(self, repository: KnowledgeRepository) -> None:
        self._repository = repository

    def execute(self, video_id: UUID) -> list[KnowledgeItem]:
        """Fetch parsed content by video identifier."""
        try:
            return self._repository.get_items_by_video_id(video_id)
        except Exception as exc:
            raise RepositoryError("Failed to fetch parsed result by video id.") from exc
