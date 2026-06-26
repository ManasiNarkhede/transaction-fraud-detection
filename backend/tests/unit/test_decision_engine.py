"""Unit tests for the DecisionEngine service."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.models.feature_vector import FeatureVector
from app.services.decision_engine import DecisionEngine


@pytest.fixture
def decision_engine():
    return DecisionEngine()


@pytest.fixture
def sample_features():
    return FeatureVector(
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


@pytest.fixture
def base_rule_result():
    return {
        "score_adjustment": 0,
        "rules_triggered": [],
        "actions": [],
        "decision": "approve",
    }


# Base score for sample_features:
#   amount_zscore * 10 + (1 - device_trust_score) * 20
# = 0.5 * 10 + (1 - 0.8) * 20 = 5 + 4 = 9


@pytest.mark.asyncio
async def test_decision_approve(decision_engine, sample_features, base_rule_result):
    """Score 30 should result in approve decision."""
    rule_result = {**base_rule_result, "score_adjustment": 21}  # 9 + 21 = 30

    with patch.object(decision_engine, "_update_transaction_status"):
        decision = await decision_engine.make_decision(
            uuid4(), sample_features, rule_result
        )

    assert decision.decision == "approve"
    assert decision.score == 30


@pytest.mark.asyncio
async def test_decision_verify(decision_engine, sample_features, base_rule_result):
    """Score 50 should result in verify decision."""
    rule_result = {**base_rule_result, "score_adjustment": 41}  # 9 + 41 = 50

    with patch.object(decision_engine, "_update_transaction_status"):
        decision = await decision_engine.make_decision(
            uuid4(), sample_features, rule_result
        )

    assert decision.decision == "verify"
    assert decision.score == 50


@pytest.mark.asyncio
async def test_decision_block(decision_engine, sample_features, base_rule_result):
    """Score 80 should result in block decision."""
    rule_result = {**base_rule_result, "score_adjustment": 71}  # 9 + 71 = 80

    with patch.object(decision_engine, "_update_transaction_status"):
        decision = await decision_engine.make_decision(
            uuid4(), sample_features, rule_result
        )

    assert decision.decision == "block"
    assert decision.score == 80


@pytest.mark.asyncio
async def test_decision_edge_40(decision_engine, sample_features, base_rule_result):
    """Score 40 (at approve threshold) should result in approve decision."""
    rule_result = {**base_rule_result, "score_adjustment": 31}  # 9 + 31 = 40

    with patch.object(decision_engine, "_update_transaction_status"):
        decision = await decision_engine.make_decision(
            uuid4(), sample_features, rule_result
        )

    assert decision.decision == "approve"
    assert decision.score == 40


@pytest.mark.asyncio
async def test_decision_edge_41(decision_engine, sample_features, base_rule_result):
    """Score 41 (just above approve threshold) should result in verify decision."""
    rule_result = {**base_rule_result, "score_adjustment": 32}  # 9 + 32 = 41

    with patch.object(decision_engine, "_update_transaction_status"):
        decision = await decision_engine.make_decision(
            uuid4(), sample_features, rule_result
        )

    assert decision.decision == "verify"
    assert decision.score == 41


@pytest.mark.asyncio
async def test_decision_edge_70(decision_engine, sample_features, base_rule_result):
    """Score 70 (at verify threshold) should result in verify decision."""
    rule_result = {**base_rule_result, "score_adjustment": 61}  # 9 + 61 = 70

    with patch.object(decision_engine, "_update_transaction_status"):
        decision = await decision_engine.make_decision(
            uuid4(), sample_features, rule_result
        )

    assert decision.decision == "verify"
    assert decision.score == 70


@pytest.mark.asyncio
async def test_decision_edge_71(decision_engine, sample_features, base_rule_result):
    """Score 71 (just above verify threshold) should result in block decision."""
    rule_result = {**base_rule_result, "score_adjustment": 62}  # 9 + 62 = 71

    with patch.object(decision_engine, "_update_transaction_status"):
        decision = await decision_engine.make_decision(
            uuid4(), sample_features, rule_result
        )

    assert decision.decision == "block"
    assert decision.score == 71


@pytest.mark.asyncio
async def test_decision_score_clamping(
    decision_engine, sample_features, base_rule_result
):
    """Score > 100 should be clamped to 100."""
    rule_result = {
        **base_rule_result,
        "score_adjustment": 200,
    }  # 9 + 200 = 209 -> clamped to 100

    with patch.object(decision_engine, "_update_transaction_status"):
        decision = await decision_engine.make_decision(
            uuid4(), sample_features, rule_result
        )

    assert decision.score == 100
    assert decision.decision == "block"


@pytest.mark.asyncio
async def test_decision_reason_generation(decision_engine, sample_features):
    """Reason should include triggered rules."""
    rule_result = {
        "score_adjustment": 0,
        "rules_triggered": ["high_amount", "new_device"],
        "actions": [],
        "decision": "approve",
    }

    with patch.object(decision_engine, "_update_transaction_status"):
        decision = await decision_engine.make_decision(
            uuid4(), sample_features, rule_result
        )

    assert "high_amount" in decision.reason
    assert "new_device" in decision.reason


@pytest.mark.asyncio
async def test_decision_block_rule_override(
    decision_engine, sample_features, base_rule_result
):
    """A block rule decision must override a low blended score."""
    rule_result = {
        **base_rule_result,
        "decision": "block",
        "rules_triggered": ["block_high_amount"],
        "actions": ["block"],
    }

    with (
        patch.object(decision_engine, "_update_transaction_status"),
        patch("app.services.decision_engine.settings") as mock_settings,
        patch.object(decision_engine.onnx_service, "is_ready", return_value=True),
        patch.object(
            decision_engine.onnx_service,
            "predict",
            return_value={"ensemble_score": 0.22},
        ),
    ):
        mock_settings.ml_enabled = True
        decision = await decision_engine.make_decision(
            uuid4(), sample_features, rule_result
        )

    assert decision.decision == "block"
    assert decision.score >= decision_engine.block_threshold


@pytest.mark.asyncio
async def test_decision_verify_rule_override(
    decision_engine, sample_features, base_rule_result
):
    """A verify rule decision should upgrade approve to verify."""
    rule_result = {
        **base_rule_result,
        "decision": "verify",
        "rules_triggered": ["verify_new_device"],
        "actions": ["verify"],
    }

    with patch.object(decision_engine, "_update_transaction_status"):
        decision = await decision_engine.make_decision(
            uuid4(), sample_features, rule_result
        )

    assert decision.decision == "verify"
    assert decision.score >= decision_engine.approve_threshold + 1


@pytest.mark.asyncio
async def test_decision_fallback_on_error(decision_engine, sample_features):
    """Error during decision making should fallback using rule output when present."""
    rule_result = {
        "score_adjustment": 0,
        "rules_triggered": ["block_high_amount"],
        "actions": ["block"],
        "decision": "block",
    }
    with (
        patch.object(
            decision_engine, "_calculate_score", side_effect=Exception("Test error")
        ),
        patch.object(
            decision_engine, "_update_transaction_status", new_callable=AsyncMock
        ),
    ):
        decision = await decision_engine.make_decision(
            uuid4(), sample_features, rule_result
        )

    assert decision.decision == "block"
    assert "Scoring error fallback" in decision.reason
