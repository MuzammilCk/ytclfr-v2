"""Health-check endpoint.

Enhanced to verify live DB and Redis connectivity.  Returns:
- status "ok"       — both checks pass.
- status "degraded" — one or more checks failed.

Kubernetes readiness probes should monitor this endpoint and remove the
pod from the load-balancer pool when status is "degraded".
"""

from typing import Annotated

import redis
from fastapi import APIRouter, Depends
from sqlalchemy import text

from ytclfr_core.utils.time_utils import utc_now
from ytclfr_infra.db.database import session_scope

router = APIRouter()


def _check_db(session_factory) -> bool:
    """Return True if a SELECT 1 against PostgreSQL succeeds."""
    try:
        with session_scope(session_factory) as session:
            session.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _check_redis(redis_url: str) -> bool:
    """Return True if a Redis PING succeeds."""
    try:
        client = redis.from_url(redis_url, socket_connect_timeout=2, socket_timeout=2)
        client.ping()
        client.close()
        return True
    except Exception:
        return False


@router.get("/health")
def health_check() -> dict:
    """Return service health including live dependency checks.

    This endpoint is intentionally dependency-free (no Depends injection)
    so that it can be called even when the DI container has not been
    initialised.  It reads connection details from settings directly.
    """
    from ytclfr_api.wiring import get_container

    container = get_container()
    checks = {
        "db": _check_db(container.session_factory),
        "redis": _check_redis(str(container.settings.redis_url)),
    }
    status = "ok" if all(checks.values()) else "degraded"
    return {
        "status": status,
        "checks": checks,
        "timestamp": utc_now().isoformat(),
    }
