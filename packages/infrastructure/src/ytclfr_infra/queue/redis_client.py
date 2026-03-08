"""Redis connectivity helper."""

import redis

from ytclfr_core.config import Settings
from ytclfr_core.errors.exceptions import ConfigurationError


def build_redis_client(settings: Settings) -> redis.Redis:
    """Build and validate a Redis client instance."""
    try:
        client = redis.from_url(settings.redis_url, decode_responses=True)
        client.ping()
        return client
    except Exception as exc:
        raise ConfigurationError("Redis connection failed.") from exc
