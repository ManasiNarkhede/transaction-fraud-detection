"""Audit service for tamper-evident fraud decision logging.

Provides hash-chained audit records so that any tampering with historical
decisions can be detected via verify_integrity().
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database import get_session_maker
from app.models.fraud_decision_audit import FraudDecisionAudit
from app.models.transaction import Transaction

logger = logging.getLogger(__name__)

# Fields that must never be persisted in the features JSONB
_PII_FIELDS = {"card_number", "cvv", "cardholder_name", "ssn", "password", "token"}


class AuditService:
    """Service for creating and querying fraud decision audit records."""

    @staticmethod
    def _sanitize_features(features: dict[str, Any]) -> dict[str, Any]:
        """Remove PII fields and make values JSON/JSONB-safe."""

        def _clean(value: Any) -> Any:
            if isinstance(value, Decimal):
                as_float = float(value)
                return as_float if math.isfinite(as_float) else None
            if isinstance(value, float):
                return value if math.isfinite(value) else None
            if isinstance(value, dict):
                return {
                    k: _clean(v)
                    for k, v in value.items()
                    if k.lower() not in _PII_FIELDS
                }
            if isinstance(value, list):
                return [_clean(item) for item in value]
            return value

        sanitized: dict[str, Any] = {}
        for key, value in features.items():
            if key.lower() not in _PII_FIELDS:
                sanitized[key] = _clean(value)
        return sanitized

    @staticmethod
    def _generate_hash(
        transaction_id: UUID,
        decision: str,
        score: int,
        reason: str,
        features: dict[str, Any],
        rules_triggered: list[str],
        model_version: str | None,
        previous_hash: str | None,
    ) -> str:
        """Generate a SHA-256 hash of the audit record data.

        Args:
            transaction_id: Transaction UUID.
            decision: Decision string (approve/verify/block).
            score: Fraud risk score.
            reason: Human-readable reason.
            features: Feature dictionary (already sanitized).
            rules_triggered: List of triggered rule names.
            model_version: Optional model version string.
            previous_hash: Hash of the previous record in the chain.

        Returns:
            Hexadecimal SHA-256 hash string.
        """
        data = {
            "transaction_id": str(transaction_id),
            "decision": decision,
            "score": score,
            "reason": reason,
            "features": features,
            "rules_triggered": rules_triggered,
            "model_version": model_version,
            "previous_hash": previous_hash,
        }
        serialized = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @classmethod
    async def log_decision(
        cls,
        transaction_id: UUID,
        decision: str,
        score: int,
        reason: str,
        features: dict[str, Any],
        rules_triggered: list[str],
        model_version: str | None = None,
        owner_id: UUID | None = None,
    ) -> FraudDecisionAudit | None:
        """Create an audit record for a fraud decision.

        Queries the most recent audit record to obtain the previous hash,
        computes the new record's hash, and persists it to the database.

        Args:
            transaction_id: Transaction UUID.
            decision: Decision string (approve/verify/block).
            score: Fraud risk score (0-100).
            reason: Human-readable reason.
            features: Feature dictionary (will be sanitized for PII).
            rules_triggered: List of triggered rule names.
            model_version: Optional model version string.

        Returns:
            The created FraudDecisionAudit record, or None on failure.
        """
        session_maker = get_session_maker()
        if session_maker is None:
            logger.warning(
                "audit_log_skipped_database_not_initialized",
                extra={"transaction_id": str(transaction_id)},
            )
            return None

        try:
            async with session_maker() as session:
                resolved_owner_id = owner_id
                if resolved_owner_id is None:
                    owner_stmt = select(Transaction.owner_id).where(
                        Transaction.id == transaction_id
                    )
                    owner_result = await session.execute(owner_stmt)
                    resolved_owner_id = owner_result.scalar_one_or_none()
                if resolved_owner_id is None:
                    logger.warning(
                        "audit_log_skipped_unknown_transaction",
                        extra={"transaction_id": str(transaction_id)},
                    )
                    return None

                previous_hash = await cls._get_previous_hash(session, resolved_owner_id)

                sanitized_features = cls._sanitize_features(features)
                normalized_rules = [str(rule) for rule in (rules_triggered or [])]

                record_hash = cls._generate_hash(
                    transaction_id=transaction_id,
                    decision=decision,
                    score=score,
                    reason=reason,
                    features=sanitized_features,
                    rules_triggered=normalized_rules,
                    model_version=model_version,
                    previous_hash=previous_hash,
                )

                audit = FraudDecisionAudit(
                    transaction_id=transaction_id,
                    decision=decision,
                    score=score,
                    reason=reason,
                    features=sanitized_features,
                    rules_triggered=normalized_rules,
                    model_version=model_version,
                    hash=record_hash,
                    previous_hash=previous_hash,
                )

                session.add(audit)
                await session.commit()
                await session.refresh(audit)

                logger.info(
                    "audit_record_created",
                    extra={
                        "transaction_id": str(transaction_id),
                        "audit_id": str(audit.id),
                        "hash": record_hash,
                    },
                )
                return audit
        except Exception as exc:
            logger.exception(
                "audit_log_failed",
                extra={
                    "transaction_id": str(transaction_id),
                    "error": str(exc),
                },
            )
            return None

    @classmethod
    async def log_override(
        cls,
        transaction_id: UUID,
        old_decision: str,
        new_decision: str,
        reason: str,
        analyst_id: UUID,
        score: int = 0,
        features: dict[str, Any] | None = None,
        rules_triggered: list[str] | None = None,
    ) -> FraudDecisionAudit | None:
        """Append an override audit record to the hash chain.

        The override is recorded as a new entry (append-only); the prior
        record is never mutated.  The reason field encodes
        ``OVERRIDE: <old> -> <new> by <analyst_id>``.

        Args:
            transaction_id: Transaction UUID.
            old_decision: The decision being overridden.
            new_decision: The new decision chosen by the analyst.
            reason: Human-readable reason for the override.
            analyst_id: UUID of the analyst performing the override.
            score: Risk score at time of override (default 0).
            features: Optional feature dict (will be sanitized).
            rules_triggered: Optional list of rules relevant to override.

        Returns:
            The created FraudDecisionAudit record, or None on failure.
        """
        override_reason = (
            f"OVERRIDE: {old_decision} -> {new_decision} "
            f"by analyst {analyst_id}. Reason: {reason}"
        )
        return await cls.log_decision(
            transaction_id=transaction_id,
            decision=new_decision,
            score=score,
            reason=override_reason,
            features=features or {},
            rules_triggered=rules_triggered or [],
        )

    @staticmethod
    async def _get_previous_hash(session: AsyncSession, owner_id: UUID) -> str | None:
        """Fetch the hash of the most recent audit record for an account owner.

        Args:
            session: Active async SQLAlchemy session.
            owner_id: Account owner UUID.

        Returns:
            The hash string of the most recent record for that owner, or None.
        """
        stmt = (
            select(FraudDecisionAudit.hash)
            .join(Transaction, Transaction.id == FraudDecisionAudit.transaction_id)
            .where(Transaction.owner_id == owner_id)
            .order_by(FraudDecisionAudit.created_at.desc())
            .limit(1)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_audit_by_transaction(
        transaction_id: UUID,
        owner_id: UUID | None = None,
    ) -> FraudDecisionAudit | None:
        """Retrieve the most recent audit record for a transaction.

        Args:
            transaction_id: Transaction UUID.
            owner_id: When set, only return the record if the transaction belongs
                to this account owner.

        Returns:
            The most recent FraudDecisionAudit for the transaction, or None.
        """
        session_maker = get_session_maker()
        if session_maker is None:
            return None

        async with session_maker() as session:
            if owner_id is not None:
                owned = await session.execute(
                    select(Transaction.id).where(
                        Transaction.id == transaction_id,
                        Transaction.owner_id == owner_id,
                    )
                )
                if owned.scalar_one_or_none() is None:
                    return None

            stmt = (
                select(FraudDecisionAudit)
                .where(FraudDecisionAudit.transaction_id == transaction_id)
                .order_by(FraudDecisionAudit.created_at.desc())
                .limit(1)
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()  # type: ignore[no-any-return]

    @staticmethod
    async def query_audits(
        owner_id: UUID,
        decision: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[FraudDecisionAudit], int]:
        """Query audit records for an account owner with optional filters.

        Args:
            decision: Filter by decision string.
            start_date: Filter by created_at >= start_date.
            end_date: Filter by created_at < end_date + 1 day.
            limit: Maximum number of records to return.
            offset: Number of records to skip.

        Returns:
            Tuple of (list of records, total count).
        """
        session_maker = get_session_maker()
        if session_maker is None:
            return [], 0

        async with session_maker() as session:
            stmt = (
                select(FraudDecisionAudit)
                .join(Transaction, Transaction.id == FraudDecisionAudit.transaction_id)
                .where(Transaction.owner_id == owner_id)
            )

            if decision is not None:
                stmt = stmt.where(FraudDecisionAudit.decision == decision)

            if start_date is not None:
                start_dt = datetime.combine(start_date, datetime.min.time())
                stmt = stmt.where(FraudDecisionAudit.created_at >= start_dt)

            if end_date is not None:
                end_dt = datetime.combine(end_date, datetime.max.time())
                stmt = stmt.where(FraudDecisionAudit.created_at <= end_dt)

            # Total count
            count_stmt = stmt.with_only_columns(
                func.count(FraudDecisionAudit.id)
            ).order_by(None)
            count_result = await session.execute(count_stmt)
            total = count_result.scalar_one() or 0

            # Paginated results
            stmt = (
                stmt.order_by(FraudDecisionAudit.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
            result = await session.execute(stmt)
            records = list(result.scalars().all())
            return records, total

    @staticmethod
    async def verify_integrity(owner_id: UUID) -> dict[str, Any]:
        """Verify the integrity of the audit hash chain for an account owner.

        Iterates through all audit records in chronological order and
        recomputes each hash to ensure the chain has not been tampered with.

        Returns:
            Dict with valid (bool), total_records (int), first_broken_id (UUID|None),
            and message (str).
        """
        session_maker = get_session_maker()
        if session_maker is None:
            return {
                "valid": False,
                "total_records": 0,
                "first_broken_id": None,
                "message": "Database not initialized",
            }

        async with session_maker() as session:
            stmt = (
                select(FraudDecisionAudit)
                .join(Transaction, Transaction.id == FraudDecisionAudit.transaction_id)
                .where(Transaction.owner_id == owner_id)
                .order_by(FraudDecisionAudit.created_at.asc())
            )
            result = await session.execute(stmt)
            records = list(result.scalars().all())

        if not records:
            return {
                "valid": True,
                "total_records": 0,
                "first_broken_id": None,
                "message": "No audit records to verify",
            }

        previous_hash: str | None = None
        for record in records:
            expected_hash = AuditService._generate_hash(
                transaction_id=record.transaction_id,
                decision=record.decision,
                score=record.score,
                reason=record.reason,
                features=record.features,
                rules_triggered=record.rules_triggered,
                model_version=record.model_version,
                previous_hash=previous_hash,
            )
            if record.hash != expected_hash:
                return {
                    "valid": False,
                    "total_records": len(records),
                    "first_broken_id": record.id,
                    "message": (
                        f"Hash mismatch at record {record.id}: "
                        f"expected {expected_hash}, got {record.hash}"
                    ),
                }
            previous_hash = record.hash

        return {
            "valid": True,
            "total_records": len(records),
            "first_broken_id": None,
            "message": f"All {len(records)} records verified successfully",
        }
