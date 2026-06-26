"""Integration tests for the authentication API endpoints."""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient

from app.services.auth_service import hash_password


@pytest.fixture
async def seeded_user(async_session: Any) -> dict[str, Any]:
    """Create a test user in the database and return user data."""
    from app.models.user import User

    user = User(
        email="testuser@example.com",
        hashed_password=hash_password("TestPass123!"),
        full_name="Test User",
        role="analyst",
        is_active=True,
    )
    async_session.add(user)
    await async_session.commit()
    await async_session.refresh(user)
    return {
        "id": user.id,
        "email": user.email,
        "password": "TestPass123!",
        "role": user.role,
    }


@pytest.fixture
async def admin_user(async_session: Any) -> dict[str, Any]:
    """Create an admin test user in the database."""
    from app.models.user import User

    user = User(
        email="adminuser@example.com",
        hashed_password=hash_password("AdminPass123!"),
        full_name="Admin User",
        role="admin",
        is_active=True,
    )
    async_session.add(user)
    await async_session.commit()
    await async_session.refresh(user)
    return {
        "id": user.id,
        "email": user.email,
        "password": "AdminPass123!",
        "role": user.role,
    }


@pytest.mark.integration
async def test_login_success(client: AsyncClient, seeded_user: dict[str, Any]) -> None:
    """POST /auth/login should return tokens for valid credentials."""
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "username": seeded_user["email"],
            "password": seeded_user["password"],
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert isinstance(data["access_token"], str)
    assert len(data["access_token"]) > 0


@pytest.mark.integration
async def test_login_invalid_password(
    client: AsyncClient, seeded_user: dict[str, Any]
) -> None:
    """POST /auth/login should return 401 for invalid password."""
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "username": seeded_user["email"],
            "password": "wrongpassword",
        },
    )
    assert response.status_code == 401
    data = response.json()
    assert "detail" in data


@pytest.mark.integration
async def test_login_user_not_found(client: AsyncClient) -> None:
    """POST /auth/login should return 401 for non-existent user."""
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "username": "nonexistent@example.com",
            "password": "somepassword",
        },
    )
    assert response.status_code == 401


@pytest.mark.integration
async def test_refresh_token_success(
    client: AsyncClient, seeded_user: dict[str, Any]
) -> None:
    """POST /auth/refresh should return new tokens for valid refresh token."""
    # First login to get tokens
    login_response = await client.post(
        "/api/v1/auth/login",
        json={
            "username": seeded_user["email"],
            "password": seeded_user["password"],
        },
    )
    login_data = login_response.json()
    refresh_token = login_data["refresh_token"]

    # Now refresh
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.integration
async def test_refresh_token_invalid(client: AsyncClient) -> None:
    """POST /auth/refresh should return 401 for invalid refresh token."""
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "invalid.token.here"},
    )
    assert response.status_code == 401


@pytest.mark.integration
async def test_get_me_success(client: AsyncClient, seeded_user: dict[str, Any]) -> None:
    """GET /auth/me should return current user info with valid token."""
    # Login first
    login_response = await client.post(
        "/api/v1/auth/login",
        json={
            "username": seeded_user["email"],
            "password": seeded_user["password"],
        },
    )
    login_data = login_response.json()
    access_token = login_data["access_token"]

    # Get me
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == seeded_user["email"]
    assert data["full_name"] == "Test User"
    assert data["role"] == "analyst"
    assert data["is_active"] is True
    assert "id" in data


@pytest.mark.integration
async def test_get_me_no_token(client: AsyncClient) -> None:
    """GET /auth/me should return 401 without token."""
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


@pytest.mark.integration
async def test_get_me_invalid_token(client: AsyncClient) -> None:
    """GET /auth/me should return 401 with invalid token."""
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer invalid.token.here"},
    )
    assert response.status_code == 401


@pytest.mark.integration
async def test_protected_route_rules_post_requires_admin(
    client: AsyncClient, seeded_user: dict[str, Any], admin_user: dict[str, Any]
) -> None:
    """POST /rules should require admin role."""
    # Try as analyst
    login_response = await client.post(
        "/api/v1/auth/login",
        json={
            "username": seeded_user["email"],
            "password": seeded_user["password"],
        },
    )
    analyst_token = login_response.json()["access_token"]

    response = await client.post(
        "/api/v1/rules",
        json={
            "name": "Test Rule",
            "description": "A test rule",
            "rule_type": "velocity",
            "conditions": {"max_amount": 1000},
            "action": "flag",
            "priority": 1,
        },
        headers={"Authorization": f"Bearer {analyst_token}"},
    )
    assert response.status_code == 403

    # Try as admin
    admin_login = await client.post(
        "/api/v1/auth/login",
        json={
            "username": admin_user["email"],
            "password": admin_user["password"],
        },
    )
    admin_token = admin_login.json()["access_token"]

    response = await client.post(
        "/api/v1/rules",
        json={
            "name": "Test Rule",
            "description": "A test rule",
            "rule_type": "velocity",
            "conditions": {"max_amount": 1000},
            "action": "flag",
            "priority": 1,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    # Should be 201 or 422 (validation error), but not 403
    assert response.status_code != 403


@pytest.mark.integration
async def test_protected_route_audit_requires_analyst(
    client: AsyncClient, seeded_user: dict[str, Any]
) -> None:
    """GET /audit should require analyst or admin role."""
    # Without token
    response = await client.get("/api/v1/audit")
    assert response.status_code == 401

    # With analyst token
    login_response = await client.post(
        "/api/v1/auth/login",
        json={
            "username": seeded_user["email"],
            "password": seeded_user["password"],
        },
    )
    analyst_token = login_response.json()["access_token"]

    response = await client.get(
        "/api/v1/audit",
        headers={"Authorization": f"Bearer {analyst_token}"},
    )
    # Should not be 401 or 403
    assert response.status_code not in (401, 403)


@pytest.mark.integration
async def test_protected_route_decisions_requires_analyst(
    client: AsyncClient, seeded_user: dict[str, Any]
) -> None:
    """GET /decisions should require analyst or admin role."""
    # Without token
    response = await client.get(
        "/api/v1/decisions/123e4567-e89b-12d3-a456-426614174000"
    )
    assert response.status_code == 401

    # With analyst token
    login_response = await client.post(
        "/api/v1/auth/login",
        json={
            "username": seeded_user["email"],
            "password": seeded_user["password"],
        },
    )
    analyst_token = login_response.json()["access_token"]

    response = await client.get(
        "/api/v1/decisions/123e4567-e89b-12d3-a456-426614174000",
        headers={"Authorization": f"Bearer {analyst_token}"},
    )
    # Should not be 401 or 403 (404 is fine since transaction doesn't exist)
    assert response.status_code not in (401, 403)
