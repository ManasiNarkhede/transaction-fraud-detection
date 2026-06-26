"""Integration tests for the authentication flow."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.auth_service import hash_password


@pytest.fixture
async def test_user(async_session: AsyncSession) -> User:
    """Create and return a test user for authentication tests."""
    user = User(
        email="authuser@example.com",
        hashed_password=hash_password("authpassword"),
        full_name="Auth Test User",
        role="analyst",
        is_active=True,
    )
    async_session.add(user)
    await async_session.commit()
    await async_session.refresh(user)
    return user


@pytest.mark.integration
async def test_auth_flow(
    client: AsyncClient,
    async_session: AsyncSession,
    test_user: User,
) -> None:
    """Test the complete authentication flow: login, access protected endpoint, refresh token."""
    # 1. Login via POST /api/v1/auth/login
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"username": test_user.email, "password": "authpassword"},
    )
    assert login_response.status_code == 200

    login_data = login_response.json()
    assert "access_token" in login_data
    assert "refresh_token" in login_data
    assert login_data["token_type"] == "bearer"

    access_token = login_data["access_token"]
    refresh_token = login_data["refresh_token"]

    # 2. Access protected endpoint /api/v1/auth/me with token
    me_response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert me_response.status_code == 200

    me_data = me_response.json()
    assert me_data["id"] == str(test_user.id)
    assert me_data["email"] == test_user.email
    assert me_data["full_name"] == test_user.full_name
    assert me_data["role"] == test_user.role
    assert me_data["is_active"] is True

    # 3. Refresh token via POST /api/v1/auth/refresh
    refresh_response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_response.status_code == 200

    refresh_data = refresh_response.json()
    assert "access_token" in refresh_data
    assert "refresh_token" in refresh_data
    assert refresh_data["token_type"] == "bearer"

    new_access_token = refresh_data["access_token"]

    # 4. Verify new token works on protected endpoint
    new_me_response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {new_access_token}"},
    )
    assert new_me_response.status_code == 200

    new_me_data = new_me_response.json()
    assert new_me_data["id"] == str(test_user.id)
    assert new_me_data["email"] == test_user.email
