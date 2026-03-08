"""Prometheus metrics helpers for API and worker runtimes."""

from __future__ import annotations

from threading import Lock

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest, start_http_server

from ytclfr_core.logging.logger import get_logger

logger = get_logger(__name__)
_metrics_server_lock = Lock()
_metrics_server_started = False

_HTTP_REQUEST_TOTAL = Counter(
    "ytclfr_http_requests_total",
    "Count of processed HTTP requests.",
    labelnames=("method", "path", "status_code"),
)
_HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "ytclfr_http_request_duration_seconds",
    "HTTP request latency in seconds.",
    labelnames=("method", "path"),
)
_API_ERROR_TOTAL = Counter(
    "ytclfr_api_errors_total",
    "Count of API exceptions.",
    labelnames=("path", "exception_type"),
)
_CELERY_TASK_TOTAL = Counter(
    "ytclfr_celery_tasks_total",
    "Count of executed Celery tasks grouped by task and status.",
    labelnames=("task_name", "status"),
)
_CELERY_TASK_DURATION_SECONDS = Histogram(
    "ytclfr_celery_task_duration_seconds",
    "Celery task duration in seconds.",
    labelnames=("task_name", "status"),
)
_CELERY_TASK_RETRY_TOTAL = Counter(
    "ytclfr_celery_task_retries_total",
    "Count of Celery retries requested by task stage.",
    labelnames=("task_name", "stage"),
)
_CELERY_TASK_ERROR_TOTAL = Counter(
    "ytclfr_celery_task_errors_total",
    "Count of Celery task exceptions.",
    labelnames=("task_name", "exception_type"),
)


def _normalize_label(value: str) -> str:
    """Normalize metric label values and prevent cardinality spikes."""
    normalized = value.strip().lower()
    if not normalized:
        return "unknown"
    if len(normalized) > 120:
        return normalized[:120]
    return normalized


def record_http_request(method: str, path: str, status_code: int, duration_seconds: float) -> None:
    """Record API request count and latency."""
    try:
        method_label = _normalize_label(method.upper())
        path_label = _normalize_label(path)
        status_label = str(status_code)
        _HTTP_REQUEST_TOTAL.labels(
            method=method_label,
            path=path_label,
            status_code=status_label,
        ).inc()
        _HTTP_REQUEST_DURATION_SECONDS.labels(
            method=method_label,
            path=path_label,
        ).observe(max(0.0, duration_seconds))
    except Exception:
        logger.exception("Failed to record HTTP metrics.", extra={"path": path})


def record_api_exception(path: str, exception_type: str) -> None:
    """Record API exception counters."""
    try:
        _API_ERROR_TOTAL.labels(
            path=_normalize_label(path),
            exception_type=_normalize_label(exception_type),
        ).inc()
    except Exception:
        logger.exception("Failed to record API exception metric.", extra={"path": path})


def record_task_timing(task_name: str, status: str, duration_seconds: float) -> None:
    """Record Celery task counters and duration."""
    try:
        task_label = _normalize_label(task_name)
        status_label = _normalize_label(status)
        _CELERY_TASK_TOTAL.labels(task_name=task_label, status=status_label).inc()
        _CELERY_TASK_DURATION_SECONDS.labels(
            task_name=task_label,
            status=status_label,
        ).observe(max(0.0, duration_seconds))
    except Exception:
        logger.exception("Failed to record task timing metric.", extra={"task_name": task_name})


def record_task_retry(task_name: str, stage: str) -> None:
    """Record Celery retry requests."""
    try:
        _CELERY_TASK_RETRY_TOTAL.labels(
            task_name=_normalize_label(task_name),
            stage=_normalize_label(stage),
        ).inc()
    except Exception:
        logger.exception("Failed to record task retry metric.", extra={"task_name": task_name})


def record_task_error(task_name: str, exception_type: str) -> None:
    """Record Celery task exception counts."""
    try:
        _CELERY_TASK_ERROR_TOTAL.labels(
            task_name=_normalize_label(task_name),
            exception_type=_normalize_label(exception_type),
        ).inc()
    except Exception:
        logger.exception("Failed to record task error metric.", extra={"task_name": task_name})


def render_prometheus_metrics() -> tuple[bytes, str]:
    """Return raw Prometheus exposition payload and content type."""
    try:
        payload = generate_latest()
        return payload, CONTENT_TYPE_LATEST
    except Exception as exc:
        logger.exception("Failed to render Prometheus payload.")
        raise RuntimeError("Failed to generate Prometheus metrics.") from exc


def start_worker_metrics_server(port: int) -> None:
    """Start Prometheus HTTP exporter for worker process once."""
    global _metrics_server_started
    with _metrics_server_lock:
        if _metrics_server_started:
            return
        try:
            start_http_server(port=port)
            _metrics_server_started = True
            logger.info("Worker Prometheus exporter started.", extra={"port": port})
        except Exception as exc:
            logger.exception("Failed to start worker Prometheus exporter.", extra={"port": port})
            raise RuntimeError("Could not start worker metrics exporter.") from exc

