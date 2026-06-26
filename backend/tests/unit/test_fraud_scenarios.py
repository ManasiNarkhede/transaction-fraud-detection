"""Fraud scenario unit tests.

Tests the decision path (DecisionEngine._calculate_score + _determine_decision +
rule_evaluator.evaluate_condition) for the 7 scenarios defined in the spec's
Testing Strategy.  All tests run without a DB or Redis — the decision engine's
DB write is patched out, and rule contexts are constructed inline.

Thresholds (from settings defaults):
    approve  : score <= 40
    verify   : 41 <= score <= 70
    block    : score >= 71
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio  # noqa: F401 — ensures asyncio plugin registration

from app.models.feature_vector import FeatureVector
from app.services.decision_engine import DecisionEngine
from app.services.rule_evaluator import evaluate_condition

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _features(
    *,
    amount: float = 50.0,
    amount_zscore: float = 0.0,
    time_since_last_tx: float = 24.0,
    tx_count_1h: int = 0,
    tx_count_24h: int = 1,
    tx_count_7d: int = 3,
    avg_amount_30d: float = 50.0,
    max_amount_30d: float = 100.0,
    unique_merchants_24h: int = 1,
    unique_countries_24h: int = 1,
    device_trust_score: float = 0.9,
    is_new_device: bool = False,
    hour_of_day: int = 10,
    day_of_week: int = 2,
    is_weekend: bool = False,
    failed_attempt_count: int = 0,
    merchant_risk_score: float = 0.0,
) -> FeatureVector:
    """Return a FeatureVector with sensible defaults, overridable per scenario."""
    return FeatureVector(
        amount=Decimal(str(amount)),
        amount_zscore=amount_zscore,
        time_since_last_tx=time_since_last_tx,
        tx_count_1h=tx_count_1h,
        tx_count_24h=tx_count_24h,
        tx_count_7d=tx_count_7d,
        avg_amount_30d=Decimal(str(avg_amount_30d)),
        max_amount_30d=Decimal(str(max_amount_30d)),
        unique_merchants_24h=unique_merchants_24h,
        unique_countries_24h=unique_countries_24h,
        device_trust_score=device_trust_score,
        is_new_device=is_new_device,
        hour_of_day=hour_of_day,
        day_of_week=day_of_week,
        is_weekend=is_weekend,
        failed_attempt_count=failed_attempt_count,
        merchant_risk_score=merchant_risk_score,
    )


def _rule_result(
    score_adjustment: int = 0,
    rules_triggered: list[str] | None = None,
    actions: list[str] | None = None,
    decision: str = "approve",
) -> dict:
    return {
        "score_adjustment": score_adjustment,
        "rules_triggered": rules_triggered or [],
        "actions": actions or [],
        "decision": decision,
    }


@pytest.fixture
def engine() -> DecisionEngine:
    return DecisionEngine()


@pytest.fixture(autouse=True)
def disable_onnx(engine: DecisionEngine) -> None:
    """Disable ONNX ML scoring so tests only exercise the rule-based score path.

    The ONNX model may be loaded from disk during tests; patching is_ready()
    ensures the deterministic rule score formula is the sole score source,
    making every scenario assertion exact and reproducible without ML artifacts.
    """
    with patch.object(engine.onnx_service, "is_ready", return_value=False):
        yield


# ---------------------------------------------------------------------------
# Scenario 1 — Normal small transaction → approve
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scenario_normal_transaction_approves(engine: DecisionEngine) -> None:
    """A normal low-value transaction from a trusted device should be approved.

    Base score = amount_zscore*10 + (1 - device_trust_score)*20
               = 0.1*10 + (1 - 0.9)*20 = 1 + 2 = 3
    No rule adjustment → score 3 → approve (<=40).
    """
    features = _features(amount=30.0, amount_zscore=0.1, device_trust_score=0.9)
    rule = _rule_result(score_adjustment=0)

    with patch.object(engine, "_update_transaction_status", new=AsyncMock()):
        decision = await engine.make_decision(uuid4(), features, rule)

    assert decision.decision == "approve"
    assert decision.score <= 40


# ---------------------------------------------------------------------------
# Scenario 2 — Large / unusual amount → elevated score (verify or block)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scenario_large_amount_elevated_score(engine: DecisionEngine) -> None:
    """A large amount with a high z-score and rule adjustment elevates score.

    Base score = 3.5*10 + (1-0.9)*20 = 35 + 2 = 37
    Rule adjustment for 'high_amount' = +35  → score 72 → block (>=71).

    The rule score_adjustment simulates the rule engine raising the score for an
    amount well outside the user's historical range (z-score 3.5).
    """
    features = _features(
        amount=5000.0,
        amount_zscore=3.5,
        device_trust_score=0.9,
    )
    rule = _rule_result(
        score_adjustment=35,
        rules_triggered=["high_amount"],
        actions=["score_adjustment"],
    )

    with patch.object(engine, "_update_transaction_status", new=AsyncMock()):
        decision = await engine.make_decision(uuid4(), features, rule)

    # A large-amount transaction should be at least challenged, not approved.
    assert decision.decision in ("verify", "block")
    assert decision.score > 40


# ---------------------------------------------------------------------------
# Scenario 3 — New device → is_new_device raises risk
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scenario_new_device_raises_risk(engine: DecisionEngine) -> None:
    """New device login should contribute to a higher score than a known device.

    device_trust_score=0.1 (new device → low trust).
    Base score = 0.5*10 + (1-0.1)*20 = 5 + 18 = 23
    Rule 'new_device' adds +25 → score 48 → verify (41-70).
    """
    features = _features(
        amount_zscore=0.5,
        device_trust_score=0.1,
        is_new_device=True,
    )
    rule = _rule_result(
        score_adjustment=25,
        rules_triggered=["new_device"],
        actions=["score_adjustment"],
    )

    with patch.object(engine, "_update_transaction_status", new=AsyncMock()):
        decision = await engine.make_decision(uuid4(), features, rule)

    assert decision.decision in ("verify", "block")
    assert decision.score > 40


def test_scenario_new_device_feature_flag() -> None:
    """is_new_device=True should be surfaced as True in the feature vector."""
    features = _features(is_new_device=True, device_trust_score=0.15)
    assert features.is_new_device is True
    # Low device trust also contributes; verify score contribution is non-trivial.
    base = features.amount_zscore * 10 + (1.0 - features.device_trust_score) * 20
    # Base from device alone: (1-0.15)*20 = 17; already higher than a trusted device
    assert base >= 17.0


# ---------------------------------------------------------------------------
# Scenario 4 — Multiple failed attempts → failed_attempt_count raises risk
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scenario_multiple_failed_attempts(engine: DecisionEngine) -> None:
    """Repeated recent failures should escalate the decision.

    Base score = 0.2*10 + (1-0.8)*20 = 2 + 4 = 6
    Rule 'failed_attempts' adds +40 → score 46 → verify (41-70).
    """
    features = _features(
        amount_zscore=0.2,
        device_trust_score=0.8,
        failed_attempt_count=4,
    )
    rule = _rule_result(
        score_adjustment=40,
        rules_triggered=["failed_attempts"],
        actions=["score_adjustment"],
    )

    with patch.object(engine, "_update_transaction_status", new=AsyncMock()):
        decision = await engine.make_decision(uuid4(), features, rule)

    assert decision.decision in ("verify", "block")
    assert decision.score > 40


def test_scenario_failed_attempt_count_feature() -> None:
    """failed_attempt_count is captured correctly in the feature vector."""
    features = _features(failed_attempt_count=5)
    assert features.failed_attempt_count == 5


# ---------------------------------------------------------------------------
# Scenario 5 — Velocity: many transactions in a short time
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scenario_velocity_raises_risk(engine: DecisionEngine) -> None:
    """High tx_count_1h / tx_count_24h signals velocity fraud.

    Base score = 0.3*10 + (1-0.85)*20 = 3 + 3 = 6
    Rule 'high_velocity' adds +50 → score 56 → verify (41-70).
    """
    features = _features(
        amount_zscore=0.3,
        device_trust_score=0.85,
        tx_count_1h=10,
        tx_count_24h=25,
    )
    rule = _rule_result(
        score_adjustment=50,
        rules_triggered=["high_velocity"],
        actions=["score_adjustment"],
    )

    with patch.object(engine, "_update_transaction_status", new=AsyncMock()):
        decision = await engine.make_decision(uuid4(), features, rule)

    assert decision.decision in ("verify", "block")
    assert decision.score > 40


@pytest.mark.asyncio
async def test_scenario_velocity_rule_condition_triggers() -> None:
    """The rule evaluator triggers on tx_count_1h > 8."""
    condition = {"field": "tx_count_1h", "op": "gt", "value": 8}
    context_high_velocity = {"tx_count_1h": 10}
    context_normal = {"tx_count_1h": 2}

    assert await evaluate_condition(condition, context_high_velocity) is True
    assert await evaluate_condition(condition, context_normal) is False


# ---------------------------------------------------------------------------
# Scenario 6 — Blacklisted location / high-risk merchant
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scenario_blacklisted_location_blocks(engine: DecisionEngine) -> None:
    """A transaction from a blocked merchant/location should be blocked.

    Rule 'blacklisted_merchant' fires with action='block', forcing score→100.
    The rule engine short-circuits and sets decision='block'; here we simulate
    a large adjustment to confirm the engine maps it to block.
    """
    features = _features(
        amount_zscore=0.5,
        device_trust_score=0.8,
        merchant_risk_score=1.0,
    )
    rule = _rule_result(
        score_adjustment=91,  # base ~9 + 91 = 100 → block
        rules_triggered=["blacklisted_merchant"],
        actions=["score_adjustment"],
    )

    with patch.object(engine, "_update_transaction_status", new=AsyncMock()):
        decision = await engine.make_decision(uuid4(), features, rule)

    assert decision.decision == "block"
    assert decision.score >= 71


@pytest.mark.asyncio
async def test_scenario_blacklisted_location_rule_condition() -> None:
    """Rule evaluator fires when merchant_id is in a blacklisted set."""
    condition = {
        "field": "merchant_id",
        "op": "in",
        "value": ["BLOCKED_MERCH_001", "BLOCKED_MERCH_002"],
    }
    assert (
        await evaluate_condition(condition, {"merchant_id": "BLOCKED_MERCH_001"})
        is True
    )
    assert (
        await evaluate_condition(condition, {"merchant_id": "LEGIT_MERCH_999"}) is False
    )


@pytest.mark.asyncio
async def test_scenario_high_risk_merchant_score() -> None:
    """merchant_risk_score=1.0 is stored correctly in the feature vector."""
    features = _features(merchant_risk_score=1.0)
    assert features.merchant_risk_score == 1.0


# ---------------------------------------------------------------------------
# Scenario 7 — False-positive scenario: legitimate-looking transaction
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scenario_false_positive_avoided(engine: DecisionEngine) -> None:
    """A transaction that superficially looks risky but is legitimate → approve.

    Avoidance mechanism: the user has a long history (low z-score), trusted
    device, no recent failures, and the rule engine fires no adjustments.
    A slightly above-average amount (z=0.8) on a known device is common for
    the user and the system should approve it, not challenge it.

    This documents the false-positive avoidance path: the amount deviation
    alone is not enough to cross the verify threshold when all other signals
    are clean.

    Base score = 0.8*10 + (1-0.95)*20 = 8 + 1 = 9 → approve (<=40).
    """
    features = _features(
        amount=200.0,
        amount_zscore=0.8,  # slightly above avg but within normal range
        device_trust_score=0.95,  # well-known device
        is_new_device=False,
        tx_count_1h=1,
        tx_count_24h=3,
        failed_attempt_count=0,
        merchant_risk_score=0.0,
    )
    rule = _rule_result(score_adjustment=0)  # no rules triggered

    with patch.object(engine, "_update_transaction_status", new=AsyncMock()):
        decision = await engine.make_decision(uuid4(), features, rule)

    assert decision.decision == "approve", (
        f"False positive: legitimate transaction was incorrectly decided as "
        f"'{decision.decision}' (score={decision.score}). "
        "When all signals are clean, the system must approve."
    )
    assert decision.score <= 40
