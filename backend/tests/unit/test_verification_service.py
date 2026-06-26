"""Unit tests for the VerificationService."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.verification_log import VerificationLog
from app.services.verification_service import VerificationService

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_session() -> AsyncMock:
    """Return a mocked async session."""
    session = AsyncMock(spec=AsyncSession)
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    # Default execute return for _update_transaction_status
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=mock_result)
    return session


@pytest.fixture
def verification_service() -> VerificationService:
    """Return a VerificationService instance."""
    return VerificationService()


@pytest.fixture
def sample_verification() -> VerificationLog:
    """Return a sample VerificationLog in PENDING state."""
    return VerificationLog(
        id=uuid4(),
        transaction_id=uuid4(),
        user_id=uuid4(),
        state="PENDING",
        channel="sms",
        contact_info="+1234567890",
        attempts=0,
        max_attempts=3,
        created_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
        otp_expires_at=datetime(2099, 1, 1, 12, 10, 0, tzinfo=UTC),
    )


# ---------------------------------------------------------------------------
# create_verification tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_verification_creates_pending_record(
    mock_session: AsyncMock,
    verification_service: VerificationService,
) -> None:
    """create_verification should create a record with PENDING state."""
    transaction_id = uuid4()
    user_id = uuid4()

    result = await verification_service.create_verification(
        session=mock_session,
        transaction_id=transaction_id,
        user_id=user_id,
        channel="sms",
        contact_info="+1234567890",
    )

    assert result is not None
    assert result.state == "PENDING"
    assert result.transaction_id == transaction_id
    assert result.user_id == user_id
    assert result.channel == "sms"
    assert result.contact_info == "+1234567890"
    assert result.attempts == 0
    assert result.max_attempts == 3
    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()
    mock_session.refresh.assert_called_once()


# ---------------------------------------------------------------------------
# validate_otp tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_otp_correct_returns_verified(
    mock_session: AsyncMock,
    verification_service: VerificationService,
    sample_verification: VerificationLog,
) -> None:
    """validate_otp with correct OTP should return VERIFIED."""
    # Mock _get_verification to return sample
    verification_service._get_verification = AsyncMock(return_value=sample_verification)
    verification_service._update_transaction_status = AsyncMock()

    # Mock OTP service
    with patch("app.services.verification_service.otp_service") as mock_otp:
        mock_otp.get_otp_data = AsyncMock(return_value={"hash": "hashed_otp"})
        mock_otp.verify_otp = MagicMock(return_value=True)
        mock_otp.delete_otp = AsyncMock()

        result = await verification_service.validate_otp(
            session=mock_session,
            verification_id=sample_verification.id,
            otp="123456",
        )

    assert result["success"] is True
    assert result["state"] == "VERIFIED"
    assert result["message"] == "OTP verified successfully"
    assert sample_verification.state == "VERIFIED"
    assert sample_verification.verified_at is not None
    mock_otp.delete_otp.assert_called_once_with(sample_verification.id)


@pytest.mark.asyncio
async def test_validate_otp_incorrect_increments_attempts(
    mock_session: AsyncMock,
    verification_service: VerificationService,
    sample_verification: VerificationLog,
) -> None:
    """validate_otp with incorrect OTP should increment attempts."""
    verification_service._get_verification = AsyncMock(return_value=sample_verification)

    with patch("app.services.verification_service.otp_service") as mock_otp:
        mock_otp.get_otp_data = AsyncMock(return_value={"hash": "hashed_otp"})
        mock_otp.verify_otp = MagicMock(return_value=False)

        result = await verification_service.validate_otp(
            session=mock_session,
            verification_id=sample_verification.id,
            otp="wrong_otp",
        )

    assert result["success"] is False
    assert result["state"] == "PENDING"
    assert result["message"] == "Invalid OTP"
    assert sample_verification.attempts == 1


@pytest.mark.asyncio
async def test_validate_otp_max_attempts_returns_failed(
    mock_session: AsyncMock,
    verification_service: VerificationService,
    sample_verification: VerificationLog,
) -> None:
    """validate_otp with max attempts should return FAILED."""
    sample_verification.attempts = 2  # One attempt remaining
    verification_service._get_verification = AsyncMock(return_value=sample_verification)
    verification_service._update_transaction_status = AsyncMock()

    with patch("app.services.verification_service.otp_service") as mock_otp:
        mock_otp.get_otp_data = AsyncMock(return_value={"hash": "hashed_otp"})
        mock_otp.verify_otp = MagicMock(return_value=False)
        mock_otp.delete_otp = AsyncMock()

        result = await verification_service.validate_otp(
            session=mock_session,
            verification_id=sample_verification.id,
            otp="wrong_otp",
        )

    assert result["success"] is False
    assert result["state"] == "FAILED"
    assert result["message"] == "Maximum attempts exceeded"
    assert sample_verification.state == "FAILED"
    mock_otp.delete_otp.assert_called_once_with(sample_verification.id)


@pytest.mark.asyncio
async def test_validate_otp_not_found(
    mock_session: AsyncMock,
    verification_service: VerificationService,
) -> None:
    """validate_otp should return NOT_FOUND when verification doesn't exist."""
    verification_service._get_verification = AsyncMock(return_value=None)

    result = await verification_service.validate_otp(
        session=mock_session,
        verification_id=uuid4(),
        otp="123456",
    )

    assert result["success"] is False
    assert result["state"] == "NOT_FOUND"
    assert result["message"] == "Verification record not found"


@pytest.mark.asyncio
async def test_validate_otp_already_verified(
    mock_session: AsyncMock,
    verification_service: VerificationService,
    sample_verification: VerificationLog,
) -> None:
    """validate_otp should return error when already verified."""
    sample_verification.state = "VERIFIED"
    verification_service._get_verification = AsyncMock(return_value=sample_verification)

    result = await verification_service.validate_otp(
        session=mock_session,
        verification_id=sample_verification.id,
        otp="123456",
    )

    assert result["success"] is False
    assert result["state"] == "VERIFIED"
    assert "already VERIFIED" in result["message"]


@pytest.mark.asyncio
async def test_validate_otp_expired(
    mock_session: AsyncMock,
    verification_service: VerificationService,
    sample_verification: VerificationLog,
) -> None:
    """validate_otp should return EXPIRED when OTP has expired."""
    sample_verification.otp_expires_at = datetime(2020, 1, 1, 12, 0, 0, tzinfo=UTC)
    verification_service._get_verification = AsyncMock(return_value=sample_verification)
    verification_service.handle_expiration = AsyncMock(return_value=sample_verification)

    result = await verification_service.validate_otp(
        session=mock_session,
        verification_id=sample_verification.id,
        otp="123456",
    )

    assert result["success"] is False
    assert result["state"] == "EXPIRED"
    assert result["message"] == "OTP has expired"


# ---------------------------------------------------------------------------
# escalate tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_escalate_transitions_to_failed(
    mock_session: AsyncMock,
    verification_service: VerificationService,
    sample_verification: VerificationLog,
) -> None:
    """escalate should transition verification to FAILED."""
    verification_service._get_verification = AsyncMock(return_value=sample_verification)
    verification_service._update_transaction_status = AsyncMock()

    with patch("app.services.verification_service.otp_service") as mock_otp:
        mock_otp.delete_otp = AsyncMock()

        result = await verification_service.escalate(
            session=mock_session,
            verification_id=sample_verification.id,
        )

    assert result is not None
    assert result.state == "FAILED"
    assert result.failed_at is not None
    mock_otp.delete_otp.assert_called_once_with(sample_verification.id)


@pytest.mark.asyncio
async def test_escalate_not_found(
    mock_session: AsyncMock,
    verification_service: VerificationService,
) -> None:
    """escalate should raise ValueError when verification not found."""
    verification_service._get_verification = AsyncMock(return_value=None)

    with pytest.raises(ValueError, match="not found"):
        await verification_service.escalate(
            session=mock_session,
            verification_id=uuid4(),
        )


# ---------------------------------------------------------------------------
# handle_expiration tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_expiration_transitions_to_expired(
    mock_session: AsyncMock,
    verification_service: VerificationService,
    sample_verification: VerificationLog,
) -> None:
    """handle_expiration should transition verification to EXPIRED."""
    verification_service._get_verification = AsyncMock(return_value=sample_verification)
    verification_service._update_transaction_status = AsyncMock()

    with patch("app.services.verification_service.otp_service") as mock_otp:
        mock_otp.delete_otp = AsyncMock()

        result = await verification_service.handle_expiration(
            session=mock_session,
            verification_id=sample_verification.id,
        )

    assert result is not None
    assert result.state == "EXPIRED"
    assert result.expired_at is not None
    mock_otp.delete_otp.assert_called_once_with(sample_verification.id)


@pytest.mark.asyncio
async def test_handle_expiration_not_found(
    mock_session: AsyncMock,
    verification_service: VerificationService,
) -> None:
    """handle_expiration should raise ValueError when verification not found."""
    verification_service._get_verification = AsyncMock(return_value=None)

    with pytest.raises(ValueError, match="not found"):
        await verification_service.handle_expiration(
            session=mock_session,
            verification_id=uuid4(),
        )


# ---------------------------------------------------------------------------
# _transition_state tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_transition_state_rejects_invalid_transitions(
    verification_service: VerificationService,
    sample_verification: VerificationLog,
) -> None:
    """_transition_state should reject invalid state transitions."""
    sample_verification.state = "VERIFIED"

    with pytest.raises(ValueError, match="Invalid state transition"):
        await verification_service._transition_state(sample_verification, "FAILED")


@pytest.mark.asyncio
async def test_transition_state_verified_sets_timestamp(
    verification_service: VerificationService,
    sample_verification: VerificationLog,
) -> None:
    """_transition_state to VERIFIED should set verified_at."""
    await verification_service._transition_state(sample_verification, "VERIFIED")

    assert sample_verification.state == "VERIFIED"
    assert sample_verification.verified_at is not None


@pytest.mark.asyncio
async def test_transition_state_failed_sets_timestamp(
    verification_service: VerificationService,
    sample_verification: VerificationLog,
) -> None:
    """_transition_state to FAILED should set failed_at."""
    await verification_service._transition_state(sample_verification, "FAILED")

    assert sample_verification.state == "FAILED"
    assert sample_verification.failed_at is not None


@pytest.mark.asyncio
async def test_transition_state_expired_sets_timestamp(
    verification_service: VerificationService,
    sample_verification: VerificationLog,
) -> None:
    """_transition_state to EXPIRED should set expired_at."""
    await verification_service._transition_state(sample_verification, "EXPIRED")

    assert sample_verification.state == "EXPIRED"
    assert sample_verification.expired_at is not None


# ---------------------------------------------------------------------------
# get_status tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_status_found(
    mock_session: AsyncMock,
    verification_service: VerificationService,
    sample_verification: VerificationLog,
) -> None:
    """get_status should return verification details when found."""
    verification_service._get_verification = AsyncMock(return_value=sample_verification)

    result = await verification_service.get_status(
        session=mock_session,
        verification_id=sample_verification.id,
    )

    assert result["found"] is True
    assert result["state"] == "PENDING"
    assert result["attempts"] == 0
    assert result["max_attempts"] == 3


@pytest.mark.asyncio
async def test_get_status_not_found(
    mock_session: AsyncMock,
    verification_service: VerificationService,
) -> None:
    """get_status should return NOT_FOUND when verification doesn't exist."""
    verification_service._get_verification = AsyncMock(return_value=None)

    result = await verification_service.get_status(
        session=mock_session,
        verification_id=uuid4(),
    )

    assert result["found"] is False
    assert result["state"] == "NOT_FOUND"


# ---------------------------------------------------------------------------
# get_queue tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_queue_returns_list(
    mock_session: AsyncMock,
    verification_service: VerificationService,
    sample_verification: VerificationLog,
) -> None:
    """get_queue should return enriched verification rows."""
    mock_result = MagicMock()
    mock_result.all.return_value = [
        (sample_verification, Decimal("500.00"), "USD", "verify", Decimal("55"))
    ]
    mock_session.execute = AsyncMock(return_value=mock_result)

    result = await verification_service.get_queue(
        session=mock_session,
        owner_id=uuid4(),
        state="PENDING",
        limit=50,
        offset=0,
    )

    assert len(result) == 1
    assert result[0]["verification"].state == "PENDING"
    assert result[0]["risk_score"] == 55
