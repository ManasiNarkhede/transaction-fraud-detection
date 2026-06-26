"""Unit tests for the dashboard service, repository FP-rate, and router."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.dependencies import require_analyst
from app.main import create_app
from app.models.user import User
from app.schemas.dashboard import (
    DashboardKPIs,
    DashboardMetricsResponse,
    DecisionLatencyKPI,
    FraudTrendPoint,
)
from app.services.dashboard_service import DashboardService

_OWNER = uuid4()

# ---------------------------------------------------------------------------
# False-positive-rate definition
# ---------------------------------------------------------------------------


def test_false_positive_rate_basic():
    """VERIFIED / (VERIFIED + FAILED + EXPIRED)."""
    rate = DashboardService._false_positive_rate(
        {"VERIFIED": 3, "FAILED": 1, "EXPIRED": 0}
    )
    assert rate == 0.75


def test_false_positive_rate_no_terminal_returns_zero():
    """No terminal verifications -> 0.0 (no division by zero)."""
    rate = DashboardService._false_positive_rate(
        {"VERIFIED": 0, "FAILED": 0, "EXPIRED": 0}
    )
    assert rate == 0.0


# ---------------------------------------------------------------------------
# Block-success-rate definition
# ---------------------------------------------------------------------------


def test_block_success_rate_basic():
    """blocked / total_decisions."""
    rate = DashboardService._block_success_rate(blocked=20, total_decisions=100)
    assert rate == 0.2


def test_block_success_rate_zero_decisions():
    """No decisions -> 0.0 (no division by zero)."""
    rate = DashboardService._block_success_rate(blocked=0, total_decisions=0)
    assert rate == 0.0


def test_block_success_rate_all_blocked():
    """All decisions blocked -> 1.0."""
    rate = DashboardService._block_success_rate(blocked=50, total_decisions=50)
    assert rate == 1.0


# ---------------------------------------------------------------------------
# Service aggregation (mocked repository)
# ---------------------------------------------------------------------------


def _make_mock_repo(
    *,
    total: int = 100,
    blocked: int = 12,
    high_risk: int = 5,
    verif: dict | None = None,
    trends: list | None = None,
    total_decisions: int = 80,
    latency: dict | None = None,
) -> MagicMock:
    """Build a fully-mocked DashboardRepository."""
    mock_repo = MagicMock()
    mock_repo.count_transactions = AsyncMock(return_value=total)
    mock_repo.count_blocked_transactions = AsyncMock(return_value=blocked)
    mock_repo.count_high_risk_users = AsyncMock(return_value=high_risk)
    mock_repo.verification_terminal_counts = AsyncMock(
        return_value=verif or {"VERIFIED": 2, "FAILED": 2, "EXPIRED": 0}
    )
    mock_repo.fraud_trends = AsyncMock(
        return_value=trends
        or [{"date": date(2026, 6, 23), "total": total, "blocked": blocked}]
    )
    mock_repo.count_total_decisions = AsyncMock(return_value=total_decisions)
    mock_repo.latency_stats = AsyncMock(
        return_value=latency or {"avg_ms": 42.5, "p95_ms": 120.0}
    )
    return mock_repo


def _patch_session(mock_repo: MagicMock):
    """Context managers that patch the DB session and repository."""
    fake_session = AsyncMock()
    fake_maker = MagicMock()
    fake_maker.return_value.__aenter__ = AsyncMock(return_value=fake_session)
    fake_maker.return_value.__aexit__ = AsyncMock(return_value=False)
    return (
        patch(
            "app.services.dashboard_service.get_session_maker",
            return_value=fake_maker,
        ),
        patch(
            "app.services.dashboard_service.DashboardRepository",
            return_value=mock_repo,
        ),
    )


@pytest.mark.asyncio
async def test_get_metrics_aggregates_repository(monkeypatch):
    """Service composes repository results into the response schema."""
    mock_repo = _make_mock_repo()

    with _patch_session(mock_repo)[0], _patch_session(mock_repo)[1]:
        pass  # need both patches simultaneously

    ctx1, ctx2 = _patch_session(mock_repo)
    with ctx1, ctx2:
        service = DashboardService()
        result = await service.get_metrics(owner_id=_OWNER)

    assert isinstance(result, DashboardMetricsResponse)
    assert result.total_transactions == 100
    assert result.blocked_transactions == 12
    assert result.high_risk_users == 5
    assert result.false_positive_rate == 0.5
    assert result.fraud_trends == [
        FraudTrendPoint(date=date(2026, 6, 23), total=100, blocked=12)
    ]
    # KPI assertions
    assert isinstance(result.kpis, DashboardKPIs)
    assert result.kpis.block_success_rate == round(12 / 80, 4)
    assert result.kpis.verification_success_rate == 0.5
    assert isinstance(result.kpis.decision_latency, DecisionLatencyKPI)
    assert result.kpis.decision_latency.avg_ms == 42.5
    assert result.kpis.decision_latency.p95_ms == 120.0
    assert result.kpis.fraud_detection_accuracy is None
    assert result.kpis.false_negative_rate is None
    assert "labeled" in result.kpis.fraud_detection_accuracy_note
    assert "labeled" in result.kpis.false_negative_rate_note


@pytest.mark.asyncio
async def test_get_metrics_latency_null_when_no_data():
    """Latency KPI fields are None when no latency rows exist yet."""
    mock_repo = _make_mock_repo(latency={"avg_ms": None, "p95_ms": None})
    ctx1, ctx2 = _patch_session(mock_repo)
    with ctx1, ctx2:
        result = await DashboardService().get_metrics(owner_id=_OWNER)

    assert result.kpis.decision_latency.avg_ms is None
    assert result.kpis.decision_latency.p95_ms is None


@pytest.mark.asyncio
async def test_get_metrics_block_success_rate_zero_decisions():
    """block_success_rate is 0.0 when no decisions exist."""
    mock_repo = _make_mock_repo(blocked=0, total_decisions=0)
    ctx1, ctx2 = _patch_session(mock_repo)
    with ctx1, ctx2:
        result = await DashboardService().get_metrics(owner_id=_OWNER)

    assert result.kpis.block_success_rate == 0.0


@pytest.mark.asyncio
async def test_get_metrics_raises_without_db():
    """Service raises if the session maker is not initialized."""
    with (
        patch("app.services.dashboard_service.get_session_maker", return_value=None),
        pytest.raises(RuntimeError),
    ):
        await DashboardService().get_metrics(owner_id=_OWNER)


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


@pytest.fixture
def app() -> FastAPI:
    return create_app()


@pytest.fixture
async def client(app: FastAPI) -> AsyncClient:
    mock_user = User(
        id=uuid4(),
        email="analyst@example.com",
        hashed_password="hashed",
        full_name="Analyst User",
        role="analyst",
        is_active=True,
    )
    app.dependency_overrides[require_analyst] = lambda: mock_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_dashboard_metrics_endpoint(client: AsyncClient) -> None:
    """GET /dashboard/metrics returns the service payload including kpis."""
    payload = DashboardMetricsResponse(
        total_transactions=100,
        blocked_transactions=12,
        high_risk_users=5,
        false_positive_rate=0.25,
        fraud_trends=[FraudTrendPoint(date=date(2026, 6, 23), total=100, blocked=12)],
        kpis=DashboardKPIs(
            block_success_rate=0.15,
            verification_success_rate=0.25,
            decision_latency=DecisionLatencyKPI(avg_ms=35.0, p95_ms=110.0),
            fraud_detection_accuracy=None,
            fraud_detection_accuracy_note=(
                "requires labeled outcomes — no confirmed-fraud feedback loop exists yet"
            ),
            false_negative_rate=None,
            false_negative_rate_note=(
                "requires labeled outcomes — no confirmed-fraud feedback loop exists yet"
            ),
        ),
    )

    with patch("app.routers.dashboard.DashboardService") as mock_cls:
        mock_service = MagicMock()
        mock_service.get_metrics = AsyncMock(return_value=payload)
        mock_cls.return_value = mock_service
        response = await client.get("/api/v1/dashboard/metrics")

    assert response.status_code == 200
    data = response.json()
    assert data["total_transactions"] == 100
    assert data["blocked_transactions"] == 12
    assert data["high_risk_users"] == 5
    assert data["false_positive_rate"] == 0.25
    assert data["fraud_trends"][0]["blocked"] == 12
    # KPIs are present in the JSON response
    assert "kpis" in data
    assert data["kpis"]["block_success_rate"] == 0.15
    assert data["kpis"]["verification_success_rate"] == 0.25
    assert data["kpis"]["decision_latency"]["avg_ms"] == 35.0
    assert data["kpis"]["decision_latency"]["p95_ms"] == 110.0
    assert data["kpis"]["fraud_detection_accuracy"] is None
    assert data["kpis"]["false_negative_rate"] is None
    assert "labeled" in data["kpis"]["fraud_detection_accuracy_note"]
