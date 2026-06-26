"""Unit tests for VerificationService.approve and VerificationService.reject."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.verification_log import VerificationLog
from app.services.verification_service import VerificationService


@pytest.fixture
def mock_session() -> AsyncMock:
    """Return a mocked async session."""
    session = AsyncMock(spec=AsyncSession)
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=mock_result)
    return session


@pytest.fixture
def pending_verification() -> VerificationLog:
    """Return a VerificationLog in PENDING state."""
    return VerificationLog(
        id=uuid4(),
        transaction_id=uuid4(),
        user_id=uuid4(),
        state="PENDING",
        channel="sms",
        contact_info="+1234567890",
        attempts=0,
        max_attempts=3,
    )


# ---------------------------------------------------------------------------
# VerificationService.approve
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_approve_transitions_to_verified(
    mock_session: AsyncMock, pending_verification: VerificationLog
) -> None:
    """approve() should transition state from PENDING to VERIFIED."""
    service = VerificationService()

    with (
        patch.object(service, "_get_verification", new_callable=AsyncMock) as mock_get,
        patch("app.services.verification_service.otp_service") as mock_otp,
    ):
        mock_get.return_value = pending_verification
        mock_otp.delete_otp = AsyncMock()

        result = await service.approve(
            session=mock_session,
            verification_id=pending_verification.id,
        )

    assert result.state == "VERIFIED"
    assert result.verified_at is not None
    mock_session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_approve_raises_when_not_found(mock_session: AsyncMock) -> None:
    """approve() should raise ValueError when verification not found."""
    service = VerificationService()

    with patch.object(service, "_get_verification", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = None

        with pytest.raises(ValueError, match="not found"):
            await service.approve(
                session=mock_session,
                verification_id=uuid4(),
            )


@pytest.mark.asyncio
async def test_approve_raises_on_invalid_state(mock_session: AsyncMock) -> None:
    """approve() should raise ValueError when already VERIFIED."""
    service = VerificationService()
    already_verified = VerificationLog(
        id=uuid4(),
        transaction_id=uuid4(),
        user_id=uuid4(),
        state="VERIFIED",
        attempts=0,
        max_attempts=3,
    )

    with patch.object(service, "_get_verification", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = already_verified

        with pytest.raises(ValueError, match="Invalid state transition"):
            await service.approve(
                session=mock_session,
                verification_id=already_verified.id,
            )


# ---------------------------------------------------------------------------
# VerificationService.reject
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reject_transitions_to_failed(
    mock_session: AsyncMock, pending_verification: VerificationLog
) -> None:
    """reject() should transition state from PENDING to FAILED."""
    service = VerificationService()

    with (
        patch.object(service, "_get_verification", new_callable=AsyncMock) as mock_get,
        patch("app.services.verification_service.otp_service") as mock_otp,
    ):
        mock_get.return_value = pending_verification
        mock_otp.delete_otp = AsyncMock()

        result = await service.reject(
            session=mock_session,
            verification_id=pending_verification.id,
        )

    assert result.state == "FAILED"
    assert result.failed_at is not None
    mock_session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_reject_raises_when_not_found(mock_session: AsyncMock) -> None:
    """reject() should raise ValueError when verification not found."""
    service = VerificationService()

    with patch.object(service, "_get_verification", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = None

        with pytest.raises(ValueError, match="not found"):
            await service.reject(
                session=mock_session,
                verification_id=uuid4(),
            )


@pytest.mark.asyncio
async def test_reject_raises_on_invalid_state(mock_session: AsyncMock) -> None:
    """reject() should raise ValueError when already FAILED."""
    service = VerificationService()
    already_failed = VerificationLog(
        id=uuid4(),
        transaction_id=uuid4(),
        user_id=uuid4(),
        state="FAILED",
        attempts=0,
        max_attempts=3,
    )

    with patch.object(service, "_get_verification", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = already_failed

        with pytest.raises(ValueError, match="Invalid state transition"):
            await service.reject(
                session=mock_session,
                verification_id=already_failed.id,
            )
