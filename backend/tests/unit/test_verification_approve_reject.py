"""Unit tests for the new verification approve/reject endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.dependencies import get_current_user, get_db_session, require_role
from app.main import create_app
from app.models.user import User


@pytest.fixture
def app() -> FastAPI:
    """Return the FastAPI application instance."""
    return create_app()


@pytest.fixture
async def client(app: FastAPI) -> AsyncClient:
    """Yield an async HTTP client with mocked auth dependencies."""
    mock_session = AsyncMock()
    mock_user = User(
        id=uuid4(),
        email="analyst@example.com",
        hashed_password="hashed",
        full_name="Analyst User",
        role="analyst",
        is_active=True,
    )

    app.dependency_overrides[get_db_session] = lambda: mock_session
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[require_role] = lambda *args, **kwargs: (lambda: mock_user)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# POST /api/v1/verify/{id}/approve
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_approve_verification_success(client: AsyncClient) -> None:
    """approve_verification should return 200 with VERIFIED state."""
    verification_id = uuid4()
    mock_verification = MagicMock()
    mock_verification.id = verification_id
    mock_verification.state = "VERIFIED"
    mock_verification.transaction_id = uuid4()

    with patch("app.routers.verification.VerificationService") as mock_cls:
        mock_svc = MagicMock()
        mock_svc.approve = AsyncMock(return_value=mock_verification)
        mock_cls.return_value = mock_svc

        response = await client.post(f"/api/v1/verify/{verification_id}/approve")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["state"] == "VERIFIED"
    assert data["data"]["message"] == "Verification approved"
    assert data["data"]["verification_id"] == str(verification_id)


@pytest.mark.asyncio
async def test_approve_verification_not_found(client: AsyncClient) -> None:
    """approve_verification should return 400 when verification not found."""
    verification_id = uuid4()

    with patch("app.routers.verification.VerificationService") as mock_cls:
        mock_svc = MagicMock()
        mock_svc.approve = AsyncMock(
            side_effect=ValueError(f"Verification {verification_id} not found")
        )
        mock_cls.return_value = mock_svc

        response = await client.post(f"/api/v1/verify/{verification_id}/approve")

    assert response.status_code == 400
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "BAD_REQUEST"


@pytest.mark.asyncio
async def test_approve_verification_invalid_state(client: AsyncClient) -> None:
    """approve_verification should return 400 on invalid state transition."""
    verification_id = uuid4()

    with patch("app.routers.verification.VerificationService") as mock_cls:
        mock_svc = MagicMock()
        mock_svc.approve = AsyncMock(
            side_effect=ValueError("Invalid state transition: VERIFIED -> VERIFIED")
        )
        mock_cls.return_value = mock_svc

        response = await client.post(f"/api/v1/verify/{verification_id}/approve")

    assert response.status_code == 400
    data = response.json()
    assert data["success"] is False


# ---------------------------------------------------------------------------
# POST /api/v1/verify/{id}/reject
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reject_verification_success(client: AsyncClient) -> None:
    """reject_verification should return 200 with FAILED state."""
    verification_id = uuid4()
    mock_verification = MagicMock()
    mock_verification.id = verification_id
    mock_verification.state = "FAILED"
    mock_verification.transaction_id = uuid4()

    with patch("app.routers.verification.VerificationService") as mock_cls:
        mock_svc = MagicMock()
        mock_svc.reject = AsyncMock(return_value=mock_verification)
        mock_cls.return_value = mock_svc

        response = await client.post(f"/api/v1/verify/{verification_id}/reject")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["state"] == "FAILED"
    assert data["data"]["message"] == "Verification rejected"


@pytest.mark.asyncio
async def test_reject_verification_not_found(client: AsyncClient) -> None:
    """reject_verification should return 400 when verification not found."""
    verification_id = uuid4()

    with patch("app.routers.verification.VerificationService") as mock_cls:
        mock_svc = MagicMock()
        mock_svc.reject = AsyncMock(
            side_effect=ValueError(f"Verification {verification_id} not found")
        )
        mock_cls.return_value = mock_svc

        response = await client.post(f"/api/v1/verify/{verification_id}/reject")

    assert response.status_code == 400
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "BAD_REQUEST"
