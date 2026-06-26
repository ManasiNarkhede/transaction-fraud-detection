"""Consumer for alert events."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import select

from app.infrastructure.database import get_session_maker
from app.models.transaction import Transaction
from app.models.user import User
from app.repositories.alert_repository import AlertRepository
from app.services.alert_router import AlertRouter
from app.services.notification import NotificationService
from app.workers.base_worker import StreamWorker

logger = logging.getLogger(__name__)


class AlertWorker(StreamWorker):
    """Consumer for alert events.

    Persists an :class:`Alert` row (read by the dashboard / Alerts page) and
    dispatches a notification for ``block``/``verify`` decisions.
    """

    def __init__(self) -> None:
        super().__init__("fraud:alerts", "alert-group", "alert-consumer-1")
        self.notification_service = NotificationService()

    async def process(self, data: dict[str, Any]) -> None:
        """Process alert event.

        Args:
            data: Alert event data dictionary (transaction_id, user_id,
                decision, score, reason).
        """
        decision = data.get("decision")
        score = data.get("score")
        reason = data.get("reason")
        transaction_id = data.get("transaction_id")
        user_id = data.get("user_id")

        if decision not in ["block", "verify"]:
            logger.debug("No alert needed for decision: %s", decision)
            return

        logger.info(
            "ALERT: Transaction blocked/verified (score=%s, reason=%s)",
            score,
            reason,
        )

        if not transaction_id:
            logger.warning("Alert event missing transaction_id; skipping")
            return

        tx_uuid = UUID(transaction_id)
        resolved_user_id = await self._resolve_user_id_for_transaction(tx_uuid, user_id)

        await self._persist_alert(tx_uuid, resolved_user_id, decision, score or 0)

        try:
            contact = await self._resolve_user_contact(resolved_user_id)
            await self.notification_service.send_fraud_alert(
                transaction_id=tx_uuid,
                decision=decision,
                score=score or 0,
                reason=reason or "",
                recipient_email=contact.get("email"),
                recipient_phone=contact.get("phone"),
            )
        except Exception as exc:
            logger.exception("Failed to send fraud alert notification: %s", exc)

    async def _resolve_user_id_for_transaction(
        self, transaction_id: UUID, user_id: str | None
    ) -> UUID | None:
        if user_id:
            return UUID(user_id)

        session_maker = get_session_maker()
        if session_maker is None:
            return None

        async with session_maker() as session:
            return await self._resolve_user_id(session, transaction_id, user_id)

    async def _resolve_user_contact(
        self, user_id: UUID | None
    ) -> dict[str, str | None]:
        """Load email and phone for alert delivery."""
        if user_id is None:
            return {"email": None, "phone": None}

        session_maker = get_session_maker()
        if session_maker is None:
            return {"email": None, "phone": None}

        async with session_maker() as session:
            stmt = select(User.email, User.phone).where(User.id == user_id)
            result = await session.execute(stmt)
            row = result.first()
            if row is None:
                return {"email": None, "phone": None}
            return {"email": row[0], "phone": row[1]}

    async def _persist_alert(
        self,
        transaction_id: UUID,
        user_id: UUID | None,
        decision: str,
        score: int,
    ) -> None:
        """Persist an Alert row for the resolved account owner."""
        session_maker = get_session_maker()
        if session_maker is None:
            logger.warning(
                "alert_persist_skipped_database_not_initialized",
                extra={"transaction_id": str(transaction_id)},
            )
            return

        if user_id is None:
            logger.warning(
                "alert_persist_skipped_no_user",
                extra={"transaction_id": str(transaction_id)},
            )
            return

        try:
            async with session_maker() as session:
                repo = AlertRepository(session)
                await repo.create_alert(
                    transaction_id=transaction_id,
                    user_id=user_id,
                    alert_type=decision,
                    severity=AlertRouter.get_priority(decision, score),
                )
        except Exception as exc:
            logger.exception("Failed to persist alert: %s", exc)

    @staticmethod
    async def _resolve_user_id(
        session: Any, transaction_id: UUID, user_id: str | None
    ) -> UUID | None:
        """Return user_id from the payload, else look it up by transaction."""
        if user_id:
            return UUID(user_id)
        stmt = select(Transaction.user_id).where(Transaction.id == transaction_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()  # type: ignore[no-any-return]
