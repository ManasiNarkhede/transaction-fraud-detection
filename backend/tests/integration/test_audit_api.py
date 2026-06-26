"""Integration tests for the audit API endpoints."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.models.feature_vector import FeatureVector
from app.services.decision_engine import DecisionEngine

# ---------------------------------------------------------------------------
# Audit API endpoint tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_audit_list_endpoint_returns_records(client: AsyncClient) -> None:
    """GET /audit should return paginated audit records."""
    mock_record = MagicMock()
    mock_record.id = uuid4()
    mock_record.transaction_id = uuid4()
    mock_record.decision = "block"
    mock_record.score = 80
    mock_record.reason = "High risk"
    mock_record.features = {"amount_zscore": 2.5}
    mock_record.rules_triggered = ["high_amount"]
    mock_record.model_version = "v1.0"
    mock_record.hash = "a" * 64
    mock_record.previous_hash = None
    mock_record.created_at = datetime(2024, 1, 1, 12, 0, 0)

    with patch(
        "app.routers.audit.AuditService.query_audits",
        return_value=([mock_record], 1),
    ):
        response = await client.get("/api/v1/audit?limit=10&offset=0")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["limit"] == 10
    assert data["offset"] == 0
    assert len(data["items"]) == 1
    assert data["items"][0]["decision"] == "block"


@pytest.mark.integration
async def test_audit_list_with_filters(client: AsyncClient) -> None:
    """GET /audit should support decision and date filters."""
    with patch(
        "app.routers.audit.AuditService.query_audits",
        return_value=([], 0),
    ) as mock_query:
        response = await client.get(
            "/api/v1/audit?decision=block&start_date=2024-01-01&end_date=2024-01-31"
        )

    assert response.status_code == 200
    mock_query.assert_awaited_once_with(
        decision="block",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 31),
        limit=50,
        offset=0,
    )


@pytest.mark.integration
async def test_audit_by_transaction_found(client: AsyncClient) -> None:
    """GET /audit/{transaction_id} should return the audit record."""
    tx_id = uuid4()
    mock_record = MagicMock()
    mock_record.id = uuid4()
    mock_record.transaction_id = tx_id
    mock_record.decision = "approve"
    mock_record.score = 30
    mock_record.reason = "No risk"
    mock_record.features = {"amount_zscore": 0.5}
    mock_record.rules_triggered = []
    mock_record.model_version = None
    mock_record.hash = "a" * 64
    mock_record.previous_hash = None
    mock_record.created_at = datetime(2024, 1, 1, 12, 0, 0)

    with patch(
        "app.routers.audit.AuditService.get_audit_by_transaction",
        return_value=mock_record,
    ):
        response = await client.get(f"/api/v1/audit/{tx_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["transaction_id"] == str(tx_id)
    assert data["decision"] == "approve"


@pytest.mark.integration
async def test_audit_by_transaction_not_found(client: AsyncClient) -> None:
    """GET /audit/{transaction_id} should return 404 when not found."""
    tx_id = uuid4()

    with patch(
        "app.routers.audit.AuditService.get_audit_by_transaction",
        return_value=None,
    ):
        response = await client.get(f"/api/v1/audit/{tx_id}")

    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "NOT_FOUND"


@pytest.mark.integration
async def test_audit_integrity_endpoint(client: AsyncClient) -> None:
    """GET /audit/integrity should return integrity check results."""
    with patch(
        "app.routers.audit.AuditService.verify_integrity",
        return_value={
            "valid": True,
            "total_records": 10,
            "first_broken_id": None,
            "message": "All 10 records verified successfully",
        },
    ):
        response = await client.get("/api/v1/audit/integrity")

    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True
    assert data["total_records"] == 10
    assert data["first_broken_id"] is None


# ---------------------------------------------------------------------------
# Decision -> Audit integration test
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_decision_evaluation_triggers_audit_log(client: AsyncClient) -> None:
    """POST /decisions/evaluate should trigger an audit log via fire-and-forget."""
    tx_id = uuid4()
    features = FeatureVector(
        amount=Decimal("100.00"),
        amount_zscore=0.5,
        time_since_last_tx=24.0,
        tx_count_1h=0,
        tx_count_24h=1,
        tx_count_7d=5,
        avg_amount_30d=Decimal("50.00"),
        max_amount_30d=Decimal("200.00"),
        unique_merchants_24h=1,
        unique_countries_24h=1,
        device_trust_score=0.8,
        is_new_device=False,
        hour_of_day=14,
        day_of_week=2,
        is_weekend=False,
    )
    rule_result = {
        "score_adjustment": 21,
        "rules_triggered": [],
        "actions": [],
        "decision": "approve",
    }

    with (
        patch(
            "app.services.decision_engine.AuditService.log_decision",
            new_callable=AsyncMock,
        ) as mock_log,
        patch("app.services.decision_engine.asyncio.create_task") as mock_create_task,
        patch.object(
            DecisionEngine, "_update_transaction_status", new_callable=AsyncMock
        ),
    ):
        response = await client.post(
            "/api/v1/decisions/evaluate",
            json={
                "transaction_id": str(tx_id),
                "features": features.model_dump(mode="json"),
                "rule_result": rule_result,
            },
        )

    assert response.status_code == 200
    # Verify that create_task was called (fire-and-forget audit logging)
    mock_create_task.assert_called_once()
    # Verify that the audit log function was called to produce the coroutine
    mock_log.assert_called_once()
