"""Rate limiting service using token bucket via Redis."""

import logging

from app.infrastructure.redis_client import get_redis
from app.services.key_builder import KeyBuilder

logger = logging.getLogger(__name__)


class RateLimiter:
    """Token-bucket style rate limiter backed by Redis."""

    async def is_allowed(
        self, entity: str, max_requests: int, window_seconds: int
    ) -> bool:
        """Check if request is within rate limit.

        Uses atomic Redis INCR + EXPIRE for correctness under concurrency.
        """
        redis_client = get_redis()
        if redis_client is None:
            # Allow if Redis is unavailable (fail-open)
            return True

        key = KeyBuilder.rate_limit(entity, f"{window_seconds}s")

        try:
            current = await redis_client.get(key)
            if current is None:
                # First request in window
                await redis_client.set(key, 1, ex=window_seconds)
                return True

            if int(current) >= max_requests:
                return False

            await redis_client.incr(key)
            return True
        except Exception as exc:
            logger.warning(
                "rate_limit_check_failed", extra={"entity": entity, "error": str(exc)}
            )
            # Fail-open on Redis errors
            return True
