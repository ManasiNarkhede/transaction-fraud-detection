"""Unit tests for the transactions ingestion router."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.dependencies import get_db_session, require_analyst
from app.main import create_app
from app.models.user import User
from app.schemas.transaction import TransactionDecisionResponse


@pytest.fixture
def app() -> FastAPI:
    """Return the FastAPI application instance."""
    return create_app()


@pytest.fixture
async def client(app: FastAPI) -> AsyncClient:
    """Yield an async HTTP client with the analyst dependency overridden."""
    mock_user = User(
        id=uuid4(),
        email="analyst@example.com",
        hashed_password="hashed",
        full_name="Analyst User",
        role="analyst",
        is_active=True,
    )
    app.dependency_overrides[require_analyst] = lambda: mock_user

    async def _mock_session():
        session = AsyncMock()
        yield session

    app.dependency_overrides[get_db_session] = _mock_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


def _valid_payload() -> dict:
    return {
        "user_id": str(uuid4()),
        "amount": "120.50",
        "currency": "USD",
        "merchant_id": "merchant-9",
        "location": "US",
        "device_id": "device-xyz",
        "ip_address": "10.0.0.1",
        "payment_method": "card",
    }


@pytest.mark.asyncio
async def test_ingest_transaction_success(client: AsyncClient) -> None:
    """POST /transactions returns 201 with the decision payload."""
    transaction_id = uuid4()
    response_model = TransactionDecisionResponse(
        transaction_id=transaction_id,
        decision="block",
        score=85,
        reason="amount_anomaly + new_device",
        rules_triggered=["amount_anomaly", "new_device"],
        requires_verification=False,
    )

    with patch("app.routers.transactions.TransactionIngestService") as mock_service_cls:
        mock_service = MagicMock()
        mock_service.ingest = AsyncMock(return_value=response_model)
        mock_service_cls.return_value = mock_service

        response = await client.post("/api/v1/transactions", json=_valid_payload())

    assert response.status_code == 201
    data = response.json()
    assert data["transaction_id"] == str(transaction_id)
    assert data["decision"] == "block"
    assert data["score"] == 85
    assert data["rules_triggered"] == ["amount_anomaly", "new_device"]


@pytest.mark.asyncio
async def test_ingest_transaction_verify_sets_flag(client: AsyncClient) -> None:
    """A verify decision surfaces requires_verification=True."""
    response_model = TransactionDecisionResponse(
        transaction_id=uuid4(),
        decision="verify",
        score=55,
        reason="velocity",
        rules_triggered=["velocity"],
        requires_verification=True,
    )

    with patch("app.routers.transactions.TransactionIngestService") as mock_service_cls:
        mock_service = MagicMock()
        mock_service.ingest = AsyncMock(return_value=response_model)
        mock_service_cls.return_value = mock_service

        response = await client.post("/api/v1/transactions", json=_valid_payload())

    assert response.status_code == 201
    assert response.json()["requires_verification"] is True


@pytest.mark.asyncio
async def test_ingest_transaction_rejects_invalid_amount(client: AsyncClient) -> None:
    """Non-positive amounts fail validation with 422."""
    payload = _valid_payload()
    payload["amount"] = "0"

    response = await client.post("/api/v1/transactions", json=payload)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_ingest_transaction_requires_user_id(client: AsyncClient) -> None:
    """Missing user_id fails validation with 422."""
    payload = _valid_payload()
    del payload["user_id"]

    response = await client.post("/api/v1/transactions", json=payload)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_transactions(client: AsyncClient) -> None:
    """GET /transactions returns paginated decision rows."""
    tx_id = uuid4()
    created_at = "2026-06-25T12:00:00+00:00"

    with patch("app.routers.transactions.TransactionRepository") as mock_repo_cls:
        mock_repo = MagicMock()
        mock_repo.list_decisions = AsyncMock(
            return_value=(
                [
                    {
                        "transaction_id": tx_id,
                        "amount": "500.00",
                        "currency": "USD",
                        "decision": "block",
                        "score": 85,
                        "reason": "block_high_amount",
                        "rules_triggered": ["block_high_amount"],
                        "created_at": created_at,
                    }
                ],
                1,
            )
        )
        mock_repo_cls.return_value = mock_repo

        response = await client.get("/api/v1/transactions?limit=10&offset=0")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["transaction_id"] == str(tx_id)
    assert data["items"][0]["decision"] == "block"
