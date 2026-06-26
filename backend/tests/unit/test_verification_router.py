"""Unit tests for the verification router."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.dependencies import get_current_user, get_db_session, require_role
from app.main import create_app
from app.models.user import User

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app() -> FastAPI:
    """Return the FastAPI application instance."""
    return create_app()


@pytest.fixture
async def client(app: FastAPI) -> AsyncClient:
    """Yield an async HTTP client for the app with mocked dependencies."""
    mock_session = AsyncMock()
    mock_user = User(
        id=uuid4(),
        email="test@example.com",
        hashed_password="hashed",
        full_name="Test User",
        role="admin",
        is_active=True,
    )

    app.dependency_overrides[get_db_session] = lambda: mock_session
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[require_role] = lambda: mock_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
def mock_admin_user() -> User:
    """Return a mocked admin user."""
    user = User(
        id=uuid4(),
        email="admin@example.com",
        hashed_password="hashed",
        full_name="Admin User",
        role="admin",
        is_active=True,
    )
    return user


@pytest.fixture
def mock_analyst_user() -> User:
    """Return a mocked analyst user."""
    user = User(
        id=uuid4(),
        email="analyst@example.com",
        hashed_password="hashed",
        full_name="Analyst User",
        role="analyst",
        is_active=True,
    )
    return user


# ---------------------------------------------------------------------------
# POST /api/v1/verify/send
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_verification_success(
    client: AsyncClient,
    mock_analyst_user: User,
) -> None:
    """send_verification should return 200 with verification details."""
    verification_id = uuid4()
    mock_verification = MagicMock()
    mock_verification.id = verification_id
    mock_verification.state = "PENDING"
    mock_verification.otp_expires_at = datetime(2024, 1, 1, 12, 10, 0, tzinfo=UTC)

    with patch("app.routers.verification.VerificationService") as mock_service_class:
        mock_service = MagicMock()
        mock_service.create_verification = AsyncMock(return_value=mock_verification)
        mock_service_class.return_value = mock_service

        response = await client.post(
            "/api/v1/verify/send",
            json={
                "transaction_id": str(uuid4()),
                "user_id": str(uuid4()),
                "channel": "sms",
                "contact_info": "+1234567890",
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["verification_id"] == str(verification_id)
    assert data["data"]["state"] == "PENDING"


@pytest.mark.asyncio
async def test_send_verification_bad_request(
    client: AsyncClient,
    mock_analyst_user: User,
) -> None:
    """send_verification should return 400 on ValueError."""
    with patch("app.routers.verification.VerificationService") as mock_service_class:
        mock_service = MagicMock()
        mock_service.create_verification = AsyncMock(
            side_effect=ValueError("Invalid channel")
        )
        mock_service_class.return_value = mock_service

        response = await client.post(
            "/api/v1/verify/send",
            json={
                "transaction_id": str(uuid4()),
                "user_id": str(uuid4()),
                "channel": "invalid",
                "contact_info": "+1234567890",
            },
        )

    assert response.status_code == 400
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "BAD_REQUEST"


# ---------------------------------------------------------------------------
# POST /api/v1/verify/otp
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_submit_otp_success(
    client: AsyncClient,
    mock_analyst_user: User,
) -> None:
    """submit_otp should return 200 with verified state."""
    with patch("app.routers.verification.VerificationService") as mock_service_class:
        mock_service = MagicMock()
        mock_service.validate_otp = AsyncMock(
            return_value={
                "success": True,
                "state": "VERIFIED",
                "message": "OTP verified successfully",
            }
        )
        mock_service_class.return_value = mock_service

        response = await client.post(
            "/api/v1/verify/otp",
            json={
                "verification_id": str(uuid4()),
                "otp": "123456",
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["state"] == "VERIFIED"


@pytest.mark.asyncio
async def test_submit_otp_bad_request(
    client: AsyncClient,
    mock_analyst_user: User,
) -> None:
    """submit_otp should return 400 on ValueError."""
    with patch("app.routers.verification.VerificationService") as mock_service_class:
        mock_service = MagicMock()
        mock_service.validate_otp = AsyncMock(
            side_effect=ValueError("Invalid OTP format")
        )
        mock_service_class.return_value = mock_service

        response = await client.post(
            "/api/v1/verify/otp",
            json={
                "verification_id": str(uuid4()),
                "otp": "bad",
            },
        )

    assert response.status_code == 400
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "BAD_REQUEST"


# ---------------------------------------------------------------------------
# GET /api/v1/verify/{verification_id}/status
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_verification_status_success(
    client: AsyncClient,
    mock_analyst_user: User,
) -> None:
    """get_verification_status should return 200 with status details."""
    verification_id = uuid4()
    expires_at = datetime(2024, 1, 1, 12, 10, 0, tzinfo=UTC)

    with patch("app.routers.verification.VerificationService") as mock_service_class:
        mock_service = MagicMock()
        mock_service.get_status = AsyncMock(
            return_value={
                "found": True,
                "state": "PENDING",
                "attempts": 1,
                "max_attempts": 3,
                "expires_at": expires_at.isoformat(),
            }
        )
        mock_service_class.return_value = mock_service

        response = await client.get(
            f"/api/v1/verify/{verification_id}/status",
        )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["state"] == "PENDING"
    assert data["data"]["attempts"] == 1
    assert data["data"]["max_attempts"] == 3


# ---------------------------------------------------------------------------
# POST /api/v1/verify/{verification_id}/escalate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_escalate_verification_success(
    client: AsyncClient,
    mock_admin_user: User,
) -> None:
    """escalate_verification should return 200 with updated state."""
    verification_id = uuid4()
    mock_verification = MagicMock()
    mock_verification.state = "FAILED"

    with patch("app.routers.verification.VerificationService") as mock_service_class:
        mock_service = MagicMock()
        mock_service.escalate = AsyncMock(return_value=mock_verification)
        mock_service_class.return_value = mock_service

        response = await client.post(
            f"/api/v1/verify/{verification_id}/escalate",
        )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["state"] == "FAILED"
    assert data["data"]["message"] == "Verification escalated successfully"


@pytest.mark.asyncio
async def test_escalate_verification_not_found(
    client: AsyncClient,
    mock_admin_user: User,
) -> None:
    """escalate_verification should return 404 when verification not found."""
    verification_id = uuid4()

    with patch("app.routers.verification.VerificationService") as mock_service_class:
        mock_service = MagicMock()
        mock_service.escalate = AsyncMock(return_value=None)
        mock_service_class.return_value = mock_service

        response = await client.post(
            f"/api/v1/verify/{verification_id}/escalate",
        )

    assert response.status_code == 404
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_escalate_verification_bad_request(
    client: AsyncClient,
    mock_admin_user: User,
) -> None:
    """escalate_verification should return 400 on ValueError."""
    verification_id = uuid4()

    with patch("app.routers.verification.VerificationService") as mock_service_class:
        mock_service = MagicMock()
        mock_service.escalate = AsyncMock(side_effect=ValueError("Already resolved"))
        mock_service_class.return_value = mock_service

        response = await client.post(
            f"/api/v1/verify/{verification_id}/escalate",
        )

    assert response.status_code == 400
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "BAD_REQUEST"


# ---------------------------------------------------------------------------
# GET /api/v1/verify/queue
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_verification_queue_success(
    client: AsyncClient,
    mock_admin_user: User,
) -> None:
    """list_verification_queue should return 200 with paginated items."""
    mock_item = MagicMock()
    mock_item.id = uuid4()
    mock_item.transaction_id = uuid4()
    mock_item.user_id = uuid4()
    mock_item.state = "PENDING"
    mock_item.channel = "sms"
    mock_item.contact_info = "+1234567890"
    mock_item.attempts = 0
    mock_item.max_attempts = 3
    mock_item.created_at = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
    mock_item.otp_expires_at = datetime(2024, 1, 1, 12, 10, 0, tzinfo=UTC)

    with patch("app.routers.verification.VerificationService") as mock_service_class:
        mock_service = MagicMock()
        mock_service.get_queue = AsyncMock(
            return_value=[
                {
                    "verification": mock_item,
                    "amount": 500.00,
                    "currency": "USD",
                    "transaction_status": "verify",
                    "risk_score": 55,
                }
            ]
        )
        mock_service_class.return_value = mock_service

        response = await client.get("/api/v1/verify/queue")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["total"] == 1
    assert len(data["data"]["items"]) == 1
    assert data["data"]["items"][0]["state"] == "PENDING"


@pytest.mark.asyncio
async def test_list_verification_queue_with_filters(
    client: AsyncClient,
    mock_admin_user: User,
) -> None:
    """list_verification_queue should accept state, limit, and offset filters."""
    with patch("app.routers.verification.VerificationService") as mock_service_class:
        mock_service = MagicMock()
        mock_service.get_queue = AsyncMock(return_value=[])
        mock_service_class.return_value = mock_service

        response = await client.get(
            "/api/v1/verify/queue?state=VERIFIED&limit=10&offset=5"
        )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["total"] == 0
    assert data["data"]["limit"] == 10
    assert data["data"]["offset"] == 5
