"""Security utilities for JWT token creation and verification."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from jose import JWTError, jwt

from app.config import settings


def create_access_token(user_id: UUID, role: str) -> str:
    """Create a JWT access token for a user.

    Args:
        user_id: The user's UUID.
        role: The user's role (e.g., 'admin', 'analyst').

    Returns:
        Encoded JWT access token string.
    """
    now = datetime.now(UTC)
    expire = now + timedelta(minutes=settings.access_token_expire_minutes)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "exp": expire,
        "iat": now,
        "type": "access",
    }
    return jwt.encode(  # type: ignore[no-any-return]
        payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )


def create_refresh_token(user_id: UUID) -> str:
    """Create a JWT refresh token for a user.

    Args:
        user_id: The user's UUID.

    Returns:
        Encoded JWT refresh token string.
    """
    now = datetime.now(UTC)
    expire = now + timedelta(days=settings.refresh_token_expire_days)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "exp": expire,
        "iat": now,
        "type": "refresh",
    }
    return jwt.encode(  # type: ignore[no-any-return]
        payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )


def verify_token(token: str) -> dict[str, Any] | None:
    """Verify and decode a JWT token.

    Args:
        token: The JWT token string to verify.

    Returns:
        Decoded token payload dict, or None if invalid/expired.
    """
    try:
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
        return payload  # type: ignore[no-any-return]
    except JWTError:
        return None
