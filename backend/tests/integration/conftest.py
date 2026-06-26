"""Pytest fixtures for integration tests."""

from collections.abc import AsyncGenerator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.infrastructure.database import async_session_maker, init_db
from app.infrastructure.redis_client import init_redis
from app.main import create_app
from app.models.user import User


@pytest.fixture(scope="session")
async def app() -> AsyncGenerator[FastAPI, None]:
    """Yield the FastAPI application instance with initialized infrastructure."""
    await init_db()
    await init_redis()
    yield create_app()


@pytest.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """Yield an async HTTP client for the app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session for integration tests."""
    async with async_session_maker() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create and return a test user."""
    user = User(
        email="test@example.com",
        hashed_password="hashed",
        full_name="Test User",
        role="analyst",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user: User) -> dict[str, str]:
    """Return headers with a valid JWT token for the test user."""
    token = create_access_token(test_user.id, test_user.role)
    return {"Authorization": f"Bearer {token}"}
