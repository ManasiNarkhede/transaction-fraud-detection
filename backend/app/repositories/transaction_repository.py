"""Repository for persisting transactions and their fraud scores."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fraud_decision_audit import FraudDecisionAudit
from app.models.fraud_score import FraudScore
from app.models.transaction import Transaction


class TransactionRepository:
    """Encapsulates DB writes for the live ingestion pipeline."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_transaction(
        self,
        *,
        user_id: UUID,
        owner_id: UUID,
        amount: Decimal,
        currency: str,
        merchant_id: str | None,
        merchant_category: str | None,
        ip_address: str | None,
        device_fingerprint: str | None,
        card_last_four: str | None,
    ) -> Transaction:
        """Insert a new pending transaction and return it with its id populated."""
        transaction = Transaction(
            user_id=user_id,
            owner_id=owner_id,
            amount=amount,
            currency=currency,
            merchant_id=merchant_id,
            merchant_category=merchant_category,
            ip_address=ip_address,
            device_fingerprint=device_fingerprint,
            card_last_four=card_last_four,
            status="pending",
        )
        self.session.add(transaction)
        await self.session.commit()
        await self.session.refresh(transaction)
        return transaction

    async def save_fraud_score(
        self,
        *,
        transaction_id: UUID,
        user_id: UUID,
        score: int,
        features_used: dict[str, Any],
        model_version: str | None = None,
        decision_latency_ms: int | None = None,
    ) -> FraudScore:
        """Persist the computed fraud score and feature snapshot."""
        fraud_score = FraudScore(
            transaction_id=transaction_id,
            user_id=user_id,
            model_version=model_version,
            score=Decimal(str(score)),
            features_used=features_used,
            decision_latency_ms=decision_latency_ms,
        )
        self.session.add(fraud_score)
        await self.session.commit()
        await self.session.refresh(fraud_score)
        return fraud_score

    async def list_decisions(
        self,
        *,
        owner_id: UUID,
        decision: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """List scored transactions for an account with score and audit metadata."""
        latest_score = select(
            FraudScore.transaction_id.label("transaction_id"),
            FraudScore.score.label("score"),
            func.row_number()
            .over(
                partition_by=FraudScore.transaction_id,
                order_by=FraudScore.created_at.desc(),
            )
            .label("rn"),
        ).subquery()

        latest_audit = select(
            FraudDecisionAudit.transaction_id.label("transaction_id"),
            FraudDecisionAudit.reason.label("reason"),
            FraudDecisionAudit.rules_triggered.label("rules_triggered"),
            func.row_number()
            .over(
                partition_by=FraudDecisionAudit.transaction_id,
                order_by=FraudDecisionAudit.created_at.desc(),
            )
            .label("rn"),
        ).subquery()

        stmt = (
            select(
                Transaction.id,
                Transaction.amount,
                Transaction.currency,
                Transaction.status,
                Transaction.created_at,
                latest_score.c.score,
                latest_audit.c.reason,
                latest_audit.c.rules_triggered,
            )
            .outerjoin(
                latest_score,
                and_(
                    latest_score.c.transaction_id == Transaction.id,
                    latest_score.c.rn == 1,
                ),
            )
            .outerjoin(
                latest_audit,
                and_(
                    latest_audit.c.transaction_id == Transaction.id,
                    latest_audit.c.rn == 1,
                ),
            )
            .where(
                Transaction.owner_id == owner_id,
                or_(
                    Transaction.status != "pending",
                    exists(
                        select(FraudScore.id).where(
                            FraudScore.transaction_id == Transaction.id
                        )
                    ),
                ),
            )
        )

        if decision is not None:
            stmt = stmt.where(Transaction.status == decision)

        if start_date is not None:
            start_dt = datetime.combine(start_date, datetime.min.time())
            stmt = stmt.where(Transaction.created_at >= start_dt)

        if end_date is not None:
            end_dt = datetime.combine(end_date, datetime.max.time())
            stmt = stmt.where(Transaction.created_at <= end_dt)

        count_stmt = stmt.with_only_columns(func.count(Transaction.id)).order_by(None)
        total = int((await self.session.execute(count_stmt)).scalar_one() or 0)

        stmt = stmt.order_by(Transaction.created_at.desc()).offset(offset).limit(limit)
        rows = (await self.session.execute(stmt)).all()

        items: list[dict[str, Any]] = []
        for row in rows:
            status = row.status
            if status == "blocked":
                status = "block"
            if status not in ("approve", "verify", "block"):
                status = "approve"
            items.append(
                {
                    "transaction_id": row.id,
                    "amount": row.amount,
                    "currency": row.currency,
                    "decision": status,
                    "score": int(row.score) if row.score is not None else 0,
                    "reason": row.reason or "Decision recorded",
                    "rules_triggered": row.rules_triggered or [],
                    "created_at": row.created_at,
                }
            )

        return items, total
