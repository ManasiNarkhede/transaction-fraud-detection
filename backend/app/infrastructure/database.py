"""Async PostgreSQL database setup."""

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from app.config import settings

engine: AsyncEngine | None = None
async_session_maker: async_sessionmaker | None = None
logger = logging.getLogger(__name__)


def get_session_maker() -> async_sessionmaker | None:
    """Return the live session maker, or None if not yet initialized.

    Always read the module global at call time. Modules must call this at
    use-time rather than binding ``async_session_maker`` at import time,
    otherwise they capture the initial ``None`` before ``init_db()`` runs.
    """
    return async_session_maker


async def init_db() -> None:
    """Initialize database engine and verify connectivity."""
    global engine, async_session_maker
    engine = create_async_engine(
        settings.database_url,
        pool_size=settings.db_pool_size,
        echo=settings.debug,
    )
    async_session_maker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("database_connected")
    except Exception as exc:
        logger.warning("database_connection_failed", extra={"error": str(exc)})
        # Phase 1: Do not crash startup. Tables will be added in Phase 2.


async def close_db() -> None:
    """Close database engine."""
    global engine, async_session_maker
    if engine:
        await engine.dispose()
        engine = None
    async_session_maker = None
