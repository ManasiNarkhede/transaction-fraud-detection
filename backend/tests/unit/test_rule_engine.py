"""Unit tests for the rule engine and condition evaluator."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.services.rule_engine import RuleEngine
from app.services.rule_evaluator import evaluate_condition

# ---------------------------------------------------------------------------
# Condition evaluator tests — field operators
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_evaluate_condition_eq() -> None:
    """Test the eq operator."""
    condition = {"field": "amount", "op": "eq", "value": 100}
    assert await evaluate_condition(condition, {"amount": 100}) is True
    assert await evaluate_condition(condition, {"amount": 200}) is False


@pytest.mark.asyncio
async def test_evaluate_condition_gt() -> None:
    """Test the gt operator."""
    condition = {"field": "amount", "op": "gt", "value": 100}
    assert await evaluate_condition(condition, {"amount": 200}) is True
    assert await evaluate_condition(condition, {"amount": 50}) is False


@pytest.mark.asyncio
async def test_evaluate_condition_in() -> None:
    """Test the in operator."""
    condition = {"field": "country", "op": "in", "value": ["US", "CA"]}
    assert await evaluate_condition(condition, {"country": "US"}) is True
    assert await evaluate_condition(condition, {"country": "UK"}) is False


@pytest.mark.asyncio
async def test_evaluate_condition_regex() -> None:
    """Test the regex operator."""
    condition = {"field": "email", "op": "regex", "value": r"@example\.com$"}
    assert await evaluate_condition(condition, {"email": "user@example.com"}) is True
    assert await evaluate_condition(condition, {"email": "user@other.com"}) is False


# ---------------------------------------------------------------------------
# Condition evaluator tests — logical combinators
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_evaluate_condition_and() -> None:
    """Test the AND combinator with short-circuit."""
    condition = {
        "and": [
            {"field": "amount", "op": "gt", "value": 100},
            {"field": "amount", "op": "lt", "value": 500},
        ]
    }
    assert await evaluate_condition(condition, {"amount": 200}) is True
    assert await evaluate_condition(condition, {"amount": 50}) is False
    assert await evaluate_condition(condition, {"amount": 600}) is False


@pytest.mark.asyncio
async def test_evaluate_condition_or() -> None:
    """Test the OR combinator with short-circuit."""
    condition = {
        "or": [
            {"field": "country", "op": "eq", "value": "US"},
            {"field": "country", "op": "eq", "value": "CA"},
        ]
    }
    assert await evaluate_condition(condition, {"country": "US"}) is True
    assert await evaluate_condition(condition, {"country": "CA"}) is True
    assert await evaluate_condition(condition, {"country": "UK"}) is False


@pytest.mark.asyncio
async def test_evaluate_condition_not() -> None:
    """Test the NOT combinator."""
    condition = {"not": {"field": "amount", "op": "eq", "value": 100}}
    assert await evaluate_condition(condition, {"amount": 200}) is True
    assert await evaluate_condition(condition, {"amount": 100}) is False


# ---------------------------------------------------------------------------
# RuleEngine tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rule_engine_block_action() -> None:
    """Test that a block action short-circuits evaluation."""
    engine = RuleEngine()
    rules: list[dict[str, Any]] = [
        {
            "name": "block_high_amount",
            "conditions": {"field": "amount", "op": "gt", "value": 1000},
            "action": "block",
            "priority": 1,
            "is_active": True,
            "score_value": 0,
        },
        {
            "name": "score_medium_amount",
            "conditions": {"field": "amount", "op": "gt", "value": 500},
            "action": "score_adjustment",
            "priority": 2,
            "is_active": True,
            "score_value": 50,
        },
    ]

    with patch.object(
        engine, "get_active_rules", new_callable=AsyncMock, return_value=rules
    ):
        result = await engine.evaluate_transaction({"amount": 1500}, owner_id=uuid4())

    assert result["decision"] == "block"
    assert "block" in result["actions"]
    assert result["rules_triggered"] == ["block_high_amount"]
    assert result["score_adjustment"] == 71


@pytest.mark.asyncio
async def test_rule_engine_score_adjustment() -> None:
    """Test that score_adjustment actions accumulate."""
    engine = RuleEngine()
    rules: list[dict[str, Any]] = [
        {
            "name": "score_1",
            "conditions": {"field": "amount", "op": "gt", "value": 100},
            "action": "score_adjustment",
            "priority": 1,
            "is_active": True,
            "score_value": 10,
        },
        {
            "name": "score_2",
            "conditions": {"field": "amount", "op": "gt", "value": 200},
            "action": "score_adjustment",
            "priority": 2,
            "is_active": True,
            "score_value": 20,
        },
    ]

    with patch.object(
        engine, "get_active_rules", new_callable=AsyncMock, return_value=rules
    ):
        result = await engine.evaluate_transaction({"amount": 300}, owner_id=uuid4())

    assert result["decision"] == "approve"
    assert result["score_adjustment"] == 30
    assert result["actions"] == ["score_adjustment", "score_adjustment"]
    assert result["rules_triggered"] == ["score_1", "score_2"]


@pytest.mark.asyncio
async def test_rule_engine_approve_action() -> None:
    """Test that approve action short-circuits evaluation."""
    engine = RuleEngine()
    rules: list[dict[str, Any]] = [
        {
            "name": "whitelist_small_amount",
            "conditions": {"field": "amount", "op": "lt", "value": 50},
            "action": "approve",
            "priority": 1,
            "is_active": True,
            "score_value": 0,
        },
    ]

    with patch.object(
        engine, "get_active_rules", new_callable=AsyncMock, return_value=rules
    ):
        result = await engine.evaluate_transaction({"amount": 10}, owner_id=uuid4())

    assert result["decision"] == "approve"
    assert "approve" in result["actions"]


@pytest.mark.asyncio
async def test_rule_engine_priority_order() -> None:
    """Test that rules are evaluated in priority order."""
    engine = RuleEngine()
    rules: list[dict[str, Any]] = [
        {
            "name": "high_priority",
            "conditions": {"field": "amount", "op": "gt", "value": 100},
            "action": "block",
            "priority": 1,
            "is_active": True,
            "score_value": 0,
        },
        {
            "name": "low_priority",
            "conditions": {"field": "amount", "op": "gt", "value": 100},
            "action": "score_adjustment",
            "priority": 10,
            "is_active": True,
            "score_value": 5,
        },
    ]

    with patch.object(
        engine, "get_active_rules", new_callable=AsyncMock, return_value=rules
    ):
        result = await engine.evaluate_transaction({"amount": 200}, owner_id=uuid4())

    assert result["decision"] == "block"
    assert result["rules_triggered"] == ["high_priority"]
