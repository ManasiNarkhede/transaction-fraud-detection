"""Repository for persisting blocked-transaction records."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.datetime_utils import utc_now_naive
from app.models.blocked_transaction import BlockedTransaction


class BlockedTransactionRepository:
    """Encapsulates DB writes for blocked transactions."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_for_transaction(
        self, transaction_id: UUID
    ) -> BlockedTransaction | None:
        """Return an existing blocked-transaction row, if any."""
        stmt = select(BlockedTransaction).where(
            BlockedTransaction.transaction_id == transaction_id
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def stage_block(
        self,
        *,
        transaction_id: UUID,
        user_id: UUID,
        reason: str | None,
        rule_triggered: str | None = None,
    ) -> BlockedTransaction:
        """Attach a blocked-transaction row to the current session without committing."""
        existing = await self.get_for_transaction(transaction_id)
        if existing is not None:
            return existing

        blocked = BlockedTransaction(
            transaction_id=transaction_id,
            user_id=user_id,
            reason=reason,
            rule_triggered=rule_triggered,
            blocked_at=utc_now_naive(),
        )
        self.session.add(blocked)
        return blocked

    async def record_block(
        self,
        *,
        transaction_id: UUID,
        user_id: UUID,
        reason: str | None,
        rule_triggered: str | None = None,
    ) -> BlockedTransaction:
        """Insert a blocked-transaction row and return it.

        Args:
            transaction_id: UUID of the blocked transaction.
            user_id: UUID of the transaction's user.
            reason: Human-readable block reason.
            rule_triggered: Comma-joined names of triggered rules, if any.

        Returns:
            The persisted ``BlockedTransaction``.
        """
        blocked = await self.stage_block(
            transaction_id=transaction_id,
            user_id=user_id,
            reason=reason,
            rule_triggered=rule_triggered,
        )
        await self.session.commit()
        await self.session.refresh(blocked)
        return blocked
