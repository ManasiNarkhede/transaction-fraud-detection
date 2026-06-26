"""Authentication service with password hashing and JWT token management."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, create_refresh_token, verify_token
from app.models.user import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a plain-text password using bcrypt.

    Args:
        password: The plain-text password.

    Returns:
        The bcrypt hashed password.
    """
    return pwd_context.hash(password)  # type: ignore[no-any-return]


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plain-text password against a bcrypt hash.

    Args:
        plain: The plain-text password.
        hashed: The bcrypt hashed password.

    Returns:
        True if the password matches, False otherwise.
    """
    return pwd_context.verify(plain, hashed)  # type: ignore[no-any-return]


def create_access_token_for_user(user_id: UUID, role: str) -> str:
    """Create a JWT access token for a user.

    Args:
        user_id: The user's UUID.
        role: The user's role.

    Returns:
        Encoded JWT access token string.
    """
    return create_access_token(user_id, role)


def create_refresh_token_for_user(user_id: UUID) -> str:
    """Create a JWT refresh token for a user.

    Args:
        user_id: The user's UUID.

    Returns:
        Encoded JWT refresh token string.
    """
    return create_refresh_token(user_id)


def verify_jwt_token(token: str) -> dict[str, Any] | None:
    """Verify a JWT token and return its payload.

    Args:
        token: The JWT token string.

    Returns:
        Decoded payload dict, or None if invalid/expired.
    """
    return verify_token(token)


async def authenticate_user(
    session: AsyncSession, email: str, password: str
) -> User | None:
    """Authenticate a user by email and password.

    Args:
        session: The async database session.
        email: The user's email address.
        password: The plain-text password.

    Returns:
        The User object if authentication succeeds, None otherwise.
    """
    stmt = select(User).where(User.email == email)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        return None

    if not user.is_active:
        return None

    if not verify_password(password, user.hashed_password):
        return None

    return user
