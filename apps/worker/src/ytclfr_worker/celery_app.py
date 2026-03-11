"""Celery application entrypoint for background workers."""

from __future__ import annotations

from threading import Lock
from time import perf_counter
from typing import Any

from celery.signals import task_failure, task_postrun, task_prerun, task_retry, worker_process_init

from ytclfr_core.config import get_settings
from ytclfr_core.logging.logger import configure_logging, get_logger
from ytclfr_core.monitoring import (
    capture_exception,
    initialize_error_tracking,
    record_task_error,
    record_task_retry,
    record_task_timing,
    start_worker_metrics_server,
)
from ytclfr_infra.queue.celery_config import build_celery_app
from ytclfr_worker.tasks.task_support import (
    get_action_engine,
    get_ai_client,
    get_downloader,
    get_frame_extractor,
    get_ocr_engine,
    get_session_factory,
    get_text_cleaner,
)

settings = get_settings()
configure_logging(settings)
initialize_error_tracking(settings, service_name=f"{settings.service_name}-worker")
logger = get_logger(__name__)

if settings.metrics_enabled and settings.worker_metrics_port is not None:
    start_worker_metrics_server(settings.worker_metrics_port)

celery_app = build_celery_app(settings, app_name="ytclfr-worker")
celery_app.conf.update(
    task_track_started=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
)
celery_app.conf.imports = (
    "ytclfr_worker.tasks.pipeline_tasks",
    "ytclfr_worker.tasks.video_tasks",
    "ytclfr_worker.tasks.ocr_tasks",
    "ytclfr_worker.tasks.ai_tasks",
    "ytclfr_worker.tasks.output_tasks",
)
celery_app.autodiscover_tasks(packages=["ytclfr_worker.tasks"])

_TASK_STARTED_AT: dict[str, float] = {}
_TASK_STARTED_AT_LOCK = Lock()


@worker_process_init.connect
def reset_worker_singletons(**_: Any) -> None:
    """Re-initialize cached adapters after prefork worker initialization."""
    get_session_factory.cache_clear()
    get_ocr_engine.cache_clear()
    get_downloader.cache_clear()
    get_frame_extractor.cache_clear()
    get_ai_client.cache_clear()
    get_action_engine.cache_clear()
    get_text_cleaner.cache_clear()
    logger.info("Worker singletons reset after process fork.")


@task_prerun.connect
def track_task_prerun(
    task_id: str | None = None,
    task: Any | None = None,
    **_: Any,
) -> None:
    """Track task start time for latency metrics."""
    if task_id is None:
        return
    with _TASK_STARTED_AT_LOCK:
        _TASK_STARTED_AT[task_id] = perf_counter()
    task_name = getattr(task, "name", "unknown")
    logger.info(
        "Celery task started.",
        extra={"task_id": task_id, "task_name": task_name},
    )


@task_postrun.connect
def track_task_postrun(
    task_id: str | None = None,
    task: Any | None = None,
    state: str | None = None,
    **_: Any,
) -> None:
    """Observe task duration and success/failure state."""
    if task_id is None:
        return
    with _TASK_STARTED_AT_LOCK:
        started_at = _TASK_STARTED_AT.pop(task_id, None)
    if started_at is None:
        return
    duration_seconds = perf_counter() - started_at
    task_name = getattr(task, "name", "unknown")
    task_state = state or "unknown"
    if settings.metrics_enabled:
        record_task_timing(
            task_name=task_name,
            status=task_state,
            duration_seconds=duration_seconds,
        )
    logger.info(
        "Celery task completed.",
        extra={
            "task_id": task_id,
            "task_name": task_name,
            "state": task_state,
            "duration_seconds": round(duration_seconds, 6),
        },
    )


@task_failure.connect
def track_task_failure(
    task_id: str | None = None,
    sender: Any | None = None,
    exception: BaseException | None = None,
    **_: Any,
) -> None:
    """Track task failures in metrics and error tracking backend."""
    task_name = getattr(sender, "name", "unknown")
    exception_type = exception.__class__.__name__ if exception is not None else "unknown"
    if settings.metrics_enabled:
        record_task_error(task_name=task_name, exception_type=exception_type)
    if exception is not None:
        capture_exception(
            exception,
            context={"task_name": task_name, "task_id": task_id or ""},
        )
    logger.error(
        "Celery task failed.",
        extra={
            "task_name": task_name,
            "task_id": task_id or "",
            "exception_type": exception_type,
            "error_message": str(exception) if exception is not None else None,
        },
    )


@task_retry.connect
def track_task_retry(
    request: Any | None = None,
    reason: BaseException | None = None,
    **_: Any,
) -> None:
    """Track task retry events."""
    task_name = getattr(request, "task", "unknown") if request is not None else "unknown"
    if settings.metrics_enabled:
        record_task_retry(task_name=task_name, stage="task_retry")
    logger.warning(
        "Celery task retry requested.",
        extra={
            "task_name": task_name,
            "retry_reason": str(reason) if reason is not None else None,
        },
    )
