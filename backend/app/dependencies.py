"""Dependency injection container with get_db_session() and get_redis_client() async generators."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Callable
from typing import Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_token
from app.infrastructure.database import get_session_maker
from app.infrastructure.redis_client import get_redis
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session with proper cleanup."""
    session_maker = get_session_maker()
    if session_maker is None:
        raise RuntimeError("Database session maker is not initialized")

    async with session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_redis_client(request: Request) -> AsyncGenerator[Redis, None]:
    """Yield the Redis client from application state with proper cleanup."""
    redis_client = get_redis()
    if redis_client is None:
        raise RuntimeError("Redis client is not initialized")
    try:
        yield redis_client
    finally:
        pass


async def get_current_user(
    token: str | None = Depends(oauth2_scheme),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> User:
    """Extract and validate the current user from a JWT token.

    Args:
        token: The JWT access token from the Authorization header.
        session: The async database session.

    Returns:
        The authenticated User object.

    Raises:
        HTTPException: 401 if token is missing, invalid, or user not found/inactive.
    """
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = verify_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_type = payload.get("type")
    if token_type != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id_str = payload.get("sub")
    if user_id_str is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    from uuid import UUID

    try:
        user_id = UUID(user_id_str)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID in token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from err

    from sqlalchemy import select

    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User is inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def require_analyst(
    user: User = Depends(get_current_user),  # noqa: B008
) -> User:
    """Any authenticated user (no role hierarchy; data scoped by owner_id)."""
    return user


async def require_admin(
    user: User = Depends(get_current_user),  # noqa: B008
) -> User:
    """Any authenticated user (no role hierarchy; data scoped by owner_id)."""
    return user


require_authenticated = get_current_user


def require_role(roles: list[str]) -> Callable[..., Any]:
    """Legacy factory — roles are not enforced; data is scoped by owner_id."""

    async def role_checker(
        user: User = Depends(get_current_user),  # noqa: B008
    ) -> User:
        return user

    return role_checker
