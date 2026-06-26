"""Repository for dashboard metric aggregation queries."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.types import Date

from app.models.fraud_score import FraudScore
from app.models.transaction import Transaction
from app.models.verification_log import VerificationLog


class DashboardRepository:
    """Read-only aggregation queries scoped to a single account owner."""

    def __init__(self, session: AsyncSession, owner_id: UUID) -> None:
        self.session = session
        self.owner_id = owner_id

    async def count_transactions(self) -> int:
        """Total number of transactions owned by this account."""
        stmt = select(func.count(Transaction.id)).where(
            Transaction.owner_id == self.owner_id
        )
        result = await self.session.execute(stmt)
        return int(result.scalar_one() or 0)

    async def count_blocked_transactions(self) -> int:
        """Transactions with a terminal block status for this account."""
        stmt = select(func.count(Transaction.id)).where(
            Transaction.owner_id == self.owner_id,
            Transaction.status.in_(["block", "blocked"]),
        )
        result = await self.session.execute(stmt)
        return int(result.scalar_one() or 0)

    async def count_high_risk_users(self, threshold: int) -> int:
        """Distinct fraud subjects with a high score on this account's transactions."""
        stmt = (
            select(func.count(func.distinct(FraudScore.user_id)))
            .join(Transaction, Transaction.id == FraudScore.transaction_id)
            .where(
                Transaction.owner_id == self.owner_id,
                FraudScore.score > Decimal(str(threshold)),
            )
        )
        result = await self.session.execute(stmt)
        return int(result.scalar_one() or 0)

    async def count_total_decisions(self) -> int:
        """Fraud-score rows for this account's transactions."""
        stmt = (
            select(func.count(FraudScore.id))
            .join(Transaction, Transaction.id == FraudScore.transaction_id)
            .where(Transaction.owner_id == self.owner_id)
        )
        result = await self.session.execute(stmt)
        return int(result.scalar_one() or 0)

    async def latency_stats(self) -> dict[str, float | None]:
        """Avg and p95 decision latency (ms) for this account's fraud scores."""
        stmt = (
            select(
                func.avg(FraudScore.decision_latency_ms).label("avg_ms"),
                func.percentile_cont(0.95)
                .within_group(FraudScore.decision_latency_ms.asc())
                .label("p95_ms"),
            )
            .join(Transaction, Transaction.id == FraudScore.transaction_id)
            .where(
                Transaction.owner_id == self.owner_id,
                FraudScore.decision_latency_ms.isnot(None),
            )
        )
        result = await self.session.execute(stmt)
        row = result.one()
        avg_ms = float(row.avg_ms) if row.avg_ms is not None else None
        p95_ms = float(row.p95_ms) if row.p95_ms is not None else None
        return {"avg_ms": avg_ms, "p95_ms": p95_ms}

    async def verification_terminal_counts(self) -> dict[str, int]:
        """Terminal verification states for this account's transactions."""
        stmt = (
            select(VerificationLog.state, func.count(VerificationLog.id))
            .join(Transaction, Transaction.id == VerificationLog.transaction_id)
            .where(
                Transaction.owner_id == self.owner_id,
                VerificationLog.state.in_(["VERIFIED", "FAILED", "EXPIRED"]),
            )
            .group_by(VerificationLog.state)
        )
        result = await self.session.execute(stmt)
        counts = {"VERIFIED": 0, "FAILED": 0, "EXPIRED": 0}
        for state, count in result.all():
            counts[state] = int(count)
        return counts

    async def fraud_trends(self, days: int = 7) -> list[dict]:
        """Daily totals for this account's transactions over the last ``days``."""
        today = datetime.now(UTC).date()
        start = today - timedelta(days=days - 1)
        start_dt = datetime.combine(start, datetime.min.time())

        tx_day = cast(Transaction.created_at, Date)
        tx_stmt = (
            select(tx_day, func.count(Transaction.id))
            .where(
                Transaction.owner_id == self.owner_id,
                Transaction.created_at >= start_dt,
            )
            .group_by(tx_day)
        )
        tx_rows = (await self.session.execute(tx_stmt)).all()
        totals = {row[0]: int(row[1]) for row in tx_rows}

        blocked_stmt = (
            select(tx_day, func.count(Transaction.id))
            .where(
                Transaction.owner_id == self.owner_id,
                Transaction.status.in_(["block", "blocked"]),
                Transaction.created_at >= start_dt,
            )
            .group_by(tx_day)
        )
        blocked_rows = (await self.session.execute(blocked_stmt)).all()
        blocked = {row[0]: int(row[1]) for row in blocked_rows}

        trends: list[dict] = []
        for offset in range(days):
            day: date = start + timedelta(days=offset)
            trends.append(
                {
                    "date": day,
                    "total": totals.get(day, 0),
                    "blocked": blocked.get(day, 0),
                }
            )
        return trends
