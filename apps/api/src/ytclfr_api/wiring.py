"""Dependency wiring for API runtime."""

from functools import lru_cache
from uuid import UUID

from celery import Celery

from ytclfr_app.services.pipeline_orchestrator import PipelineDispatcher, PipelineOrchestrator
from ytclfr_app.use_cases.fetch_knowledge import FetchKnowledgeUseCase
from ytclfr_app.use_cases.fetch_video_result import FetchVideoResultUseCase
from ytclfr_app.use_cases.submit_job import SubmitJobUseCase
from ytclfr_core.config import Settings, get_settings
from ytclfr_core.errors.exceptions import YTCLFRError
from ytclfr_core.logging.logger import configure_logging
from ytclfr_domain.repositories.job_repository import JobRepository
from ytclfr_domain.repositories.knowledge_repository import KnowledgeRepository
from ytclfr_domain.repositories.video_repository import VideoRepository
from ytclfr_infra.db import models  # noqa: F401
from ytclfr_infra.db.repositories.sqlalchemy_job_repository import SQLAlchemyJobRepository
from ytclfr_infra.db.repositories.sqlalchemy_knowledge_repository import SQLAlchemyKnowledgeRepository
from ytclfr_infra.db.repositories.sqlalchemy_video_repository import SQLAlchemyVideoRepository
from ytclfr_infra.db.session import Base, build_engine, build_session_factory
from ytclfr_infra.queue.celery_config import build_celery_app


class CeleryPipelineDispatcher(PipelineDispatcher):
    """Dispatch processing jobs to Celery."""

    def __init__(self, celery_app: Celery) -> None:
        self._celery_app = celery_app

    def enqueue_pipeline(self, job_id: UUID) -> None:
        """Queue pipeline execution task."""
        try:
            self._celery_app.send_task("ytclfr.pipeline.run", kwargs={"job_id": str(job_id)})
        except Exception as exc:
            raise YTCLFRError("Failed to enqueue pipeline task.") from exc


class AppContainer:
    """Container for runtime dependencies."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        configure_logging(settings)

        engine = build_engine(settings)
        Base.metadata.create_all(bind=engine)
        session_factory = build_session_factory(engine)

        self.job_repository: JobRepository = SQLAlchemyJobRepository(session_factory)
        self.knowledge_repository: KnowledgeRepository = SQLAlchemyKnowledgeRepository(session_factory)
        self.video_repository: VideoRepository = SQLAlchemyVideoRepository(session_factory)

        celery_app = build_celery_app(settings, app_name="ytclfr-api")
        orchestrator = PipelineOrchestrator(CeleryPipelineDispatcher(celery_app))
        self.submit_job_use_case = SubmitJobUseCase(
            self.job_repository,
            self.video_repository,
            orchestrator,
        )
        self.fetch_knowledge_use_case = FetchKnowledgeUseCase(self.knowledge_repository)
        self.fetch_video_result_use_case = FetchVideoResultUseCase(self.knowledge_repository)


@lru_cache(maxsize=1)
def get_container() -> AppContainer:
    """Build and cache API container."""
    settings = get_settings()
    return AppContainer(settings)
