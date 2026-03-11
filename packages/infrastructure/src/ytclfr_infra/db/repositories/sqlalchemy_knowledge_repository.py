"""SQLAlchemy implementation of the knowledge repository contract.

Key changes from the original:
1. Added upsert_parsed_output() — replaces the DELETE+INSERT pattern with
   targeted updates for existing rows, eliminating the transient empty-result
   window during task retries.
2. get_items_by_video_id() now maps raw_response["action_output"] into
   KnowledgeItem.action_output so the API can expose it to the frontend.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session, sessionmaker

from ytclfr_core.errors.exceptions import RepositoryError
from ytclfr_core.utils.time_utils import utc_now
from ytclfr_domain.entities.knowledge_item import KnowledgeItem
from ytclfr_domain.repositories.knowledge_repository import KnowledgeRepository
from ytclfr_infra.db.models import JobModel, ParsedContentModel
from ytclfr_infra.db.session import session_scope


class SQLAlchemyKnowledgeRepository(KnowledgeRepository):
    """Persist and fetch structured knowledge items."""

    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def save_items(self, job_id: UUID, items: list[KnowledgeItem]) -> None:
        """Replace knowledge items for one job (legacy path via PipelineRunner)."""
        try:
            with session_scope(self._factory) as session:
                job = session.get(JobModel, job_id)
                if job is None:
                    raise RepositoryError(
                        f"Job not found for parsed content save: {job_id}"
                    )
                session.query(ParsedContentModel).filter(
                    ParsedContentModel.job_id == job_id
                ).delete()
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
        except RepositoryError:
            raise
        except Exception as exc:
            raise RepositoryError("Failed to save knowledge items.") from exc

    def upsert_parsed_output(
        self,
        job_id: UUID,
        video_id: UUID,
        parsed_payload: dict[str, Any],
    ) -> None:
        """Idempotently persist AI parsed output.

        Strategy:
        - SUMMARY row: update in place if it exists, insert if not.
        - POINT rows: insert new ones, update matching ones, delete
          orphans that are no longer present in the new payload.

        This makes the operation safe to call multiple times for the same
        job_id — no data is deleted until the new payload is fully written.
        """
        summary = str(parsed_payload.get("summary", "")).strip()
        raw_points = parsed_payload.get("points", [])
        points = [str(p).strip() for p in raw_points if str(p).strip()]
        entities = [
            str(e).strip()
            for e in parsed_payload.get("entities", [])
            if str(e).strip()
        ]
        if not summary:
            summary = "\n".join(points)

        try:
            with session_scope(self._factory) as session:
                now = utc_now()

                # ---- Upsert SUMMARY row ----
                existing_summary = (
                    session.query(ParsedContentModel)
                    .filter_by(job_id=job_id, content_type="SUMMARY")
                    .first()
                )
                if existing_summary is not None:
                    existing_summary.summary = summary
                    existing_summary.tags = entities
                    existing_summary.entities = entities
                    existing_summary.raw_response = parsed_payload
                    existing_summary.updated_at = now
                else:
                    session.add(
                        ParsedContentModel(
                            job_id=job_id,
                            video_id=video_id,
                            content_type="SUMMARY",
                            title="Video Summary",
                            summary=summary,
                            tags=entities,
                            entities=entities,
                            raw_response=parsed_payload,
                        )
                    )

                # ---- Upsert POINT rows ----
                existing_points: list[ParsedContentModel] = (
                    session.query(ParsedContentModel)
                    .filter_by(job_id=job_id, content_type="POINT")
                    .all()
                )
                # Build a map of {summary_text -> model} for existing points.
                existing_by_text: dict[str, ParsedContentModel] = {
                    (row.summary or ""): row for row in existing_points
                }

                new_point_texts: set[str] = set()
                for point in points:
                    new_point_texts.add(point)
                    if point in existing_by_text:
                        # Update tags on the existing row (text unchanged).
                        existing_by_text[point].tags = entities
                        existing_by_text[point].entities = entities
                        existing_by_text[point].updated_at = now
                    else:
                        # Insert a new point row.
                        session.add(
                            ParsedContentModel(
                                job_id=job_id,
                                video_id=video_id,
                                content_type="POINT",
                                title="Key Point",
                                summary=point,
                                tags=entities,
                                entities=entities,
                                raw_response=None,
                            )
                        )

                # Delete orphaned POINT rows that are no longer in the payload.
                for text, orphan_row in existing_by_text.items():
                    if text not in new_point_texts:
                        session.delete(orphan_row)

        except RepositoryError:
            raise
        except Exception as exc:
            raise RepositoryError("Failed to upsert parsed output.") from exc

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

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
                return [self._to_knowledge_item(row) for row in rows]
        except Exception as exc:
            raise RepositoryError("Failed to fetch knowledge items.") from exc

    def get_items_by_video_id(self, video_id: UUID) -> list[KnowledgeItem]:
        """Fetch knowledge items by video identifier.

        Maps raw_response["action_output"] into KnowledgeItem.action_output
        so the API result endpoint can expose it to the frontend.
        """
        try:
            with session_scope(self._factory) as session:
                rows = (
                    session.query(ParsedContentModel)
                    .filter(ParsedContentModel.video_id == video_id)
                    .order_by(ParsedContentModel.created_at.asc())
                    .all()
                )
                return [self._to_knowledge_item(row) for row in rows]
        except Exception as exc:
            raise RepositoryError("Failed to fetch video knowledge items.") from exc

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_knowledge_item(row: ParsedContentModel) -> KnowledgeItem:
        """Map one ORM row to a KnowledgeItem domain entity."""
        action_output: dict[str, Any] | None = None
        if row.raw_response and isinstance(row.raw_response, dict):
            action_output = row.raw_response.get("action_output") or None

        return KnowledgeItem(
            title=row.title or "Untitled",
            description=row.summary or "",
            tags=[str(tag) for tag in (row.tags or []) if str(tag).strip()],
            action_output=action_output,
        )
