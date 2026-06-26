"""Rule engine for fraud detection.

Loads active rules from the database (with Redis caching), evaluates
transactions against them in priority order, and returns a decision.
"""

from __future__ import annotations

import logging
import time
from typing import Any, cast
from uuid import UUID

from sqlalchemy import select

from app.config import settings
from app.infrastructure.database import get_session_maker
from app.models import FraudRule
from app.services.cache import Cache
from app.services.key_builder import KeyBuilder
from app.services.rule_evaluator import evaluate_condition

logger = logging.getLogger(__name__)

RULE_CACHE_TTL = 60  # seconds


class RuleEngine:
    """Evaluates transactions against fraud detection rules."""

    def __init__(self) -> None:
        self.cache = Cache()
        self._last_refresh = 0.0
        self._rules_cache: list[dict[str, Any]] = []

    async def evaluate_transaction(
        self, transaction_data: dict, owner_id: UUID | None = None
    ) -> dict[str, Any]:
        """Evaluate a transaction against active rules for the account owner.

        Args:
            transaction_data: Dict containing transaction fields.
            owner_id: Account owner whose rule set should be applied.

        Returns:
            Dict with score_adjustment, rules_triggered, actions, and decision.
        """
        if owner_id is None:
            logger.warning("rule_eval_missing_owner_id")
            return {
                "score_adjustment": 0,
                "rules_triggered": [],
                "actions": [],
                "decision": "approve",
            }

        rules = await self.get_active_rules(owner_id)
        context = transaction_data

        result: dict[str, Any] = {
            "score_adjustment": 0,
            "rules_triggered": [],
            "actions": [],
            "decision": "approve",
        }

        for rule in rules:
            if await self._evaluate_rule(rule, context):
                result["rules_triggered"].append(rule["name"])

                action = str(rule.get("action", "")).strip().lower()
                score_value = int(rule.get("score_value", 0) or 0)
                if action in ("block", "reject", "deny"):
                    block_bump = max(score_value, settings.verify_threshold + 1)
                    result["score_adjustment"] += block_bump
                    result["actions"].append("block")
                    result["decision"] = "block"
                    break  # Short-circuit
                if action in ("allow", "approve"):
                    result["actions"].append(action)
                    result["decision"] = "approve"
                    break  # Short-circuit
                if action == "score_adjustment":
                    result["score_adjustment"] += score_value
                    result["actions"].append("score_adjustment")
                if action == "verify":
                    verify_bump = max(score_value, settings.approve_threshold + 1)
                    result["score_adjustment"] += verify_bump
                    result["actions"].append("verify")
                    if result["decision"] != "block":
                        result["decision"] = "verify"

        return result

    async def load_rules(self, owner_id: UUID) -> list[dict[str, Any]]:
        """Load active rules for an owner from the database ordered by priority.

        Returns:
            List of rule dicts.
        """
        session_maker = get_session_maker()
        if session_maker is None:
            logger.warning("database_not_initialized")
            return []

        try:
            async with session_maker() as session:
                stmt = (
                    select(FraudRule)
                    .where(
                        FraudRule.is_active.is_(True),
                        FraudRule.owner_id == owner_id,
                    )
                    .order_by(FraudRule.priority.asc())
                )
                result = await session.execute(stmt)
                rules = result.scalars().all()
                return [_rule_to_dict(rule) for rule in rules]
        except Exception as exc:
            logger.warning("load_rules_failed", extra={"error": str(exc)})
            return []

    async def _evaluate_rule(self, rule: dict[str, Any], context: dict) -> bool:
        """Evaluate a single rule's conditions against the context.

        Args:
            rule: Rule dict with a "conditions" key.
            context: Transaction context dict.

        Returns:
            True if the rule conditions are satisfied.
        """
        conditions = rule.get("conditions")
        if not conditions:
            return False
        return await evaluate_condition(conditions, context)

    async def get_active_rules(self, owner_id: UUID) -> list[dict[str, Any]]:
        """Get cached active rules for an owner, refreshing from DB if needed.

        Uses Redis cache with a 60-second TTL. Falls back to the
        in-memory cache if Redis is unavailable.

        Returns:
            List of active rule dicts ordered by priority.
        """
        cache_key = KeyBuilder.fraud_rules(str(owner_id))

        # Try Redis cache first
        cached = await self.cache.get(cache_key)
        if cached is not None and isinstance(cached, list):
            self._rules_cache = cast("list[dict[str, Any]]", cached)
            self._last_refresh = time.time()
            return self._rules_cache

        # Load from DB and populate caches
        rules = await self.load_rules(owner_id)
        self._rules_cache = rules
        self._last_refresh = time.time()
        await self.cache.set(cache_key, rules, ttl=RULE_CACHE_TTL)
        return rules

    async def invalidate_rules_cache(self, owner_id: UUID) -> None:
        """Clear cached rules for an owner after CRUD changes."""
        cache_key = KeyBuilder.fraud_rules(str(owner_id))
        await self.cache.delete(cache_key)
        self._rules_cache = []
        self._last_refresh = 0.0


def _rule_to_dict(rule: FraudRule) -> dict[str, Any]:
    """Convert a FraudRule ORM object to a plain dict."""
    return {
        "id": str(rule.id) if rule.id is not None else None,
        "name": rule.name,
        "description": rule.description,
        "rule_type": rule.rule_type,
        "conditions": rule.conditions,
        "action": rule.action,
        "priority": rule.priority,
        "is_active": rule.is_active,
        "score_value": rule.score_value,
    }
