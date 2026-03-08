"""Logging configuration helpers."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from logging.config import dictConfig
from typing import Any

from ytclfr_core.config import Settings

_RESERVED_LOG_RECORD_KEYS = {
    "args",
    "asctime",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "module",
    "msecs",
    "message",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "thread",
    "threadName",
    "taskName",
}


class JsonFormatter(logging.Formatter):
    """Format records as structured JSON with dynamic extra fields."""

    def __init__(self, *, service: str, environment: str) -> None:
        super().__init__()
        self._service = service
        self._environment = environment

    def format(self, record: logging.LogRecord) -> str:
        """Serialize log record to one JSON document."""
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": self._service,
            "environment": self._environment,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        for key, value in record.__dict__.items():
            if key in _RESERVED_LOG_RECORD_KEYS or key.startswith("_"):
                continue
            payload[key] = value
        if record.exc_info is not None:
            payload["exception"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack_info"] = record.stack_info
        return json.dumps(payload, default=str, ensure_ascii=True)


def configure_logging(settings: Settings) -> None:
    """Configure application logging with JSON or text formatting."""
    level = settings.log_level.upper()
    if level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        raise ValueError(f"Unsupported LOG_LEVEL: {settings.log_level}")

    formatter_key = "json" if settings.log_format == "json" else "text"
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "json": {
                    "()": "ytclfr_core.logging.logger.JsonFormatter",
                    "service": settings.service_name,
                    "environment": settings.environment,
                },
                "text": {
                    "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": formatter_key,
                }
            },
            "root": {
                "handlers": ["console"],
                "level": level,
            },
        }
    )


def get_logger(name: str) -> logging.Logger:
    """Return a logger instance for a module."""
    return logging.getLogger(name)
