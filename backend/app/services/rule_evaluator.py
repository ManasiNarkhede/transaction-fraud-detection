"""Condition evaluator for fraud detection rules.

Supports field-based operators and logical combinators with
short-circuit evaluation.
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)


async def evaluate_condition(condition: dict, context: dict) -> bool:
    """Evaluate a condition against a context dictionary.

    Args:
        condition: A condition dict. May contain:
            - A logical combinator: {"and": [...]}, {"or": [...]}, {"not": {...}}
            - A field operator: {"field": "amount", "op": "gt", "value": 1000}
        context: A dict with field values (e.g., {"amount": 1500}).

    Returns:
        True if the condition is satisfied, False otherwise.
        Missing fields cause the condition to evaluate to False.
    """
    if not isinstance(condition, dict):
        return False  # type: ignore[unreachable]

    # Logical combinators
    if "and" in condition:
        return await _evaluate_and(condition["and"], context)
    if "or" in condition:
        return await _evaluate_or(condition["or"], context)
    if "not" in condition:
        return await _evaluate_not(condition["not"], context)

    # Field operator
    if "field" in condition and "op" in condition:
        return await _evaluate_field_condition(condition, context)

    return False


async def _evaluate_and(conditions: list, context: dict) -> bool:
    """Evaluate AND with short-circuit."""
    if not isinstance(conditions, list):
        return False  # type: ignore[unreachable]
    for sub in conditions:
        if not await evaluate_condition(sub, context):
            return False
    return True


async def _evaluate_or(conditions: list, context: dict) -> bool:
    """Evaluate OR with short-circuit."""
    if not isinstance(conditions, list):
        return False  # type: ignore[unreachable]
    for sub in conditions:
        if await evaluate_condition(sub, context):
            return True
    return False


async def _evaluate_not(condition: dict, context: dict) -> bool:
    """Evaluate NOT."""
    return not await evaluate_condition(condition, context)


async def _evaluate_field_condition(condition: dict, context: dict) -> bool:
    """Evaluate a single field condition."""
    field = condition.get("field")
    op = condition.get("op")
    expected = condition.get("value")

    if field is None or op is None:
        return False

    if field not in context:
        return False

    actual = context[field]

    try:
        if op == "eq":
            return bool(actual == expected)
        if op == "ne":
            return bool(actual != expected)
        if op == "gt":
            return bool(actual > expected)
        if op == "lt":
            return bool(actual < expected)
        if op == "gte":
            return bool(actual >= expected)
        if op == "lte":
            return bool(actual <= expected)
        if op == "in":
            if isinstance(expected, list | tuple | set | str):
                return actual in expected
            return False
        if op == "not_in":
            if isinstance(expected, list | tuple | set | str):
                return actual not in expected
            return False
        if op == "regex":
            if expected is None:
                return False
            pattern = str(expected)
            text_value = str(actual) if actual is not None else ""
            return re.search(pattern, text_value) is not None
        if op == "contains":
            if expected is None:
                return False
            if isinstance(actual, str):
                return str(expected) in actual
            if isinstance(actual, list | tuple | set):
                return expected in actual
            if isinstance(actual, dict):
                return expected in actual
            return False
    except Exception as exc:
        logger.warning(
            "condition_evaluation_failed",
            extra={
                "field": field,
                "op": op,
                "actual": actual,
                "expected": expected,
                "error": str(exc),
            },
        )
        return False

    return False
