"""Service that assembles fraud dashboard metrics.

Keeps the router thin: all aggregation runs through
:class:`DashboardRepository`, and the false-positive rate is derived here.
"""

from __future__ import annotations

from uuid import UUID

from app.config import settings
from app.infrastructure.database import get_session_maker
from app.repositories.dashboard_repository import DashboardRepository
from app.schemas.dashboard import (
    DashboardKPIs,
    DashboardMetricsResponse,
    DecisionLatencyKPI,
    FraudTrendPoint,
)


class DashboardService:
    """Builds the dashboard metrics response from persisted data."""

    def __init__(self, trend_days: int = 7) -> None:
        self.trend_days = trend_days
        # High-risk = a fraud score in the "verify" band or above.
        self.high_risk_threshold = settings.verify_threshold

    async def get_metrics(self, owner_id: UUID) -> DashboardMetricsResponse:
        """Aggregate dashboard metrics for a single account owner.

        Returns:
            A fully-populated :class:`DashboardMetricsResponse`.

        Raises:
            RuntimeError: if the database session maker is not initialized.
        """
        session_maker = get_session_maker()
        if session_maker is None:
            raise RuntimeError("Database session maker is not initialized")

        async with session_maker() as session:
            repo = DashboardRepository(session, owner_id=owner_id)
            total = await repo.count_transactions()
            blocked = await repo.count_blocked_transactions()
            high_risk = await repo.count_high_risk_users(self.high_risk_threshold)
            verif = await repo.verification_terminal_counts()
            trends = await repo.fraud_trends(self.trend_days)
            total_decisions = await repo.count_total_decisions()
            latency = await repo.latency_stats()

        fp_rate = self._false_positive_rate(verif)

        kpis = DashboardKPIs(
            block_success_rate=self._block_success_rate(blocked, total_decisions),
            verification_success_rate=fp_rate,
            decision_latency=DecisionLatencyKPI(
                avg_ms=latency["avg_ms"],
                p95_ms=latency["p95_ms"],
            ),
            fraud_detection_accuracy=None,
            fraud_detection_accuracy_note=(
                "requires labeled outcomes — no confirmed-fraud feedback loop exists yet"
            ),
            false_negative_rate=None,
            false_negative_rate_note=(
                "requires labeled outcomes — no confirmed-fraud feedback loop exists yet"
            ),
        )

        return DashboardMetricsResponse(
            total_transactions=total,
            blocked_transactions=blocked,
            high_risk_users=high_risk,
            false_positive_rate=fp_rate,
            fraud_trends=[FraudTrendPoint(**point) for point in trends],
            kpis=kpis,
        )

    @staticmethod
    def _false_positive_rate(verif: dict[str, int]) -> float:
        """Compute the false-positive rate from terminal verification counts.

        Definition: a transaction the system challenged (``verify``) which the
        user then passed (state ``VERIFIED``) is treated as a false positive —
        the system suspected fraud but the legitimate user proved themselves.

            FP rate = VERIFIED / (VERIFIED + FAILED + EXPIRED)

        Returns ``0.0`` when there are no terminal verifications.
        """
        verified = verif.get("VERIFIED", 0)
        terminal = verified + verif.get("FAILED", 0) + verif.get("EXPIRED", 0)
        if terminal == 0:
            return 0.0
        return round(verified / terminal, 4)

    @staticmethod
    def _block_success_rate(blocked: int, total_decisions: int) -> float:
        """Fraction of decisions that resulted in a block.

            block_success_rate = blocked_transactions / total_decisions

        Returns ``0.0`` when no decisions have been recorded.
        """
        if total_decisions == 0:
            return 0.0
        return round(blocked / total_decisions, 4)
