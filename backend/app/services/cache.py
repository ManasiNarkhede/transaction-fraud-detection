"""Generic cache helper with Redis backend."""

import logging
from typing import Any

import orjson

from app.infrastructure.redis_client import get_redis

logger = logging.getLogger(__name__)


class Cache:
    """Async cache helper using Redis with orjson serialization."""

    async def get(self, key: str) -> Any:
        """Get value by key, deserialize JSON."""
        redis_client = get_redis()
        if redis_client is None:
            return None
        try:
            value = await redis_client.get(key)
            if value is None:
                return None
            return orjson.loads(value)
        except Exception as exc:
            logger.warning("cache_get_failed", extra={"key": key, "error": str(exc)})
            return None

    async def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
        """Set value by key, serialize JSON."""
        redis_client = get_redis()
        if redis_client is None:
            return False
        try:
            serialized = orjson.dumps(value)
            await redis_client.set(key, serialized, ex=ttl)
            return True
        except Exception as exc:
            logger.warning("cache_set_failed", extra={"key": key, "error": str(exc)})
            return False

    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        redis_client = get_redis()
        if redis_client is None:
            return False
        try:
            result = await redis_client.delete(key)
            return bool(result > 0)
        except Exception as exc:
            logger.warning("cache_delete_failed", extra={"key": key, "error": str(exc)})
            return False

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        redis_client = get_redis()
        if redis_client is None:
            return False
        try:
            result = await redis_client.exists(key)
            return bool(result > 0)
        except Exception as exc:
            logger.warning("cache_exists_failed", extra={"key": key, "error": str(exc)})
            return False

    async def ttl(self, key: str) -> int:
        """Get remaining TTL for key in seconds."""
        redis_client = get_redis()
        if redis_client is None:
            return -2
        try:
            return int(await redis_client.ttl(key))
        except Exception as exc:
            logger.warning("cache_ttl_failed", extra={"key": key, "error": str(exc)})
            return -2

    async def expire(self, key: str, seconds: int) -> bool:
        """Set expiration on key."""
        redis_client = get_redis()
        if redis_client is None:
            return False
        try:
            result = await redis_client.expire(key, seconds)
            return bool(result)
        except Exception as exc:
            logger.warning("cache_expire_failed", extra={"key": key, "error": str(exc)})
            return False
