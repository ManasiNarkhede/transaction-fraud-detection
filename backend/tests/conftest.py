"""Pytest fixtures with app and client."""

from collections.abc import AsyncGenerator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database import async_session_maker, init_db
from app.infrastructure.redis_client import init_redis
from app.main import create_app


@pytest.fixture
def db_available() -> None:
    """Skip integration tests if database is not available."""
    import asyncio

    async def _check() -> bool:
        await init_db()
        from app.infrastructure.database import async_session_maker

        return async_session_maker is not None

    try:
        available = asyncio.get_event_loop().run_until_complete(_check())
    except Exception:
        available = False

    if not available:
        pytest.skip("Database not available")


@pytest.fixture
async def app(db_available: None) -> AsyncGenerator:
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
async def async_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session for integration tests."""
    if async_session_maker is None:
        pytest.skip("Database not initialized")

    async with async_session_maker() as session:
        yield session
        await session.rollback()
