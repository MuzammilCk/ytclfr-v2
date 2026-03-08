"""Repository interface for structured knowledge."""

from typing import Protocol
from uuid import UUID

from ytclfr_domain.entities.knowledge_item import KnowledgeItem


class KnowledgeRepository(Protocol):
    """Persistence contract for knowledge records."""

    def save_items(self, job_id: UUID, items: list[KnowledgeItem]) -> None:
        """Persist extracted knowledge for a job."""

    def get_items(self, job_id: UUID) -> list[KnowledgeItem]:
        """Fetch extracted knowledge for a job."""

    def get_items_by_video_id(self, video_id: UUID) -> list[KnowledgeItem]:
        """Fetch extracted knowledge for a video."""
