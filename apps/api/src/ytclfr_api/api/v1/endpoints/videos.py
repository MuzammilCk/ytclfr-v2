"""Video-related informational endpoints."""

from fastapi import APIRouter, HTTPException, status

router = APIRouter()


@router.get("/videos/supported")
def supported_video_sources() -> dict[str, list[str]]:
    """List currently supported video input sources."""
    try:
        return {"sources": ["youtube"]}
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load supported sources.",
        ) from exc
