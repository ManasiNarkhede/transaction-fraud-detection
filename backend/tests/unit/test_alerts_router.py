"""Unit tests for the alerts HTTP router."""

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


def _make_mock_alert(status: str = "open", severity: str = "medium") -> MagicMock:
    """Return a MagicMock with Alert-like attributes."""
    alert = MagicMock()
    alert.id = uuid4()
    alert.transaction_id = uuid4()
    alert.user_id = uuid4()
    alert.alert_type = "velocity"
    alert.severity = severity
    alert.status = status
    alert.assigned_to = None
    alert.resolved_at = None
    alert.created_at = datetime(2024, 6, 1, 12, 0, 0, tzinfo=UTC)
    return alert


# ---------------------------------------------------------------------------
# GET /api/v1/alerts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_alerts_success(client: AsyncClient) -> None:
    """list_alerts should return 200 with paginated items."""
    mock_alert = _make_mock_alert()

    with patch("app.routers.alerts.AlertService") as mock_cls:
        mock_cls.list_alerts = AsyncMock(return_value=([mock_alert], 1))

        response = await client.get("/api/v1/alerts")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["status"] == "open"
    assert data["items"][0]["severity"] == "medium"


@pytest.mark.asyncio
async def test_list_alerts_with_filters(client: AsyncClient) -> None:
    """list_alerts should accept status and severity query params."""
    with patch("app.routers.alerts.AlertService") as mock_cls:
        mock_cls.list_alerts = AsyncMock(return_value=([], 0))

        response = await client.get(
            "/api/v1/alerts?status=open&severity=high&limit=10&offset=5"
        )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["limit"] == 10
    assert data["offset"] == 5
    mock_cls.list_alerts.assert_awaited_once()
    call_kwargs = mock_cls.list_alerts.call_args.kwargs
    assert call_kwargs["status"] == "open"
    assert call_kwargs["severity"] == "high"


# ---------------------------------------------------------------------------
# GET /api/v1/alerts/{id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_alert_success(client: AsyncClient) -> None:
    """get_alert should return 200 with alert details."""
    mock_alert = _make_mock_alert()

    with patch("app.routers.alerts.AlertService") as mock_cls:
        mock_cls.get_alert = AsyncMock(return_value=mock_alert)

        response = await client.get(f"/api/v1/alerts/{mock_alert.id}")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "open"
    assert data["alert_type"] == "velocity"


@pytest.mark.asyncio
async def test_get_alert_not_found(client: AsyncClient) -> None:
    """get_alert should return 404 when alert does not exist."""
    with patch("app.routers.alerts.AlertService") as mock_cls:
        mock_cls.get_alert = AsyncMock(return_value=None)

        response = await client.get(f"/api/v1/alerts/{uuid4()}")

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/v1/alerts/{id}/acknowledge
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_acknowledge_alert_success(client: AsyncClient) -> None:
    """acknowledge_alert should return 200 with investigating status."""
    mock_alert = _make_mock_alert(status="investigating")

    with patch("app.routers.alerts.AlertService") as mock_cls:
        mock_cls.acknowledge_alert = AsyncMock(return_value=mock_alert)

        response = await client.post(f"/api/v1/alerts/{uuid4()}/acknowledge")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "investigating"


@pytest.mark.asyncio
async def test_acknowledge_alert_not_found(client: AsyncClient) -> None:
    """acknowledge_alert should return 404 when alert does not exist."""
    with patch("app.routers.alerts.AlertService") as mock_cls:
        mock_cls.acknowledge_alert = AsyncMock(return_value=None)

        response = await client.post(f"/api/v1/alerts/{uuid4()}/acknowledge")

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/v1/alerts/{id}/resolve
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_alert_success(client: AsyncClient) -> None:
    """resolve_alert should return 200 with resolved status."""
    mock_alert = _make_mock_alert(status="resolved")
    mock_alert.resolved_at = datetime(2024, 6, 1, 13, 0, 0, tzinfo=UTC)

    with patch("app.routers.alerts.AlertService") as mock_cls:
        mock_cls.resolve_alert = AsyncMock(return_value=mock_alert)

        response = await client.post(f"/api/v1/alerts/{uuid4()}/resolve")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "resolved"
    assert data["resolved_at"] is not None


@pytest.mark.asyncio
async def test_resolve_alert_not_found(client: AsyncClient) -> None:
    """resolve_alert should return 404 when alert does not exist."""
    with patch("app.routers.alerts.AlertService") as mock_cls:
        mock_cls.resolve_alert = AsyncMock(return_value=None)

        response = await client.post(f"/api/v1/alerts/{uuid4()}/resolve")

    assert response.status_code == 404
