"""Server-Sent Events endpoint for real-time job status streaming.

Replaces the 4-second polling loop in the frontend with a push-based
model.  The worker publishes status events to Redis pub/sub via
RedisEventPublisher; this endpoint subscribes and streams them as SSE.

Usage (browser):
    const source = new EventSource('/api/v1/job-events/<job_id>');
    source.addEventListener('status_update', (e) => { ... });
    source.addEventListener('stream_end', () => source.close());

SSE event types emitted:
    status_update  — job status changed; data is JSON JobStatusEvent.
    heartbeat      — keepalive sent every 15 seconds.
    stream_end     — terminal state reached; client should close the source.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import AsyncGenerator

import redis.asyncio as aioredis
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from ytclfr_core.logging.logger import get_logger
from ytclfr_domain.value_objects.job_status import JobStatus

router = APIRouter()
logger = get_logger(__name__)

_CHANNEL_PREFIX = "ytclfr:job_events"
_HEARTBEAT_INTERVAL_SECONDS = 15
_SUBSCRIBE_TIMEOUT_SECONDS = 300  # 5 minutes max per connection


def _channel_name(job_id: str) -> str:
    return f"{_CHANNEL_PREFIX}:{job_id}"


def _is_terminal(status_value: str) -> bool:
    """Return True if the status represents a pipeline end-state."""
    return status_value.upper() in {
        JobStatus.COMPLETED.value,
        JobStatus.FAILED.value,
    }


def _sse_line(event: str, data: str) -> str:
    """Format a single SSE message block."""
    return f"event: {event}\ndata: {data}\n\n"


async def _job_event_generator(
    job_id: str,
    redis_url: str,
) -> AsyncGenerator[str, None]:
    """Async generator that yields SSE messages from Redis pub/sub.

    Subscribes to the job-specific channel, yields status_update events,
    emits heartbeats every 15 seconds to keep the connection alive, and
    closes when a terminal state is received or the timeout is reached.
    """
    client = aioredis.from_url(redis_url, decode_responses=True)
    pubsub = client.pubsub()
    channel = _channel_name(job_id)

    try:
        await pubsub.subscribe(channel)
        logger.info("SSE client subscribed.", extra={"channel": channel})

        elapsed = 0.0
        while elapsed < _SUBSCRIBE_TIMEOUT_SECONDS:
            # Non-blocking poll — returns None if no message is waiting.
            message = await pubsub.get_message(
                ignore_subscribe_messages=True, timeout=1.0
            )

            if message is not None and message.get("type") == "message":
                raw_data = message.get("data", "")
                try:
                    payload = json.loads(raw_data)
                except json.JSONDecodeError:
                    logger.warning(
                        "SSE: could not decode Redis message.",
                        extra={"channel": channel},
                    )
                    continue

                yield _sse_line("status_update", json.dumps(payload))

                if _is_terminal(payload.get("status", "")):
                    yield _sse_line("stream_end", json.dumps({"reason": "terminal_state"}))
                    return

            # Emit heartbeat every HEARTBEAT_INTERVAL_SECONDS.
            elapsed += 1.0
            if int(elapsed) % _HEARTBEAT_INTERVAL_SECONDS == 0:
                yield _sse_line("heartbeat", json.dumps({"elapsed_seconds": int(elapsed)}))

        # Timeout reached — tell the client to close and reconnect if needed.
        yield _sse_line(
            "stream_end",
            json.dumps({"reason": "timeout", "elapsed_seconds": int(elapsed)}),
        )

    except asyncio.CancelledError:
        # Client disconnected; clean up silently.
        logger.info("SSE client disconnected.", extra={"channel": channel})
    except Exception:
        logger.exception("SSE stream error.", extra={"channel": channel})
        yield _sse_line("stream_end", json.dumps({"reason": "server_error"}))
    finally:
        try:
            await pubsub.unsubscribe(channel)
            await client.aclose()
        except Exception:
            pass


@router.get("/job-events/{job_id}", include_in_schema=True)
async def stream_job_events(job_id: str) -> StreamingResponse:
    """Stream real-time job status events via Server-Sent Events.

    Connect with the browser's EventSource API.  The stream emits
    status_update events whenever the worker transitions the job through
    a new lifecycle stage.  A heartbeat is sent every 15 seconds to
    prevent idle connection timeouts.  The stream closes automatically
    once a terminal state (COMPLETED / FAILED) is received.

    Args:
        job_id: UUID string of the job to monitor.

    Returns:
        A streaming text/event-stream response.

    Raises:
        422: If job_id is not a valid UUID.
    """
    try:
        uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="job_id must be a valid UUID.",
        )

    from ytclfr_api.wiring import get_container

    container = get_container()
    redis_url = str(container.settings.redis_url)

    return StreamingResponse(
        _job_event_generator(job_id=job_id, redis_url=redis_url),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx buffering
            "Connection": "keep-alive",
        },
    )
