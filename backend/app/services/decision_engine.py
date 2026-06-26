"""Decision engine for fraud detection.

Calculates a fraud risk score from features and rule results, maps the score
to a decision (approve / verify / block), and updates the transaction status
in the database.
"""

from __future__ import annotations

import asyncio
import logging
import math
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.infrastructure.database import get_session_maker
from app.models.decision import Decision
from app.models.feature_vector import FeatureVector
from app.models.transaction import Transaction
from app.repositories.blocked_transaction_repository import (
    BlockedTransactionRepository,
)
from app.services.onnx_inference import ONNXInferenceService
from app.services.stream_producer import RedisStreamProducer

logger = logging.getLogger(__name__)


class DecisionEngine:
    """Evaluates transactions and produces approve/verify/block decisions."""

    def __init__(self) -> None:
        """Load decision thresholds from application settings."""
        self.approve_threshold = settings.approve_threshold
        self.verify_threshold = settings.verify_threshold
        self.block_threshold = settings.block_threshold
        self.ml_rule_weight = settings.ml_rule_weight
        self.ml_model_weight = settings.ml_model_weight
        self.onnx_service = ONNXInferenceService(model_dir=settings.model_dir)
        self.stream_producer = RedisStreamProducer()

    async def make_decision(
        self,
        transaction_id: UUID,
        features: FeatureVector,
        rule_result: dict[str, Any],
    ) -> Decision:
        """Evaluate a transaction and return a Decision.

        Args:
            transaction_id: The UUID of the transaction being evaluated.
            features: Engineered feature vector for the transaction.
            rule_result: Output from the RuleEngine containing score
                adjustments, triggered rules, and actions.

        Returns:
            A Decision object with score, decision, reason, and metadata.
        """
        try:
            score = self._calculate_score(features, rule_result)
            decision = self._determine_decision(score)
            score, decision = self._apply_rule_decision_override(
                score, decision, rule_result
            )
            reason = self._generate_reason(rule_result, features, score)

            # Update transaction status in the database
            user_id: UUID | None = None
            session_maker = get_session_maker()
            if session_maker is not None:
                async with session_maker() as session:
                    user_id = await self._update_transaction_status(
                        session, transaction_id, decision, score, reason, rule_result
                    )
            else:
                logger.warning(
                    "database_not_initialized",
                    extra={"transaction_id": str(transaction_id)},
                )

            decision_obj = Decision(
                transaction_id=transaction_id,
                score=score,
                decision=decision,
                reason=reason,
                rules_triggered=rule_result.get("rules_triggered", []),
                features_used=features.model_dump(mode="json"),
            )

            # Publish to streams (fire-and-forget)
            try:
                asyncio.create_task(
                    self.stream_producer.publish_scoring_result(
                        transaction_id,
                        decision,
                        score,
                        reason,
                        features.model_dump(mode="json"),
                    )
                )
                if decision in ["block", "verify"]:
                    asyncio.create_task(
                        self.stream_producer.publish_alert(
                            transaction_id, decision, score, reason, user_id=user_id
                        )
                    )
                asyncio.create_task(
                    self.stream_producer.publish_dashboard_update(
                        transaction_id, {"decision": decision, "score": score}
                    )
                )
            except Exception as exc:
                logger.warning(
                    "stream_publish_fire_and_forget_failed",
                    extra={
                        "transaction_id": str(transaction_id),
                        "error": str(exc),
                    },
                )

            # Fire-and-forget verification creation for "verify" decisions
            # Pending verification rows are created synchronously in TransactionIngestService.

            return decision_obj
        except Exception as exc:
            logger.exception(
                "decision_engine_error",
                extra={
                    "transaction_id": str(transaction_id),
                    "error": str(exc),
                },
            )
            score, decision = self._fallback_from_rules(rule_result)
            reason = (
                f"Scoring error fallback. "
                f"{self._generate_reason(rule_result, features, score)}"
            )
            session_maker = get_session_maker()
            if session_maker is not None:
                async with session_maker() as session:
                    await self._update_transaction_status(
                        session,
                        transaction_id,
                        decision,
                        score,
                        reason,
                        rule_result,
                    )
            return Decision(
                transaction_id=transaction_id,
                score=score,
                decision=decision,
                reason=reason,
                rules_triggered=rule_result.get("rules_triggered", []),
                features_used=features.model_dump(mode="json"),
            )

    def _calculate_score(
        self, features: FeatureVector, rule_result: dict[str, Any]
    ) -> int:
        """Calculate the final fraud risk score.

        Base score is derived from:
            - amount_zscore * 10
            - (1 - device_trust_score) * 20  (device risk)

        Rule score adjustments are added on top. If ONNX models are loaded
        and ML is enabled, the rule score is combined with the ML ensemble
        score using configurable weights.

        Args:
            features: Feature vector for the transaction.
            rule_result: Rule engine output with score_adjustment.

        Returns:
            Integer score between 0 and 100 (inclusive).
        """
        base_score = (
            features.amount_zscore * 10 + (1.0 - features.device_trust_score) * 20
        )
        adjustment = rule_result.get("score_adjustment", 0)
        rule_score = self._clamp_score(float(base_score) + float(adjustment))

        # Attempt ML scoring if models are available
        ml_score: float | None = None
        if settings.ml_enabled and self.onnx_service.is_ready():
            try:
                features_dict = features.model_dump()
                # Convert Decimal values to float for ONNX
                for key, value in features_dict.items():
                    if hasattr(value, "__float__"):
                        features_dict[key] = float(value)

                prediction = self.onnx_service.predict(features_dict)
                raw_ml = float(prediction["ensemble_score"]) * 100
                if math.isfinite(raw_ml):
                    ml_score = raw_ml
                logger.info(
                    "ml_score_computed",
                    extra={
                        "rule_score": rule_score,
                        "ml_score": ml_score,
                        "ensemble_score": prediction["ensemble_score"],
                    },
                )
            except Exception as exc:
                logger.warning(
                    "ml_scoring_failed",
                    extra={"error": str(exc)},
                )

        if ml_score is not None:
            combined_score = (
                self.ml_rule_weight * rule_score + self.ml_model_weight * ml_score
            )
            return self._clamp_score(combined_score)

        return rule_score

    @staticmethod
    def _clamp_score(raw: float) -> int:
        """Convert a raw score to an integer in [0, 100], guarding NaN/Inf."""
        if not math.isfinite(raw):
            return 0
        return max(0, min(100, int(raw)))

    def _fallback_from_rules(self, rule_result: dict[str, Any]) -> tuple[int, str]:
        """Derive decision/score from rule output when scoring raises unexpectedly."""
        actions = rule_result.get("actions", [])
        rule_decision = rule_result.get("decision", "approve")

        if "block" in actions or rule_decision == "block":
            return max(self.verify_threshold + 1, self.block_threshold), "block"
        if "verify" in actions or rule_decision == "verify":
            return self.approve_threshold + 1, "verify"
        if any(action in ("allow", "approve") for action in actions):
            return self.approve_threshold, "approve"
        return 50, "verify"

    def _apply_rule_decision_override(
        self, score: int, decision: str, rule_result: dict[str, Any]
    ) -> tuple[int, str]:
        """Apply rule-engine decisions that must override score thresholds.

        Block and verify rules are authoritative when their actions fired.
        Approve/allow applies only when a matching whitelist rule explicitly
        ran (present in ``actions``), not for the default no-rule state.
        """
        actions = rule_result.get("actions", [])
        rule_decision = rule_result.get("decision", "approve")

        if "block" in actions or rule_decision == "block":
            return max(score, self.block_threshold), "block"

        if ("verify" in actions or rule_decision == "verify") and decision != "block":
            return max(score, self.approve_threshold + 1), "verify"

        if any(action in ("allow", "approve") for action in actions):
            return min(score, self.approve_threshold), "approve"

        return score, decision

    def _determine_decision(self, score: int) -> str:
        """Map a score to a decision string.

        Thresholds (inclusive):
            - 0  .. 40  -> approve
            - 41 .. 70  -> verify
            - 71 .. 100 -> block

        Args:
            score: Fraud risk score (0-100).

        Returns:
            One of "approve", "verify", or "block".
        """
        if score <= self.approve_threshold:
            return "approve"
        if score <= self.verify_threshold:
            return "verify"
        return "block"

    def _generate_reason(
        self,
        rule_result: dict[str, Any],
        features: FeatureVector,
        score: int,
    ) -> str:
        """Generate a human-readable reason for the decision.

        Args:
            rule_result: Rule engine output with triggered rules.
            features: Feature vector for feature highlights.
            score: Final fraud risk score.

        Returns:
            Human-readable explanation string.
        """
        rules_triggered = rule_result.get("rules_triggered", [])

        if rules_triggered:
            reason = " + ".join(rules_triggered)
        else:
            reason = "No risk signals detected"

        # Include feature highlights for high scores
        if score > self.verify_threshold:
            highlights = []
            if features.amount_zscore > 2.0:
                highlights.append(f"amount_zscore={features.amount_zscore:.2f}")
            if features.device_trust_score < 0.5:
                highlights.append(
                    f"device_trust_score={features.device_trust_score:.2f}"
                )
            if features.tx_count_1h > 5:
                highlights.append(f"tx_count_1h={features.tx_count_1h}")
            if highlights:
                reason += f" | Highlights: {', '.join(highlights)}"

        return reason

    async def _update_transaction_status(
        self,
        session: AsyncSession,
        transaction_id: UUID,
        decision: str,
        score: int,
        reason: str,
        rule_result: dict[str, Any],
    ) -> UUID | None:
        """Update the transaction's status and record blocks.

        When the decision is ``block`` this is the single finalization point:
        the transaction status is set to ``block`` and a ``BlockedTransaction``
        row is persisted via :class:`BlockedTransactionRepository`.

        Args:
            session: Active async SQLAlchemy session.
            transaction_id: UUID of the transaction to update.
            decision: Decision string to set as the transaction status.
            score: Fraud risk score (0-100), used in the block reason.
            reason: Human-readable reason for the decision.
            rule_result: Rule engine output (for triggered rule names).

        Returns:
            The transaction's ``user_id`` if found, otherwise ``None``.
        """
        stmt = select(Transaction).where(Transaction.id == transaction_id)
        result = await session.execute(stmt)
        transaction = result.scalar_one_or_none()

        if transaction is None:
            logger.warning(
                "transaction_not_found_for_status_update",
                extra={"transaction_id": str(transaction_id)},
            )
            return None

        transaction.status = decision

        if decision == "block":
            rules_triggered = rule_result.get("rules_triggered", [])
            rule_triggered = ", ".join(rules_triggered) if rules_triggered else None
            try:
                repo = BlockedTransactionRepository(session)
                await repo.stage_block(
                    transaction_id=transaction_id,
                    user_id=transaction.user_id,
                    reason=f"{reason} (score={score})",
                    rule_triggered=rule_triggered,
                )
            except Exception as block_exc:
                logger.warning(
                    "blocked_transaction_persist_failed",
                    extra={
                        "transaction_id": str(transaction_id),
                        "error": str(block_exc),
                    },
                )

        await session.commit()
        logger.info(
            "transaction_status_updated",
            extra={"transaction_id": str(transaction_id), "status": decision},
        )

        return transaction.user_id
