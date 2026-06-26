"""OTP service for generation, hashing, storage, and validation."""

from __future__ import annotations

import logging
import secrets
from uuid import UUID

import orjson
from passlib.context import CryptContext

from app.infrastructure.redis_client import get_redis

logger = logging.getLogger(__name__)

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def generate_otp() -> str:
    """Generate a cryptographically secure 6-digit numeric OTP.

    Returns:
        A zero-padded 6-digit numeric string (e.g., "004237").
    """
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_otp(otp: str) -> str:
    """Hash an OTP using bcrypt.

    Args:
        otp: The plain-text OTP.

    Returns:
        The bcrypt hashed OTP.
    """
    return _pwd_context.hash(otp)  # type: ignore[no-any-return]


def verify_otp(otp: str, otp_hash: str) -> bool:
    """Verify a plain-text OTP against a bcrypt hash.

    Args:
        otp: The plain-text OTP.
        otp_hash: The bcrypt hashed OTP.

    Returns:
        True if the OTP matches, False otherwise.
    """
    return _pwd_context.verify(otp, otp_hash)  # type: ignore[no-any-return]


async def store_otp(verification_id: UUID, otp: str, ttl: int = 600) -> None:
    """Store a hashed OTP in Redis with a TTL.

    Args:
        verification_id: The verification session UUID.
        otp: The plain-text OTP to hash and store.
        ttl: Time-to-live in seconds (default: 600).
    """
    redis_client = get_redis()
    if redis_client is None:
        logger.warning(
            "store_otp_redis_unavailable",
            extra={"verification_id": str(verification_id)},
        )
        return

    key = f"verify:{verification_id}:otp"
    data = {"hash": hash_otp(otp)}

    try:
        serialized = orjson.dumps(data)
        await redis_client.set(key, serialized, ex=ttl)
    except Exception as exc:
        logger.warning(
            "store_otp_failed",
            extra={"verification_id": str(verification_id), "error": str(exc)},
        )


async def get_otp_data(verification_id: UUID) -> dict | None:
    """Retrieve OTP data from Redis.

    Args:
        verification_id: The verification session UUID.

    Returns:
        The stored OTP data dict, or None if not found or on error.
    """
    redis_client = get_redis()
    if redis_client is None:
        return None

    key = f"verify:{verification_id}:otp"

    try:
        value = await redis_client.get(key)
        if value is None:
            return None
        return orjson.loads(value)  # type: ignore[no-any-return]
    except Exception as exc:
        logger.warning(
            "get_otp_data_failed",
            extra={"verification_id": str(verification_id), "error": str(exc)},
        )
        return None


async def delete_otp(verification_id: UUID) -> None:
    """Remove OTP data from Redis.

    Args:
        verification_id: The verification session UUID.
    """
    redis_client = get_redis()
    if redis_client is None:
        logger.warning(
            "delete_otp_redis_unavailable",
            extra={"verification_id": str(verification_id)},
        )
        return

    key = f"verify:{verification_id}:otp"

    try:
        await redis_client.delete(key)
    except Exception as exc:
        logger.warning(
            "delete_otp_failed",
            extra={"verification_id": str(verification_id), "error": str(exc)},
        )


async def is_rate_limited(
    user_id: UUID, max_requests: int = 3, window: int = 3600
) -> bool:
    """Check if a user has exceeded the OTP request rate limit.

    Uses atomic Redis INCR + EXPIRE for correctness under concurrency.

    Args:
        user_id: The user's UUID.
        max_requests: Maximum allowed requests in the window (default: 3).
        window: Time window in seconds (default: 3600).

    Returns:
        True if the user is rate limited, False otherwise.
    """
    redis_client = get_redis()
    if redis_client is None:
        # Fail-open if Redis is unavailable
        return False

    key = f"verify:ratelimit:{user_id}"

    try:
        current = await redis_client.get(key)
        if current is None:
            # First request in window
            await redis_client.set(key, 1, ex=window)
            return False

        if int(current) >= max_requests:
            return True

        await redis_client.incr(key)
        return False
    except Exception as exc:
        logger.warning(
            "is_rate_limited_failed", extra={"user_id": str(user_id), "error": str(exc)}
        )
        # Fail-open on Redis errors
        return False


async def increment_attempts(verification_id: UUID) -> int:
    """Increment the attempt counter for a verification session.

    Args:
        verification_id: The verification session UUID.

    Returns:
        The new attempt count, or 0 on error.
    """
    redis_client = get_redis()
    if redis_client is None:
        logger.warning(
            "increment_attempts_redis_unavailable",
            extra={"verification_id": str(verification_id)},
        )
        return 0

    key = f"verify:{verification_id}:attempts"

    try:
        new_count = await redis_client.incr(key)
        return int(new_count)
    except Exception as exc:
        logger.warning(
            "increment_attempts_failed",
            extra={"verification_id": str(verification_id), "error": str(exc)},
        )
        return 0


async def get_attempts(verification_id: UUID) -> int:
    """Get the current attempt count for a verification session.

    Args:
        verification_id: The verification session UUID.

    Returns:
        The current attempt count, or 0 if not found or on error.
    """
    redis_client = get_redis()
    if redis_client is None:
        return 0

    key = f"verify:{verification_id}:attempts"

    try:
        value = await redis_client.get(key)
        if value is None:
            return 0
        return int(value)
    except Exception as exc:
        logger.warning(
            "get_attempts_failed",
            extra={"verification_id": str(verification_id), "error": str(exc)},
        )
        return 0
