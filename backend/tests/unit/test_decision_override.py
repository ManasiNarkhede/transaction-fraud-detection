"""Unit tests for the decision override endpoint."""

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
def admin_user() -> User:
    """Return a mocked admin user."""
    return User(
        id=uuid4(),
        email="admin@example.com",
        hashed_password="hashed",
        full_name="Admin User",
        role="admin",
        is_active=True,
    )


# ---------------------------------------------------------------------------
# POST /api/v1/decisions/{transaction_id}/override
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_override_decision_success(app: FastAPI, admin_user: User) -> None:
    """override_decision should return 200 with old/new decision and audit_id."""
    transaction_id = uuid4()
    audit_id = uuid4()

    mock_transaction = MagicMock()
    mock_transaction.id = transaction_id
    mock_transaction.status = "pending"

    mock_audit = MagicMock()
    mock_audit.id = audit_id

    mock_session_result = MagicMock()
    mock_session_result.scalar_one_or_none.return_value = mock_transaction

    mock_db_session = AsyncMock()
    mock_db_session.execute = AsyncMock(return_value=mock_session_result)
    mock_db_session.commit = AsyncMock()

    app.dependency_overrides[get_db_session] = lambda: mock_db_session
    app.dependency_overrides[get_current_user] = lambda: admin_user
    app.dependency_overrides[require_role] = lambda *args, **kwargs: (
        lambda: admin_user
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch("app.routers.decisions.AuditService") as mock_audit_svc:
            mock_audit_svc.log_override = AsyncMock(return_value=mock_audit)

            response = await client.post(
                f"/api/v1/decisions/{transaction_id}/override",
                json={
                    "new_decision": "approved",
                    "reason": "Manual review passed",
                },
            )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["transaction_id"] == str(transaction_id)
    assert data["new_decision"] == "approved"
    assert data["old_decision"] == "pending"
    assert data["reason"] == "Manual review passed"
    assert data["audit_id"] == str(audit_id)


@pytest.mark.asyncio
async def test_override_decision_transaction_not_found(
    app: FastAPI, admin_user: User
) -> None:
    """override_decision should return 404 when transaction not found."""
    transaction_id = uuid4()

    mock_session_result = MagicMock()
    mock_session_result.scalar_one_or_none.return_value = None

    mock_db_session = AsyncMock()
    mock_db_session.execute = AsyncMock(return_value=mock_session_result)

    app.dependency_overrides[get_db_session] = lambda: mock_db_session
    app.dependency_overrides[get_current_user] = lambda: admin_user
    app.dependency_overrides[require_role] = lambda *args, **kwargs: (
        lambda: admin_user
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            f"/api/v1/decisions/{transaction_id}/override",
            json={
                "new_decision": "approved",
                "reason": "Test override",
            },
        )

    app.dependency_overrides.clear()
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_override_decision_missing_body(app: FastAPI, admin_user: User) -> None:
    """override_decision should return 422 with missing required fields."""
    transaction_id = uuid4()

    mock_db_session = AsyncMock()
    app.dependency_overrides[get_db_session] = lambda: mock_db_session
    app.dependency_overrides[get_current_user] = lambda: admin_user
    app.dependency_overrides[require_role] = lambda *args, **kwargs: (
        lambda: admin_user
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            f"/api/v1/decisions/{transaction_id}/override",
            json={},
        )

    app.dependency_overrides.clear()
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Unit tests for AuditService.log_override
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_audit_service_log_override_calls_log_decision() -> None:
    """log_override should delegate to log_decision with enriched reason."""
    from app.services.audit_service import AuditService

    transaction_id = uuid4()
    analyst_id = uuid4()
    mock_record = MagicMock()
    mock_record.id = uuid4()

    with patch.object(AuditService, "log_decision", new_callable=AsyncMock) as mock_log:
        mock_log.return_value = mock_record

        result = await AuditService.log_override(
            transaction_id=transaction_id,
            old_decision="pending",
            new_decision="approved",
            reason="Looks legit",
            analyst_id=analyst_id,
        )

    assert result is mock_record
    mock_log.assert_awaited_once()
    call_kwargs = mock_log.call_args.kwargs
    assert call_kwargs["transaction_id"] == transaction_id
    assert call_kwargs["decision"] == "approved"
    assert "OVERRIDE" in call_kwargs["reason"]
    assert "pending" in call_kwargs["reason"]
    assert "approved" in call_kwargs["reason"]
    assert str(analyst_id) in call_kwargs["reason"]
