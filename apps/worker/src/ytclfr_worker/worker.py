"""Celery worker module entrypoint."""

from ytclfr_worker.celery_app import celery_app

__all__ = ["celery_app"]
