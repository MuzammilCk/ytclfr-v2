"""FastAPI dependency providers."""

from ytclfr_app.use_cases.fetch_knowledge import FetchKnowledgeUseCase
from ytclfr_app.use_cases.fetch_video_result import FetchVideoResultUseCase
from ytclfr_app.use_cases.submit_job import SubmitJobUseCase
from ytclfr_domain.repositories.job_repository import JobRepository
from ytclfr_api.wiring import get_container


def get_submit_job_use_case() -> SubmitJobUseCase:
    """Provide submit-job use case instance."""
    return get_container().submit_job_use_case


def get_fetch_knowledge_use_case() -> FetchKnowledgeUseCase:
    """Provide fetch-knowledge use case instance."""
    return get_container().fetch_knowledge_use_case


def get_fetch_video_result_use_case() -> FetchVideoResultUseCase:
    """Provide fetch-result-by-video use case instance."""
    return get_container().fetch_video_result_use_case


def get_job_repository() -> JobRepository:
    """Provide job repository instance."""
    return get_container().job_repository
