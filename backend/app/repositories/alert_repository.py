"""Repository for persisting fraud alert records."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import Alert


class AlertRepository:
    """Encapsulates DB writes for fraud alerts."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_alert(
        self,
        *,
        transaction_id: UUID,
        user_id: UUID,
        alert_type: str,
        severity: str = "medium",
    ) -> Alert:
        """Insert an alert row and return it.

        Args:
            transaction_id: UUID of the transaction that triggered the alert.
            user_id: UUID of the transaction's user.
            alert_type: Alert category (e.g. the decision: block/verify).
            severity: Alert severity (low/medium/high/critical).

        Returns:
            The persisted ``Alert``.
        """
        alert = Alert(
            transaction_id=transaction_id,
            user_id=user_id,
            alert_type=alert_type,
            severity=severity,
            status="open",
        )
        self.session.add(alert)
        await self.session.commit()
        await self.session.refresh(alert)
        return alert

    async def get_by_id(self, alert_id: UUID) -> Alert | None:
        """Fetch a single alert by primary key.

        Args:
            alert_id: UUID of the alert.

        Returns:
            The Alert record, or None if not found.
        """
        stmt = select(Alert).where(Alert.id == alert_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
