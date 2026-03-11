"""Redis pub/sub implementation of the EventPublisher protocol.

Worker tasks call publish_job_event() after each lifecycle transition.
The SSE API endpoint subscribes to the matching channel and streams the
event as a Server-Sent Event to the connected browser.

Channel naming scheme:
    ytclfr:job_events:{job_id}

Message format (JSON):
    {
        "job_id": "<uuid>",
        "status": "RUNNING",
        "video_id": "<uuid or null>",
        "error_message": null,
        "timestamp": "2026-03-11T10:00:00+00:00"
    }
"""

from __future__ import annotations

import json
from uuid import UUID

import redis

from ytclfr_core.errors.exceptions import YTCLFRError
from ytclfr_core.logging.logger import get_logger
from ytclfr_core.utils.time_utils import utc_now
from ytclfr_domain.repositories.event_publisher import EventPublisher

logger = get_logger(__name__)

_CHANNEL_PREFIX = "ytclfr:job_events"


def _channel_name(job_id: UUID) -> str:
    """Build the Redis pub/sub channel name for a job."""
    return f"{_CHANNEL_PREFIX}:{job_id}"


class RedisEventPublisher:
    """Publish job lifecycle events to a Redis pub/sub channel.

    A single synchronous Redis client is held per instance. Worker tasks
    use the lru_cached get_event_publisher() factory so the connection is
    created once per worker process.
    """

    def __init__(self, redis_url: str) -> None:
        try:
            self._client = redis.from_url(redis_url, decode_responses=True)
            # Eagerly validate connectivity.
            self._client.ping()
        except Exception as exc:
            raise YTCLFRError(
                f"RedisEventPublisher: failed to connect to Redis at {redis_url!r}."
            ) from exc

    def publish_job_event(
        self,
        *,
        job_id: UUID,
        status: str,
        video_id: UUID | None,
        error_message: str | None,
    ) -> None:
        """Publish a job status event to the job-specific Redis channel.

        Failures are swallowed here; the caller (JobLifecycleService) also
        wraps publish calls in a try/except so pipeline execution is never
        interrupted by a pub/sub failure.
        """
        message = json.dumps(
            {
                "job_id": str(job_id),
                "status": status,
                "video_id": str(video_id) if video_id is not None else None,
                "error_message": error_message,
                "timestamp": utc_now().isoformat(),
            },
            ensure_ascii=True,
        )
        channel = _channel_name(job_id)
        try:
            subscriber_count = self._client.publish(channel, message)
            logger.debug(
                "Job event published.",
                extra={
                    "channel": channel,
                    "status": status,
                    "subscribers": subscriber_count,
                },
            )
        except Exception:
            logger.warning(
                "Failed to publish job event to Redis.",
                extra={"channel": channel, "status": status},
            )


class NoOpEventPublisher:
    """No-op publisher for use in tests or when Redis is unavailable."""

    def publish_job_event(
        self,
        *,
        job_id: UUID,
        status: str,
        video_id: UUID | None,
        error_message: str | None,
    ) -> None:
        """Accept and discard the event silently."""
