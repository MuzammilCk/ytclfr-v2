"""Celery app factory and broker configuration."""

from celery import Celery

from ytclfr_core.config import Settings


def build_celery_app(settings: Settings, app_name: str = "ytclfr") -> Celery:
    """Create and configure a Celery app instance."""
    app = Celery(app_name)
    app.conf.update(
        broker_url=settings.resolved_celery_broker_url,
        result_backend=settings.resolved_celery_result_backend,
        task_always_eager=settings.celery_task_always_eager,
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        enable_utc=True,
    )
    return app
