"""Authentication API endpoints for login, token refresh, and user info."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_token
from app.dependencies import get_current_user, get_db_session
from app.models.user import User
from app.services.auth_service import (
    authenticate_user,
    create_access_token_for_user,
    create_refresh_token_for_user,
    hash_password,
)
from app.services.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

# Login rate-limit: 10 attempts per 60-second window per IP+username key.
_LOGIN_MAX_REQUESTS = 10
_LOGIN_WINDOW_SECONDS = 60


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class LoginRequest(BaseModel):
    """Schema for login requests."""

    username: str
    password: str


class RegisterRequest(BaseModel):
    """Schema for self-registration requests."""

    email: EmailStr
    phone: str = Field(min_length=5, max_length=32)
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)


class TokenResponse(BaseModel):
    """Schema for token responses."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    """Schema for token refresh requests."""

    refresh_token: str


class UserResponse(BaseModel):
    """Schema for current user info responses."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    full_name: str
    phone: str | None = None
    role: str
    is_active: bool


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/login", response_model=TokenResponse)
async def login(
    request: Request,
    login_request: LoginRequest,
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Authenticate a user and return access and refresh tokens.

    Args:
        request: The incoming HTTP request (used to extract client IP).
        login_request: Login credentials (username/email and password).
        session: The async database session.

    Returns:
        Access and refresh tokens.

    Raises:
        HTTPException: 401 if authentication fails.
        HTTPException: 429 if the login rate limit is exceeded.
    """
    # Rate-limit by IP + normalised username to slow brute-force attempts.
    client_ip = request.client.host if request.client else "unknown"
    rate_key = f"{client_ip}:{login_request.username.lower()}"
    limiter = RateLimiter()
    allowed = await limiter.is_allowed(
        rate_key, _LOGIN_MAX_REQUESTS, _LOGIN_WINDOW_SECONDS
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please try again later.",
        )

    user = await authenticate_user(
        session, login_request.username, login_request.password
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token_for_user(user.id, user.role)
    refresh_token = create_refresh_token_for_user(user.id)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@router.post(
    "/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED
)
async def register(
    register_request: RegisterRequest,
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Self-register a new account and return access and refresh tokens.

    Collects email, phone, and password. Email must be unique. The new
    account is created active with the default role.

    Args:
        register_request: Registration details (email, phone, password).
        session: The async database session.

    Returns:
        Access and refresh tokens for the newly created user.

    Raises:
        HTTPException: 409 if the email is already registered.
    """
    email = register_request.email.lower().strip()

    existing = await session.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    full_name = register_request.full_name or email.split("@", 1)[0]
    user = User(
        email=email,
        hashed_password=hash_password(register_request.password),
        full_name=full_name,
        phone=register_request.phone,
        role="analyst",
        is_active=True,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    access_token = create_access_token_for_user(user.id, user.role)
    refresh = create_refresh_token_for_user(user.id)

    return {
        "access_token": access_token,
        "refresh_token": refresh,
        "token_type": "bearer",
    }


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: RefreshRequest,
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Refresh an access token using a valid refresh token.

    Args:
        request: The refresh token.
        session: The async database session.

    Returns:
        New access and refresh tokens.

    Raises:
        HTTPException: 401 if the refresh token is invalid or expired.
    """
    payload = verify_token(request.refresh_token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_type = payload.get("type")
    if token_type != "refresh":
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

    try:
        user_id = UUID(user_id_str)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID in token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from err

    from sqlalchemy import select as _select

    stmt = _select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token_for_user(user.id, user.role)
    new_refresh_token = create_refresh_token_for_user(user.id)

    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
    }


@router.get("/me", response_model=UserResponse)
async def get_me(
    user: User = Depends(get_current_user),  # noqa: B008
) -> dict[str, Any]:
    """Return information about the currently authenticated user.

    Args:
        user: The current authenticated user.

    Returns:
        User info dict.
    """
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "phone": user.phone,
        "role": user.role,
        "is_active": user.is_active,
    }
