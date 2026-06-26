"""Seed script to create test users for development and testing."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Add backend to path so we can import app
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.infrastructure.database import get_session_maker, init_db
from app.models.user import User
from app.services.auth_service import hash_password

ADMIN_EMAIL = "admin@fraudguard.com"
ADMIN_PASSWORD = "Admin123!"
ADMIN_NAME = "Admin User"

ANALYST_EMAIL = "analyst@fraudguard.com"
ANALYST_PASSWORD = "Analyst123!"
ANALYST_NAME = "Analyst User"


async def create_user_if_not_exists(
    email: str, password: str, full_name: str, role: str
) -> None:
    """Create a user if they don't already exist."""
    session_maker = get_session_maker()
    if session_maker is None:
        raise RuntimeError("Database session maker is not initialized")
    async with session_maker() as session:
        stmt = select(User).where(User.email == email)
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing is not None:
            print(f"User {email} already exists, skipping.")
            return

        user = User(
            email=email,
            hashed_password=hash_password(password),
            full_name=full_name,
            role=role,
            is_active=True,
        )
        session.add(user)
        await session.commit()
        print(f"Created {role} user: {email}")


async def main() -> None:
    """Run the seed script."""
    await init_db()

    await create_user_if_not_exists(ADMIN_EMAIL, ADMIN_PASSWORD, ADMIN_NAME, "admin")
    await create_user_if_not_exists(
        ANALYST_EMAIL, ANALYST_PASSWORD, ANALYST_NAME, "analyst"
    )

    print("Done seeding users.")


if __name__ == "__main__":
    asyncio.run(main())
