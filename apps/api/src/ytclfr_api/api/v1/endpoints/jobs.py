"""Job submission and status endpoints.

Rate limiting is applied to the job submission endpoints to prevent a
single client from flooding the processing queue.  The limiter uses the
client IP address as the rate-limit key.

Limits (configurable via RATE_LIMIT_SUBMIT env var):
- POST /process-video : 10 requests / minute
- POST /jobs          : 10 requests / minute
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address

from ytclfr_api.api.deps import get_job_repository, get_submit_job_use_case
from ytclfr_app.use_cases.submit_job import SubmitJobUseCase
from ytclfr_contracts.api_models import (
    JobStatusResponse,
    ProcessVideoRequest,
    ProcessVideoResponse,
    SubmitJobRequest,
    SubmitJobResponse,
)
from ytclfr_core.logging.logger import get_logger
from ytclfr_domain.repositories.job_repository import JobRepository

router = APIRouter()
logger = get_logger(__name__)

# Limiter instance — registered on the app in main.py.
_limiter = Limiter(key_func=get_remote_address)


@router.post(
    "/process-video",
    response_model=ProcessVideoResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
@_limiter.limit("10/minute")
def process_video(
    request: Request,
    payload: ProcessVideoRequest,
    use_case: Annotated[SubmitJobUseCase, Depends(get_submit_job_use_case)],
) -> ProcessVideoResponse:
    """Validate YouTube URL, persist records, and enqueue async processing.

    Rate limited to 10 requests per minute per IP.
    """
    try:
        job_id = use_case.execute(payload.youtube_url)
        logger.info("Queued process-video job.", extra={"job_id": str(job_id)})
        return ProcessVideoResponse(job_id=job_id)
    except Exception as exc:
        logger.exception("Failed to process video submission.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to queue video processing job.",
        ) from exc


@router.post(
    "/jobs",
    response_model=SubmitJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
@_limiter.limit("10/minute")
def submit_job(
    request: Request,
    payload: SubmitJobRequest,
    use_case: Annotated[SubmitJobUseCase, Depends(get_submit_job_use_case)],
) -> SubmitJobResponse:
    """Submit a new video processing job.

    Rate limited to 10 requests per minute per IP.
    """
    try:
        job_id = use_case.execute(str(payload.video_url))
        logger.info(
            "Queued job from /jobs endpoint.", extra={"job_id": str(job_id)}
        )
        return SubmitJobResponse(job_id=job_id, status="PENDING")
    except Exception as exc:
        logger.exception("Failed to submit job from /jobs endpoint.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit job.",
        ) from exc


@router.get("/job-status/{id}", response_model=JobStatusResponse)
def get_job_status_by_id(
    id: UUID,
    repository: Annotated[JobRepository, Depends(get_job_repository)],
) -> JobStatusResponse:
    """Fetch current status for one job by required route naming."""
    return _load_job_status(id, repository)


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
def get_job_status(
    job_id: UUID,
    repository: Annotated[JobRepository, Depends(get_job_repository)],
) -> JobStatusResponse:
    """Fetch current status for one job."""
    return _load_job_status(job_id, repository)


def _load_job_status(job_id: UUID, repository: JobRepository) -> JobStatusResponse:
    """Load and map one job status response."""
    try:
        job = repository.get(job_id)
        if job is None:
            logger.warning("Job not found.", extra={"job_id": str(job_id)})
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Job not found."
            )
        logger.info(
            "Job status fetched.",
            extra={"job_id": str(job_id), "status": job.status.value},
        )
        return JobStatusResponse(
            job_id=job.job_id,
            video_id=job.video_id,
            status=job.status.value,
            error_message=job.error_message,
            updated_at=job.updated_at,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to fetch job status.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch job status.",
        ) from exc
