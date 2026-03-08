"""Knowledge retrieval endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from ytclfr_api.api.deps import get_fetch_knowledge_use_case, get_fetch_video_result_use_case
from ytclfr_app.use_cases.fetch_knowledge import FetchKnowledgeUseCase
from ytclfr_app.use_cases.fetch_video_result import FetchVideoResultUseCase
from ytclfr_contracts.api_models import KnowledgeResponse, VideoResultResponse
from ytclfr_core.logging.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.get("/knowledge/{job_id}", response_model=KnowledgeResponse)
def get_knowledge(
    job_id: UUID,
    use_case: Annotated[FetchKnowledgeUseCase, Depends(get_fetch_knowledge_use_case)],
) -> KnowledgeResponse:
    """Return structured knowledge items for a completed job."""
    try:
        items = use_case.execute(job_id)
        return KnowledgeResponse(
            job_id=job_id,
            items=[
                {"title": item.title, "description": item.description, "tags": item.tags}
                for item in items
            ],
        )
    except Exception as exc:
        logger.exception("Failed to fetch knowledge by job id.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch knowledge.",
        ) from exc


@router.get("/result/{video_id}", response_model=VideoResultResponse)
def get_result(
    video_id: UUID,
    use_case: Annotated[FetchVideoResultUseCase, Depends(get_fetch_video_result_use_case)],
) -> VideoResultResponse:
    """Return structured parsed content for one video."""
    try:
        items = use_case.execute(video_id)
        logger.info("Fetched parsed result.", extra={"video_id": str(video_id), "count": len(items)})
        return VideoResultResponse(
            video_id=video_id,
            items=[
                {"title": item.title, "description": item.description, "tags": item.tags}
                for item in items
            ],
        )
    except Exception as exc:
        logger.exception("Failed to fetch parsed result by video id.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch result.",
        ) from exc
