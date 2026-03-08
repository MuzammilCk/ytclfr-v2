"""Versioned API router."""

from fastapi import APIRouter

from ytclfr_api.api.v1.endpoints import health, jobs, knowledge, spotify, videos

router = APIRouter()
router.include_router(health.router, tags=["health"])
router.include_router(jobs.router, tags=["jobs"])
router.include_router(knowledge.router, tags=["knowledge"])
router.include_router(videos.router, tags=["videos"])
router.include_router(spotify.router, tags=["spotify"])
