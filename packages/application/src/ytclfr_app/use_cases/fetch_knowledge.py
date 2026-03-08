"""Use case for retrieving extracted knowledge for a job."""

from uuid import UUID

from ytclfr_core.errors.exceptions import RepositoryError
from ytclfr_domain.entities.knowledge_item import KnowledgeItem
from ytclfr_domain.repositories.knowledge_repository import KnowledgeRepository


class FetchKnowledgeUseCase:
    """Fetch persisted knowledge items for a job."""

    def __init__(self, repository: KnowledgeRepository) -> None:
        self._repository = repository

    def execute(self, job_id: UUID) -> list[KnowledgeItem]:
        """Load knowledge items by job identifier."""
        try:
            return self._repository.get_items(job_id)
        except Exception as exc:
            raise RepositoryError("Failed to fetch knowledge items.") from exc
