"""Celery tasks for Spotify enrichment stages."""

from celery import shared_task


@shared_task(name="ytclfr.spotify.bootstrap")
def spotify_bootstrap_task(job_id: str) -> dict[str, str]:
    """Bootstrap placeholder for Spotify-stage tasks."""
    return {"job_id": job_id, "status": "queued"}
