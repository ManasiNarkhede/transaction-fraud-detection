"""Integration tests for the full scoring pipeline."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transaction import Transaction
from app.models.user import User
from app.services.auth_service import hash_password


@pytest.fixture
async def test_user(async_session: AsyncSession) -> User:
    """Create and return a test analyst user."""
    user = User(
        email="analyst@example.com",
        hashed_password=hash_password("testpassword"),
        full_name="Test Analyst",
        role="analyst",
        is_active=True,
    )
    async_session.add(user)
    await async_session.commit()
    await async_session.refresh(user)
    return user


@pytest.fixture
async def test_transaction(async_session: AsyncSession, test_user: User) -> Transaction:
    """Create and return a test transaction for the test user."""
    transaction = Transaction(
        user_id=test_user.id,
        amount=1000.00,
        currency="USD",
        merchant_id="merchant-123",
        merchant_category="retail",
        status="pending",
    )
    async_session.add(transaction)
    await async_session.commit()
    await async_session.refresh(transaction)
    return transaction


@pytest.fixture
async def auth_headers(client: AsyncClient, test_user: User) -> dict[str, str]:
    """Login and return authorization headers with access token."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": test_user.email, "password": "testpassword"},
    )
    assert response.status_code == 200
    data = response.json()
    token = data["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.integration
async def test_scoring_pipeline(
    client: AsyncClient,
    async_session: AsyncSession,
    test_user: User,
    test_transaction: Transaction,
    auth_headers: dict[str, str],
) -> None:
    """Test the complete scoring flow: create transaction, score it, verify decision, check audit."""
    # 1. Score the transaction via POST /api/v1/decisions/evaluate
    evaluate_response = await client.post(
        "/api/v1/decisions/evaluate",
        headers=auth_headers,
        json={
            "transaction_id": str(test_transaction.id),
            "features": {
                "amount": "1000.00",
                "amount_zscore": 1.5,
                "time_since_last_tx": 2.0,
                "tx_count_1h": 1,
                "tx_count_24h": 3,
                "tx_count_7d": 10,
                "avg_amount_30d": "500.00",
                "max_amount_30d": "2000.00",
                "unique_merchants_24h": 2,
                "unique_countries_24h": 1,
                "device_trust_score": 0.8,
                "is_new_device": False,
                "hour_of_day": 14,
                "day_of_week": 2,
                "is_weekend": False,
            },
            "rule_result": {
                "score_adjustment": 10,
                "rules_triggered": ["high_amount_rule"],
                "actions": ["flag"],
            },
        },
    )
    assert evaluate_response.status_code == 200

    decision_data = evaluate_response.json()
    # 2. Verify the decision structure
    assert "score" in decision_data
    assert "decision" in decision_data
    assert 0 <= decision_data["score"] <= 100
    assert decision_data["decision"] in ["approve", "verify", "block"]
    assert "transaction_id" in decision_data
    assert "reason" in decision_data

    # 3. Check audit log was created via GET /api/v1/audit
    audit_response = await client.get(
        "/api/v1/audit",
        headers=auth_headers,
    )
    assert audit_response.status_code == 200

    audit_data = audit_response.json()
    assert "items" in audit_data
    assert len(audit_data["items"]) > 0

    # Verify the most recent audit record matches our transaction
    latest = audit_data["items"][0]
    assert latest["transaction_id"] == str(test_transaction.id)
    assert latest["decision"] == decision_data["decision"]
    assert latest["score"] == decision_data["score"]
