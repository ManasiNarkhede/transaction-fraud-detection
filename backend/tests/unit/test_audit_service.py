"""Unit tests for the AuditService."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.audit_service import AuditService

_OWNER = uuid4()

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_features():
    return {
        "amount": Decimal("100.00"),
        "amount_zscore": 0.5,
        "time_since_last_tx": 24.0,
        "tx_count_1h": 0,
        "tx_count_24h": 1,
        "tx_count_7d": 5,
        "avg_amount_30d": Decimal("50.00"),
        "max_amount_30d": Decimal("200.00"),
        "unique_merchants_24h": 1,
        "unique_countries_24h": 1,
        "device_trust_score": 0.8,
        "is_new_device": False,
        "hour_of_day": 14,
        "day_of_week": 2,
        "is_weekend": False,
    }


@pytest.fixture
def mock_session_maker():
    """Patch get_session_maker for isolated unit tests."""
    mock_maker = MagicMock()
    with patch(
        "app.services.audit_service.get_session_maker", return_value=mock_maker
    ) as _:
        yield mock_maker


# ---------------------------------------------------------------------------
# Hash generation tests
# ---------------------------------------------------------------------------


def test_generate_hash_consistency():
    """Same inputs must always produce the same hash."""
    h1 = AuditService._generate_hash(
        transaction_id=UUID("12345678-1234-5678-1234-567812345678"),
        decision="approve",
        score=30,
        reason="No risk signals detected",
        features={"amount_zscore": 0.5},
        rules_triggered=[],
        model_version="v1.0",
        previous_hash="abc123",
    )
    h2 = AuditService._generate_hash(
        transaction_id=UUID("12345678-1234-5678-1234-567812345678"),
        decision="approve",
        score=30,
        reason="No risk signals detected",
        features={"amount_zscore": 0.5},
        rules_triggered=[],
        model_version="v1.0",
        previous_hash="abc123",
    )
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex length


def test_generate_hash_different_inputs():
    """Different inputs must produce different hashes."""
    h1 = AuditService._generate_hash(
        transaction_id=UUID("12345678-1234-5678-1234-567812345678"),
        decision="approve",
        score=30,
        reason="No risk signals detected",
        features={"amount_zscore": 0.5},
        rules_triggered=[],
        model_version="v1.0",
        previous_hash="abc123",
    )
    h2 = AuditService._generate_hash(
        transaction_id=UUID("12345678-1234-5678-1234-567812345678"),
        decision="block",
        score=30,
        reason="No risk signals detected",
        features={"amount_zscore": 0.5},
        rules_triggered=[],
        model_version="v1.0",
        previous_hash="abc123",
    )
    assert h1 != h2


def test_generate_hash_includes_previous_hash():
    """Hash must change when previous_hash changes."""
    h1 = AuditService._generate_hash(
        transaction_id=UUID("12345678-1234-5678-1234-567812345678"),
        decision="approve",
        score=30,
        reason="No risk signals detected",
        features={"amount_zscore": 0.5},
        rules_triggered=[],
        model_version="v1.0",
        previous_hash="abc123",
    )
    h2 = AuditService._generate_hash(
        transaction_id=UUID("12345678-1234-5678-1234-567812345678"),
        decision="approve",
        score=30,
        reason="No risk signals detected",
        features={"amount_zscore": 0.5},
        rules_triggered=[],
        model_version="v1.0",
        previous_hash="def456",
    )
    assert h1 != h2


# ---------------------------------------------------------------------------
# PII sanitization tests
# ---------------------------------------------------------------------------


def test_sanitize_features_removes_pii():
    """PII fields must be stripped from features."""
    raw = {
        "amount": 100.0,
        "card_number": "4111111111111111",
        "cvv": "123",
        "cardholder_name": "John Doe",
        "ssn": "123-45-6789",
        "password": "secret",
        "token": "abc123",
        "device_trust_score": 0.8,
    }
    sanitized = AuditService._sanitize_features(raw)
    assert "card_number" not in sanitized
    assert "cvv" not in sanitized
    assert "cardholder_name" not in sanitized
    assert "ssn" not in sanitized
    assert "password" not in sanitized
    assert "token" not in sanitized
    assert "amount" in sanitized
    assert "device_trust_score" in sanitized


def test_sanitize_features_converts_decimal():
    """Decimal feature values must be JSON-serializable floats."""
    from decimal import Decimal

    sanitized = AuditService._sanitize_features({"avg_amount_30d": Decimal("50.00")})
    assert sanitized["avg_amount_30d"] == 50.0


# ---------------------------------------------------------------------------
# log_decision tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_log_decision_creates_record(mock_session_maker, sample_features):
    """log_decision should create and return an audit record."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=False)

    # Owner lookup then previous hash lookup
    owner_result = MagicMock()
    owner_result.scalar_one_or_none.return_value = uuid4()
    hash_result = MagicMock()
    hash_result.scalar_one_or_none.return_value = None
    mock_session.execute.side_effect = [owner_result, hash_result]

    record = await AuditService.log_decision(
        transaction_id=uuid4(),
        decision="approve",
        score=30,
        reason="No risk signals detected",
        features=sample_features,
        rules_triggered=[],
        model_version="v1.0",
    )

    assert record is not None
    assert record.decision == "approve"
    assert record.score == 30
    assert record.hash is not None
    assert record.previous_hash is None
    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_log_decision_forms_chain(mock_session_maker, sample_features):
    """Second record's previous_hash should equal first record's hash."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=False)

    first_hash = "a" * 64
    owner_id = uuid4()

    owner_result = MagicMock()
    owner_result.scalar_one_or_none.return_value = owner_id
    hash_none = MagicMock()
    hash_none.scalar_one_or_none.return_value = None
    hash_first = MagicMock()
    hash_first.scalar_one_or_none.return_value = first_hash

    mock_session.execute.side_effect = [
        owner_result,
        hash_none,
        owner_result,
        hash_first,
    ]

    record1 = await AuditService.log_decision(
        transaction_id=uuid4(),
        decision="approve",
        score=30,
        reason="No risk signals detected",
        features=sample_features,
        rules_triggered=[],
    )

    record2 = await AuditService.log_decision(
        transaction_id=uuid4(),
        decision="block",
        score=80,
        reason="High risk",
        features=sample_features,
        rules_triggered=["rule1"],
    )

    assert record1 is not None
    assert record2 is not None
    assert record1.previous_hash is None
    assert record2.previous_hash == first_hash


@pytest.mark.asyncio
async def test_log_decision_graceful_on_failure(mock_session_maker, sample_features):
    """log_decision should return None on database failure without raising."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=False)
    mock_session.execute.side_effect = Exception("DB error")

    record = await AuditService.log_decision(
        transaction_id=uuid4(),
        decision="approve",
        score=30,
        reason="No risk signals detected",
        features=sample_features,
        rules_triggered=[],
    )

    assert record is None


@pytest.mark.asyncio
async def test_log_decision_when_db_not_initialized():
    """log_decision should return None when async_session_maker is None."""
    with patch("app.services.audit_service.get_session_maker", return_value=None):
        record = await AuditService.log_decision(
            transaction_id=uuid4(),
            decision="approve",
            score=30,
            reason="No risk signals detected",
            features={},
            rules_triggered=[],
        )
    assert record is None


# ---------------------------------------------------------------------------
# verify_integrity tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_verify_integrity_empty_chain():
    """Empty chain should be reported as valid."""
    mock_session = AsyncMock(spec=AsyncSession)
    with patch("app.services.audit_service.get_session_maker") as mock_get:
        mock_maker = mock_get.return_value
        mock_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_maker.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        result = await AuditService.verify_integrity(owner_id=_OWNER)

    assert result["valid"] is True
    assert result["total_records"] == 0
    assert result["first_broken_id"] is None


@pytest.mark.asyncio
async def test_verify_integrity_valid_chain():
    """A valid hash chain should pass verification."""
    from app.models.fraud_decision_audit import FraudDecisionAudit

    tx_id = uuid4()
    features = {"amount_zscore": 0.5}
    rules_triggered = ["rule1"]

    # Create first record with no previous hash
    hash1 = AuditService._generate_hash(
        transaction_id=tx_id,
        decision="approve",
        score=30,
        reason="No risk",
        features=features,
        rules_triggered=rules_triggered,
        model_version=None,
        previous_hash=None,
    )

    record1 = FraudDecisionAudit(
        id=uuid4(),
        transaction_id=tx_id,
        decision="approve",
        score=30,
        reason="No risk",
        features=features,
        rules_triggered=rules_triggered,
        model_version=None,
        hash=hash1,
        previous_hash=None,
        created_at=datetime(2024, 1, 1, 12, 0, 0),
    )

    # Create second record chained to first
    hash2 = AuditService._generate_hash(
        transaction_id=tx_id,
        decision="block",
        score=80,
        reason="High risk",
        features=features,
        rules_triggered=rules_triggered,
        model_version=None,
        previous_hash=hash1,
    )

    record2 = FraudDecisionAudit(
        id=uuid4(),
        transaction_id=tx_id,
        decision="block",
        score=80,
        reason="High risk",
        features=features,
        rules_triggered=rules_triggered,
        model_version=None,
        hash=hash2,
        previous_hash=hash1,
        created_at=datetime(2024, 1, 1, 12, 1, 0),
    )

    mock_session = AsyncMock(spec=AsyncSession)
    with patch("app.services.audit_service.get_session_maker") as mock_get:
        mock_maker = mock_get.return_value
        mock_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_maker.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [record1, record2]
        mock_session.execute.return_value = mock_result

        result = await AuditService.verify_integrity(owner_id=_OWNER)

    assert result["valid"] is True
    assert result["total_records"] == 2
    assert result["first_broken_id"] is None


@pytest.mark.asyncio
async def test_verify_integrity_detects_tampering():
    """Tampered record should be detected and reported."""
    from app.models.fraud_decision_audit import FraudDecisionAudit

    tx_id = uuid4()
    features = {"amount_zscore": 0.5}

    # Create a record with a tampered hash
    record = FraudDecisionAudit(
        id=uuid4(),
        transaction_id=tx_id,
        decision="approve",
        score=30,
        reason="No risk",
        features=features,
        rules_triggered=[],
        model_version=None,
        hash="tampered_hash_123456789012345678901234567890123456789012345678901234567890",
        previous_hash=None,
        created_at=datetime(2024, 1, 1, 12, 0, 0),
    )

    mock_session = AsyncMock(spec=AsyncSession)
    with patch("app.services.audit_service.get_session_maker") as mock_get:
        mock_maker = mock_get.return_value
        mock_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_maker.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [record]
        mock_session.execute.return_value = mock_result

        result = await AuditService.verify_integrity(owner_id=_OWNER)

    assert result["valid"] is False
    assert result["total_records"] == 1
    assert result["first_broken_id"] == record.id
    assert "mismatch" in result["message"].lower()


# ---------------------------------------------------------------------------
# query_audits tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_query_audits_with_decision_filter():
    """query_audits should filter by decision."""
    from app.models.fraud_decision_audit import FraudDecisionAudit

    record = FraudDecisionAudit(
        id=uuid4(),
        transaction_id=uuid4(),
        decision="block",
        score=80,
        reason="High risk",
        features={},
        rules_triggered=[],
        hash="a" * 64,
        previous_hash=None,
        created_at=datetime(2024, 1, 1, 12, 0, 0),
    )

    mock_session = AsyncMock(spec=AsyncSession)
    with patch("app.services.audit_service.get_session_maker") as mock_get:
        mock_maker = mock_get.return_value
        mock_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_maker.return_value.__aexit__ = AsyncMock(return_value=False)

        # Mock count query
        count_result = MagicMock()
        count_result.scalar_one.return_value = 1

        # Mock data query
        data_result = MagicMock()
        data_result.scalars.return_value.all.return_value = [record]

        mock_session.execute.side_effect = [count_result, data_result]

        records, total = await AuditService.query_audits(
            owner_id=_OWNER, decision="block"
        )

    assert total == 1
    assert len(records) == 1
    assert records[0].decision == "block"


@pytest.mark.asyncio
async def test_query_audits_with_date_filter():
    """query_audits should filter by date range."""
    mock_session = AsyncMock(spec=AsyncSession)
    with patch("app.services.audit_service.get_session_maker") as mock_get:
        mock_maker = mock_get.return_value
        mock_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_maker.return_value.__aexit__ = AsyncMock(return_value=False)

        count_result = MagicMock()
        count_result.scalar_one.return_value = 0

        data_result = MagicMock()
        data_result.scalars.return_value.all.return_value = []

        mock_session.execute.side_effect = [count_result, data_result]

        records, total = await AuditService.query_audits(
            owner_id=_OWNER,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
        )

    assert total == 0
    assert len(records) == 0


@pytest.mark.asyncio
async def test_query_audits_pagination():
    """query_audits should respect limit and offset."""
    mock_session = AsyncMock(spec=AsyncSession)
    with patch("app.services.audit_service.get_session_maker") as mock_get:
        mock_maker = mock_get.return_value
        mock_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_maker.return_value.__aexit__ = AsyncMock(return_value=False)

        count_result = MagicMock()
        count_result.scalar_one.return_value = 100

        data_result = MagicMock()
        data_result.scalars.return_value.all.return_value = []

        mock_session.execute.side_effect = [count_result, data_result]

        records, total = await AuditService.query_audits(
            owner_id=_OWNER, limit=10, offset=20
        )

    assert total == 100
    assert len(records) == 0


@pytest.mark.asyncio
async def test_query_audits_when_db_not_initialized():
    """query_audits should return empty results when DB is not initialized."""
    with patch("app.services.audit_service.get_session_maker", return_value=None):
        records, total = await AuditService.query_audits(owner_id=_OWNER)

    assert records == []
    assert total == 0
