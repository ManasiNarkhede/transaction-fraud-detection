"""Async Redis client setup."""

import logging

import redis.asyncio as redis

from app.config import settings

redis_client: redis.Redis | None = None
logger = logging.getLogger(__name__)


def get_redis() -> redis.Redis | None:
    """Return the live Redis client, or None if not yet initialized.

    Always read the module global at call time. Modules must call this at
    use-time rather than binding ``redis_client`` at import time, otherwise
    they capture the initial ``None`` before ``init_redis()`` runs.
    """
    return redis_client


async def init_redis() -> None:
    """Initialize Redis client and verify connectivity."""
    global redis_client
    redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    try:
        await redis_client.ping()
        logger.info("redis_connected")
    except Exception as exc:
        logger.warning("redis_connection_failed", extra={"error": str(exc)})
        # Phase 1: Do not crash startup. Streams/caching will be added later.


async def close_redis() -> None:
    """Close Redis client."""
    global redis_client
    if redis_client:
        await redis_client.close()
        redis_client = None


async def ping() -> bool:
    """Ping Redis to verify connectivity."""
    if redis_client is None:
        return False
    try:
        return bool(await redis_client.ping())
    except Exception:
        return False
