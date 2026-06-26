"""Alert service for reading and updating fraud alerts."""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.datetime_utils import utc_now_naive
from app.models.alert import Alert
from app.models.transaction import Transaction
from app.repositories.alert_repository import AlertRepository
from app.services.alert_router import AlertRouter
from app.services.notification import NotificationService

logger = logging.getLogger(__name__)


class AlertService:
    """Service for querying and updating Alert records."""

    @staticmethod
    async def list_alerts(
        session: AsyncSession,
        owner_id: UUID,
        status: str | None = None,
        severity: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Alert], int]:
        """Return paginated alerts, newest first, with optional filters.

        Args:
            session: Active async SQLAlchemy session.
            status: Optional filter by status (open/investigating/resolved/dismissed).
            severity: Optional filter by severity (low/medium/high/critical).
            limit: Maximum number of records to return.
            offset: Number of records to skip.

        Returns:
            Tuple of (list of Alert records, total count).
        """
        stmt = (
            select(Alert)
            .join(Transaction, Transaction.id == Alert.transaction_id)
            .where(Transaction.owner_id == owner_id)
        )

        if status is not None:
            stmt = stmt.where(Alert.status == status)
        if severity is not None:
            stmt = stmt.where(Alert.severity == severity)

        count_stmt = stmt.with_only_columns(func.count(Alert.id)).order_by(None)
        count_result = await session.execute(count_stmt)
        total: int = count_result.scalar_one() or 0

        stmt = stmt.order_by(Alert.created_at.desc()).offset(offset).limit(limit)
        result = await session.execute(stmt)
        alerts = list(result.scalars().all())
        return alerts, total

    @staticmethod
    async def get_alert(
        session: AsyncSession, alert_id: UUID, owner_id: UUID
    ) -> Alert | None:
        """Fetch a single alert by primary key if owned by the account."""
        stmt = (
            select(Alert)
            .join(Transaction, Transaction.id == Alert.transaction_id)
            .where(Alert.id == alert_id, Transaction.owner_id == owner_id)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def acknowledge_alert(
        session: AsyncSession, alert_id: UUID, owner_id: UUID
    ) -> Alert | None:
        """Transition an alert from 'open' to 'investigating'."""
        alert = await AlertService.get_alert(session, alert_id, owner_id)
        if alert is None:
            return None

        if alert.status == "open":
            alert.status = "investigating"
            await session.commit()
            await session.refresh(alert)
            logger.info(
                "alert_acknowledged",
                extra={"alert_id": str(alert_id), "status": alert.status},
            )
        return alert

    @staticmethod
    async def resolve_alert(
        session: AsyncSession, alert_id: UUID, owner_id: UUID
    ) -> Alert | None:
        """Transition an alert to 'resolved' and set resolved_at timestamp."""
        alert = await AlertService.get_alert(session, alert_id, owner_id)
        if alert is None:
            return None

        alert.status = "resolved"
        alert.resolved_at = utc_now_naive()
        await session.commit()
        await session.refresh(alert)
        logger.info(
            "alert_resolved",
            extra={"alert_id": str(alert_id)},
        )
        return alert

    @staticmethod
    async def record_decision_alert(
        transaction_id: UUID,
        owner_id: UUID,
        decision: str,
        score: int,
        reason: str,
    ) -> None:
        """Persist an alert and notify the account owner for block/verify decisions."""
        if decision not in ("block", "verify"):
            return

        from app.infrastructure.database import get_session_maker
        from app.models.user import User

        session_maker = get_session_maker()
        if session_maker is None:
            logger.warning(
                "decision_alert_skipped_database_not_initialized",
                extra={"transaction_id": str(transaction_id)},
            )
            return

        recipient_email: str | None = None
        recipient_phone: str | None = None

        try:
            async with session_maker() as session:
                repo = AlertRepository(session)
                await repo.create_alert(
                    transaction_id=transaction_id,
                    user_id=owner_id,
                    alert_type=decision,
                    severity=AlertRouter.get_priority(decision, score),
                )

                row = (
                    await session.execute(
                        select(User.email, User.phone).where(User.id == owner_id)
                    )
                ).first()
                if row is not None:
                    recipient_email = row[0]
                    recipient_phone = row[1]

            notification = NotificationService()
            await notification.send_fraud_alert(
                transaction_id=transaction_id,
                decision=decision,
                score=score,
                reason=reason,
                recipient_email=recipient_email,
                recipient_phone=recipient_phone,
            )
        except Exception as exc:
            logger.warning(
                "decision_alert_failed",
                extra={
                    "transaction_id": str(transaction_id),
                    "decision": decision,
                    "error": str(exc),
                },
            )
