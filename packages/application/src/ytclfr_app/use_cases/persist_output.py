"""Use case for persisting AI-parsed output idempotently.

Replaces the DELETE + INSERT pattern in task_support.persist_parsed_output
with an upsert strategy. This eliminates the transient empty-result window
that occurred when a consumer polled /result/{video_id} between the DELETE
and the subsequent INSERT on a task retry.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from ytclfr_core.errors.exceptions import RepositoryError
from ytclfr_core.logging.logger import get_logger
from ytclfr_domain.repositories.knowledge_repository import KnowledgeRepository

logger = get_logger(__name__)


class PersistOutputUseCase:
    """Idempotently persist AI-parsed content including action_output.

    Uses the KnowledgeRepository.upsert_parsed_output method, which
    updates existing rows or inserts new ones — making this safe to
    call multiple times for the same job_id (e.g. on task retries).
    """

    def __init__(self, knowledge_repository: KnowledgeRepository) -> None:
        self._repository = knowledge_repository

    def execute(
        self,
        job_id: UUID,
        video_id: UUID,
        parsed_payload: dict[str, Any],
    ) -> None:
        """Persist parsed AI output for a completed pipeline job.

        Args:
            job_id: Identifier of the originating job.
            video_id: Identifier of the source video.
            parsed_payload: Full AI parsed payload — must include
                summary, points, entities, and action_output keys.

        Raises:
            RepositoryError: If the persistence operation fails.
        """
        if not parsed_payload:
            raise RepositoryError("Cannot persist empty parsed payload.")

        try:
            self._repository.upsert_parsed_output(
                job_id=job_id,
                video_id=video_id,
                parsed_payload=parsed_payload,
            )
        except RepositoryError:
            raise
        except Exception as exc:
            raise RepositoryError(
                f"Failed to persist parsed output for job {job_id}."
            ) from exc

        action_type = (parsed_payload.get("action_output") or {}).get("action_type", "none")
        logger.info(
            "Parsed output persisted.",
            extra={
                "job_id": str(job_id),
                "video_id": str(video_id),
                "action_type": action_type,
            },
        )
