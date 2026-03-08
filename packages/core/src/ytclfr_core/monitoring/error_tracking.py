"""Error tracking integration helpers."""

from __future__ import annotations

from threading import Lock
from typing import Any

from ytclfr_core.config import Settings
from ytclfr_core.logging.logger import get_logger

try:
    import sentry_sdk
except ImportError:  # pragma: no cover - guarded by dependency management.
    sentry_sdk = None

logger = get_logger(__name__)
_error_tracking_lock = Lock()
_error_tracking_initialized = False


def initialize_error_tracking(settings: Settings, *, service_name: str) -> None:
    """Initialize Sentry error tracking when DSN is configured."""
    global _error_tracking_initialized
    if _error_tracking_initialized:
        return
    if settings.sentry_dsn is None:
        logger.info("Error tracking is disabled because SENTRY_DSN is not configured.")
        return
    if sentry_sdk is None:
        logger.warning("sentry-sdk is unavailable; error tracking will remain disabled.")
        return
    with _error_tracking_lock:
        if _error_tracking_initialized:
            return
        try:
            sentry_sdk.init(
                dsn=settings.sentry_dsn,
                environment=settings.environment,
                traces_sample_rate=settings.sentry_traces_sample_rate,
                server_name=service_name,
            )
            _error_tracking_initialized = True
            logger.info(
                "Error tracking initialized.",
                extra={"service_name": service_name, "environment": settings.environment},
            )
        except Exception as exc:
            logger.exception("Failed to initialize error tracking.")
            raise RuntimeError("Could not initialize error tracking.") from exc


def capture_exception(exc: BaseException, context: dict[str, Any] | None = None) -> None:
    """Capture an exception in Sentry when tracking is initialized."""
    if not _error_tracking_initialized or sentry_sdk is None:
        return
    try:
        if context:
            with sentry_sdk.push_scope() as scope:
                for key, value in context.items():
                    scope.set_extra(key, value)
                sentry_sdk.capture_exception(exc)
            return
        sentry_sdk.capture_exception(exc)
    except Exception:
        logger.exception("Failed to report exception to error tracking backend.")

