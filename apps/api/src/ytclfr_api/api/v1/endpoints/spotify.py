"""Spotify enrichment informational endpoints."""

from fastapi import APIRouter, HTTPException, status

router = APIRouter()


@router.get("/spotify/status")
def spotify_module_status() -> dict[str, str]:
    """Return bootstrap status of Spotify module."""
    try:
        return {"status": "enabled"}
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load spotify status.",
        ) from exc
