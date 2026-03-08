"""FastAPI application entrypoint."""

from __future__ import annotations

from time import perf_counter
from typing import Awaitable, Callable
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse, Response

from ytclfr_api.api.v1.router import router as v1_router
from ytclfr_core.config import get_settings
from ytclfr_core.logging.logger import configure_logging, get_logger
from ytclfr_core.monitoring import (
    capture_exception,
    initialize_error_tracking,
    record_api_exception,
    record_http_request,
    render_prometheus_metrics,
)


def _resolve_request_path(request: Request) -> str:
    """Resolve low-cardinality route path for logging and metrics."""
    route = request.scope.get("route")
    path_template = getattr(route, "path", None)
    if isinstance(path_template, str) and path_template.strip():
        return path_template
    return request.url.path


def create_app() -> FastAPI:
    """Build and configure FastAPI app."""
    settings = get_settings()
    configure_logging(settings)
    initialize_error_tracking(settings, service_name=f"{settings.service_name}-api")
    logger = get_logger(__name__)

    app = FastAPI(title="YTCLFR API", version="0.1.0")

    @app.middleware("http")
    async def request_logging_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Emit structured request logs and Prometheus API metrics."""
        request_id = request.headers.get("x-request-id") or str(uuid4())
        status_code = 500
        start_time = perf_counter()
        try:
            response = await call_next(request)
            response.headers["x-request-id"] = request_id
            status_code = response.status_code
            return response
        except Exception as exc:
            path = _resolve_request_path(request)
            record_api_exception(path=path, exception_type=exc.__class__.__name__)
            capture_exception(
                exc,
                context={
                    "path": path,
                    "method": request.method,
                    "request_id": request_id,
                },
            )
            logger.exception(
                "Unhandled API exception.",
                extra={
                    "request_id": request_id,
                    "http_method": request.method,
                    "path": path,
                },
            )
            raise
        finally:
            duration_seconds = perf_counter() - start_time
            path = _resolve_request_path(request)
            if settings.metrics_enabled and status_code >= 500:
                record_api_exception(path=path, exception_type=f"http_{status_code}")
            if settings.metrics_enabled:
                record_http_request(
                    method=request.method,
                    path=path,
                    status_code=status_code,
                    duration_seconds=duration_seconds,
                )
            logger.info(
                "HTTP request completed.",
                extra={
                    "request_id": request_id,
                    "http_method": request.method,
                    "path": path,
                    "status_code": status_code,
                    "duration_seconds": round(duration_seconds, 6),
                },
            )

    if settings.metrics_enabled:

        @app.get("/metrics", include_in_schema=False)
        def metrics() -> Response:
            """Expose Prometheus metrics payload."""
            try:
                payload, content_type = render_prometheus_metrics()
                return Response(content=payload, media_type=content_type)
            except Exception as exc:
                capture_exception(exc, context={"endpoint": "/metrics"})
                logger.exception("Failed to generate Prometheus metrics payload.")
                return PlainTextResponse("metrics unavailable", status_code=500)

    app.include_router(v1_router, prefix="/api/v1")
    return app


app = create_app()
