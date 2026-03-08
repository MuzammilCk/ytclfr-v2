"""Use case for submitting a new video processing job."""

from uuid import UUID, uuid4

from ytclfr_app.services.pipeline_orchestrator import PipelineOrchestrator
from ytclfr_core.errors.exceptions import RepositoryError
from ytclfr_core.utils.time_utils import utc_now
from ytclfr_domain.entities.video_job import VideoJob
from ytclfr_domain.entities.video_record import VideoRecord
from ytclfr_domain.repositories.job_repository import JobRepository
from ytclfr_domain.repositories.video_repository import VideoRepository
from ytclfr_domain.value_objects.job_status import JobStatus


class SubmitJobUseCase:
    """Create a job record and dispatch asynchronous processing."""

    def __init__(
        self,
        repository: JobRepository,
        video_repository: VideoRepository,
        orchestrator: PipelineOrchestrator,
    ) -> None:
        self._repository = repository
        self._video_repository = video_repository
        self._orchestrator = orchestrator

    def execute(self, video_url: str) -> UUID:
        """Create a job and enqueue it for asynchronous processing."""
        now = utc_now()
        video = VideoRecord(
            video_id=uuid4(),
            source_url=video_url,
            status=JobStatus.PENDING.value,
            created_at=now,
            updated_at=now,
        )
        job = VideoJob(
            job_id=uuid4(),
            video_id=video.video_id,
            video_url=video_url,
            status=JobStatus.PENDING,
            created_at=now,
            updated_at=now,
        )
        try:
            self._video_repository.create(video)
            persisted = self._repository.create(job)
            self._orchestrator.dispatch(persisted.job_id)
            return persisted.job_id
        except Exception as exc:
            raise RepositoryError("Failed to submit processing job.") from exc
