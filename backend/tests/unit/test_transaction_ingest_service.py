"""Unit tests for TransactionIngestService orchestration (mocked DB/engines)."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.models.decision import Decision
from app.models.feature_vector import FeatureVector
from app.schemas.transaction import TransactionIngestRequest
from app.services.transaction_ingest_service import TransactionIngestService


class _FakeSessionCtx:
    """Async context manager yielding a fixed (mock) session."""

    def __init__(self, session: object) -> None:
        self._session = session

    async def __aenter__(self) -> object:
        return self._session

    async def __aexit__(self, *exc: object) -> bool:
        return False


def _make_features() -> FeatureVector:
    return FeatureVector(
        amount=Decimal("100.00"),
        log_amount=4.6,
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
        failed_attempt_count=2,
        merchant_risk_score=0.25,
    )


def _make_request() -> TransactionIngestRequest:
    return TransactionIngestRequest(
        user_id=uuid4(),
        amount=Decimal("100.00"),
        currency="USD",
        merchant_id="merchant-1",
        device_id="device-abc",
        ip_address="1.2.3.4",
        payment_method="card",
    )


@pytest.fixture
def injected_service() -> tuple[TransactionIngestService, MagicMock]:
    """Build a service with mocked feature/rule/decision collaborators."""
    transaction_id = uuid4()

    feature_service = MagicMock()
    feature_service.compute_features_from_db = AsyncMock(return_value=_make_features())
    feature_service.cache_features = AsyncMock(return_value=True)

    rule_engine = MagicMock()
    rule_engine.evaluate_transaction = AsyncMock(
        return_value={"score_adjustment": 30, "rules_triggered": ["velocity"]}
    )

    decision_engine = MagicMock()
    decision_engine.make_decision = AsyncMock(
        return_value=Decision(
            transaction_id=transaction_id,
            score=55,
            decision="verify",
            reason="velocity",
            rules_triggered=["velocity"],
            features_used={},
        )
    )

    service = TransactionIngestService(
        feature_service=feature_service,
        rule_engine=rule_engine,
        decision_engine=decision_engine,
    )
    return service, MagicMock(transaction_id=transaction_id)


@pytest.mark.asyncio
async def test_ingest_orchestrates_full_flow(
    injected_service: tuple[TransactionIngestService, MagicMock],
) -> None:
    """ingest should persist, compute features, score, and return a decision."""
    service, ctx = injected_service
    request = _make_request()

    mock_session = AsyncMock()
    mock_repo = MagicMock()
    created_tx = MagicMock()
    created_tx.id = ctx.transaction_id
    mock_repo.create_transaction = AsyncMock(return_value=created_tx)
    mock_repo.save_fraud_score = AsyncMock(return_value=MagicMock())

    with (
        patch(
            "app.services.transaction_ingest_service.get_session_maker",
            return_value=lambda: _FakeSessionCtx(mock_session),
        ),
        patch(
            "app.services.transaction_ingest_service.TransactionRepository",
            return_value=mock_repo,
        ),
    ):
        response = await service.ingest(request, owner_id=uuid4())

    assert response.transaction_id == ctx.transaction_id
    assert response.decision == "verify"
    assert response.score == 55
    assert response.requires_verification is True
    assert response.rules_triggered == ["velocity"]

    # Feature engineering was driven from the persisted transaction.
    service.feature_service.compute_features_from_db.assert_awaited_once()
    # Rule result fed into the decision engine.
    service.rule_engine.evaluate_transaction.assert_awaited_once()
    service.decision_engine.make_decision.assert_awaited_once()
    # Fraud score was persisted.
    mock_repo.save_fraud_score.assert_awaited_once()


@pytest.mark.asyncio
async def test_ingest_approve_sets_no_verification(
    injected_service: tuple[TransactionIngestService, MagicMock],
) -> None:
    """An approve decision should not require verification."""
    service, ctx = injected_service
    service.decision_engine.make_decision = AsyncMock(
        return_value=Decision(
            transaction_id=ctx.transaction_id,
            score=10,
            decision="approve",
            reason="No risk signals detected",
            rules_triggered=[],
            features_used={},
        )
    )

    mock_session = AsyncMock()
    mock_repo = MagicMock()
    created_tx = MagicMock()
    created_tx.id = ctx.transaction_id
    mock_repo.create_transaction = AsyncMock(return_value=created_tx)
    mock_repo.save_fraud_score = AsyncMock(return_value=MagicMock())

    with (
        patch(
            "app.services.transaction_ingest_service.get_session_maker",
            return_value=lambda: _FakeSessionCtx(mock_session),
        ),
        patch(
            "app.services.transaction_ingest_service.TransactionRepository",
            return_value=mock_repo,
        ),
    ):
        response = await service.ingest(_make_request(), owner_id=uuid4())

    assert response.decision == "approve"
    assert response.requires_verification is False


@pytest.mark.asyncio
async def test_ingest_raises_without_db(
    injected_service: tuple[TransactionIngestService, MagicMock],
) -> None:
    """ingest should raise when the session maker is uninitialized."""
    service, _ = injected_service
    with (
        patch(
            "app.services.transaction_ingest_service.get_session_maker",
            return_value=None,
        ),
        pytest.raises(RuntimeError),
    ):
        await service.ingest(_make_request(), owner_id=uuid4())
