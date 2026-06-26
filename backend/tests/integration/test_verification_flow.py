"""Integration tests for the verification flow."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transaction import Transaction
from app.models.user import User
from app.services import otp_service
from app.services.auth_service import hash_password


@pytest.fixture
async def test_user(async_session: AsyncSession) -> User:
    """Create and return a test user for verification tests."""
    user = User(
        email="verifyuser@example.com",
        hashed_password=hash_password("verifypassword"),
        full_name="Verify Test User",
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
        amount=500.00,
        currency="USD",
        merchant_id="merchant-456",
        merchant_category="ecommerce",
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
        json={"username": test_user.email, "password": "verifypassword"},
    )
    assert response.status_code == 200
    data = response.json()
    token = data["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.integration
async def test_verification_flow(
    client: AsyncClient,
    async_session: AsyncSession,
    test_user: User,
    test_transaction: Transaction,
    auth_headers: dict[str, str],
) -> None:
    """Test the complete verification flow: create verification, check status, submit OTP, verify update."""
    # 1. Create verification via POST /api/v1/verify/send
    send_response = await client.post(
        "/api/v1/verify/send",
        headers=auth_headers,
        json={
            "transaction_id": str(test_transaction.id),
            "user_id": str(test_user.id),
            "channel": "email",
            "contact_info": "user@example.com",
        },
    )
    assert send_response.status_code == 200

    send_data = send_response.json()
    assert send_data["success"] is True
    assert "verification_id" in send_data["data"]
    assert send_data["data"]["state"] == "PENDING"

    verification_id = send_data["data"]["verification_id"]

    # 2. Check status via GET /api/v1/verify/{id}/status
    status_response = await client.get(
        f"/api/v1/verify/{verification_id}/status",
        headers=auth_headers,
    )
    assert status_response.status_code == 200

    status_data = status_response.json()
    assert status_data["success"] is True
    assert status_data["data"]["state"] == "PENDING"
    assert status_data["data"]["attempts"] == 0
    assert status_data["data"]["max_attempts"] == 3

    # Manually store an OTP in Redis so we can submit it
    test_otp = "123456"
    await otp_service.store_otp(verification_id, test_otp, ttl=600)

    # 3. Submit OTP via POST /api/v1/verify/otp
    otp_response = await client.post(
        "/api/v1/verify/otp",
        headers=auth_headers,
        json={
            "verification_id": verification_id,
            "otp": test_otp,
        },
    )
    assert otp_response.status_code == 200

    otp_data = otp_response.json()
    assert otp_data["success"] is True
    assert otp_data["data"]["state"] == "VERIFIED"
    assert "verified" in otp_data["data"]["message"].lower()

    # 4. Verify transaction status was updated to approved
    await async_session.refresh(test_transaction)
    stmt = select(Transaction).where(Transaction.id == test_transaction.id)
    result = await async_session.execute(stmt)
    updated_transaction = result.scalar_one()
    assert updated_transaction.status == "approved"
