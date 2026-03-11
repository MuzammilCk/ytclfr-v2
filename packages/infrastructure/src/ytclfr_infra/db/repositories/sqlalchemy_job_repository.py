"""SQLAlchemy implementation of the job repository contract.

Extended to round-trip started_at, completed_at, and attempts between
the domain entity and the ORM model. These fields are needed by
JobLifecycleService to update lifecycle timestamps through the
repository interface.
"""

from uuid import UUID

from sqlalchemy.orm import Session, sessionmaker

from ytclfr_core.errors.exceptions import RepositoryError
from ytclfr_domain.entities.video_job import VideoJob
from ytclfr_domain.repositories.job_repository import JobRepository
from ytclfr_domain.value_objects.job_status import JobStatus
from ytclfr_infra.db.models import JobModel
from ytclfr_infra.db.session import session_scope


class SQLAlchemyJobRepository(JobRepository):
    """Persist and retrieve jobs using SQLAlchemy."""

    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory

    def create(self, job: VideoJob) -> VideoJob:
        """Create and persist a new job record."""
        model = JobModel(
            id=job.job_id,
            video_id=job.video_id,
            video_url=job.video_url,
            status=job.status.value,
            error_message=job.error_message,
            started_at=job.started_at,
            completed_at=job.completed_at,
            attempts=job.attempts,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )
        try:
            with session_scope(self._factory) as session:
                session.add(model)
            return job
        except Exception as exc:
            raise RepositoryError("Failed to create job in database.") from exc

    def get(self, job_id: UUID) -> VideoJob | None:
        """Fetch one job by identifier."""
        try:
            with session_scope(self._factory) as session:
                model = session.get(JobModel, job_id)
                if model is None:
                    return None
                return self._to_entity(model)
        except Exception as exc:
            raise RepositoryError("Failed to get job from database.") from exc

    def update(self, job: VideoJob) -> VideoJob:
        """Update an existing job record with all lifecycle fields."""
        try:
            with session_scope(self._factory) as session:
                model = session.get(JobModel, job.job_id)
                if model is None:
                    raise RepositoryError("Job not found for update.")
                model.video_id = job.video_id
                model.status = job.status.value
                model.error_message = job.error_message
                model.updated_at = job.updated_at
                # Lifecycle timestamp fields — only set if provided.
                if job.started_at is not None:
                    model.started_at = job.started_at
                if job.completed_at is not None:
                    model.completed_at = job.completed_at
                if job.attempts > 0:
                    model.attempts = job.attempts
            return job
        except RepositoryError:
            raise
        except Exception as exc:
            raise RepositoryError("Failed to update job in database.") from exc

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_entity(model: JobModel) -> VideoJob:
        """Map an ORM model row to a domain entity."""
        return VideoJob(
            job_id=model.id,
            video_id=model.video_id,
            video_url=model.video_url,
            status=JobStatus(model.status),
            error_message=model.error_message,
            created_at=model.created_at,
            updated_at=model.updated_at,
            started_at=model.started_at,
            completed_at=model.completed_at,
            attempts=int(model.attempts or 0),
        )
