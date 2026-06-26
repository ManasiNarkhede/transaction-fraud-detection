"""Orchestration service for the live transaction ingestion flow.

Implements the spec Data Flow for a single transaction:
  1. transaction enters        -> persist as pending
  2. checked against history   -> server-side feature engineering
  3. AI/ML risk score          -> DecisionEngine (ML primary, rule fallback)
  4. rules engine thresholds   -> DecisionEngine threshold mapping
  5/6/7. approve/verify/block  -> Decision + status update
  8. alert  / 9. audit         -> published by DecisionEngine (streams + audit)

The router stays thin; all orchestration lives here.
"""

from __future__ import annotations

import asyncio
import logging
import math
from datetime import UTC, datetime
from time import perf_counter
from uuid import UUID

from app.infrastructure.database import get_session_maker
from app.models.decision import Decision
from app.repositories.transaction_repository import TransactionRepository
from app.schemas.transaction import (
    TransactionDecisionResponse,
    TransactionIngestRequest,
)
from app.services.alert_service import AlertService
from app.services.audit_service import AuditService
from app.services.decision_engine import DecisionEngine
from app.services.feature_engineering import FeatureEngineeringService
from app.services.rule_engine import RuleEngine
from app.services.verification_service import VerificationService

logger = logging.getLogger(__name__)


class TransactionIngestService:
    """Coordinates persistence, feature engineering, and scoring."""

    def __init__(
        self,
        feature_service: FeatureEngineeringService | None = None,
        rule_engine: RuleEngine | None = None,
        decision_engine: DecisionEngine | None = None,
    ) -> None:
        self.feature_service = feature_service or FeatureEngineeringService()
        self.rule_engine = rule_engine or RuleEngine()
        self.decision_engine = decision_engine or DecisionEngine()

    async def ingest(
        self, request: TransactionIngestRequest, owner_id: UUID
    ) -> TransactionDecisionResponse:
        """Run the full ingestion flow and return the decision."""
        session_maker = get_session_maker()
        if session_maker is None:
            raise RuntimeError("Database session maker is not initialized")

        timestamp = request.transaction_time or datetime.now(UTC)

        # 1. Persist the incoming transaction (pending).
        async with session_maker() as session:
            repo = TransactionRepository(session)
            transaction = await repo.create_transaction(
                user_id=owner_id,
                owner_id=owner_id,
                amount=request.amount,
                currency=request.currency,
                merchant_id=request.merchant_id,
                merchant_category=request.merchant_category,
                ip_address=request.ip_address,
                device_fingerprint=request.device_id,
                card_last_four=request.card_last_four,
            )
            transaction_id = transaction.id

            # 2. Compute features server-side from this transaction + history.
            features = await self.feature_service.compute_features_from_db(
                session=session,
                user_id=owner_id,
                amount=request.amount,
                fingerprint=request.device_id or "",
                merchant_id=request.merchant_id or "",
                timestamp=timestamp,
                transaction_id=transaction_id,
            )

        # Cache the freshly computed vector for reuse by other consumers.
        try:
            await self.feature_service.cache_features(owner_id, features)
        except Exception as exc:  # caching is best-effort
            logger.warning(
                "feature_cache_failed",
                extra={"user_id": str(owner_id), "error": str(exc)},
            )

        # 3/4. Rule evaluation feeds the decision engine (ML primary + thresholds).
        rule_result = await self.rule_engine.evaluate_transaction(
            self._build_rule_context(request, timestamp, owner_id),
            owner_id=owner_id,
        )

        # 5/6/7 + 8/9: DecisionEngine scores, maps thresholds, updates status,
        # and fires audit/stream/alert/verification (fire-and-forget).
        _decision_start = perf_counter()
        decision: Decision = await self.decision_engine.make_decision(
            transaction_id=transaction_id,
            features=features,
            rule_result=rule_result,
        )
        decision_latency_ms: int = math.ceil((perf_counter() - _decision_start) * 1000)

        try:
            await AuditService.log_decision(
                transaction_id=transaction_id,
                decision=decision.decision,
                score=decision.score,
                reason=decision.reason,
                features=features.model_dump(mode="json"),
                rules_triggered=decision.rules_triggered,
                model_version=None,
                owner_id=owner_id,
            )
        except Exception as exc:
            logger.exception(
                "audit_log_failed",
                extra={"transaction_id": str(transaction_id), "error": str(exc)},
            )

        # Persist the fraud score + feature snapshot (JSON-safe).
        try:
            score_session_maker = get_session_maker()
            if score_session_maker is not None:
                async with score_session_maker() as session:
                    repo = TransactionRepository(session)
                    await repo.save_fraud_score(
                        transaction_id=transaction_id,
                        user_id=owner_id,
                        score=decision.score,
                        features_used=features.model_dump(mode="json"),
                        decision_latency_ms=decision_latency_ms,
                    )
        except Exception as exc:  # scoring persistence is non-fatal
            logger.warning(
                "fraud_score_persist_failed",
                extra={"transaction_id": str(transaction_id), "error": str(exc)},
            )

        if decision.decision == "verify":
            try:
                verify_session_maker = get_session_maker()
                if verify_session_maker is not None:
                    async with verify_session_maker() as session:
                        verification_service = VerificationService()
                        await (
                            verification_service.create_pending_for_verify_transaction(
                                session=session,
                                transaction_id=transaction_id,
                                owner_id=owner_id,
                            )
                        )
            except Exception as exc:
                logger.warning(
                    "verification_pending_create_failed",
                    extra={"transaction_id": str(transaction_id), "error": str(exc)},
                )

        if decision.decision in ("block", "verify"):
            asyncio.create_task(
                self._send_decision_alert(
                    transaction_id=transaction_id,
                    owner_id=owner_id,
                    decision=decision.decision,
                    score=decision.score,
                    reason=decision.reason,
                )
            )

        return TransactionDecisionResponse(
            transaction_id=transaction_id,
            decision=decision.decision,
            score=decision.score,
            reason=decision.reason,
            rules_triggered=decision.rules_triggered,
            requires_verification=decision.decision == "verify",
        )

    @staticmethod
    async def _send_decision_alert(
        *,
        transaction_id: UUID,
        owner_id: UUID,
        decision: str,
        score: int,
        reason: str,
    ) -> None:
        """Send alerts in the background so ingest can return before SMS/email."""
        try:
            await AlertService.record_decision_alert(
                transaction_id=transaction_id,
                owner_id=owner_id,
                decision=decision,
                score=score,
                reason=reason,
            )
        except Exception as exc:
            logger.warning(
                "decision_alert_create_failed",
                extra={"transaction_id": str(transaction_id), "error": str(exc)},
            )

    @staticmethod
    def _build_rule_context(
        request: TransactionIngestRequest, timestamp: datetime, owner_id: UUID
    ) -> dict:
        """Flatten the request into a dict the rule engine can evaluate."""
        return {
            "user_id": str(owner_id),
            "amount": float(request.amount),
            "currency": request.currency,
            "merchant_id": request.merchant_id,
            "merchant_category": request.merchant_category,
            "location": request.location,
            "device_id": request.device_id,
            "ip_address": request.ip_address,
            "payment_method": request.payment_method,
            "hour_of_day": timestamp.hour,
        }
