"""Repository interface for structured knowledge.

Extended with upsert_parsed_output to support idempotent persistence
of AI-parsed results including action_output payloads.
"""

from typing import Any, Protocol
from uuid import UUID

from ytclfr_domain.entities.knowledge_item import KnowledgeItem


class KnowledgeRepository(Protocol):
    """Persistence contract for knowledge records."""

    def save_items(self, job_id: UUID, items: list[KnowledgeItem]) -> None:
        """Persist extracted knowledge for a job (legacy path)."""

    def get_items(self, job_id: UUID) -> list[KnowledgeItem]:
        """Fetch extracted knowledge for a job."""

    def get_items_by_video_id(self, video_id: UUID) -> list[KnowledgeItem]:
        """Fetch extracted knowledge for a video."""

    def upsert_parsed_output(
        self,
        job_id: UUID,
        video_id: UUID,
        parsed_payload: dict[str, Any],
    ) -> None:
        """Idempotently persist parsed AI output for a job/video pair.

        On first call this inserts the rows. On subsequent calls (e.g. task
        retries) it updates existing rows in place, preventing the transient
        empty-result window caused by DELETE + INSERT semantics.

        Args:
            job_id: Job identifier that produced this output.
            video_id: Associated video identifier.
            parsed_payload: Full AI-parsed payload including action_output.
        """
