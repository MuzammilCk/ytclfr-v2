"""Health-check endpoint."""

from fastapi import APIRouter, HTTPException, status

from ytclfr_core.utils.time_utils import utc_now

router = APIRouter()


@router.get("/health")
def health_check() -> dict[str, str]:
    """Return service health information."""
    try:
        return {"status": "ok", "timestamp": utc_now().isoformat()}
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to build health response.",
        ) from exc
