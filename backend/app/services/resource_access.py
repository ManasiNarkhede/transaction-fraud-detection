"""Helpers for per-account resource ownership checks."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import Alert
from app.models.fraud_rule import FraudRule
from app.models.transaction import Transaction


async def get_owned_transaction(
    session: AsyncSession, transaction_id: UUID, owner_id: UUID
) -> Transaction | None:
    """Return a transaction only if it belongs to ``owner_id``."""
    stmt = select(Transaction).where(
        Transaction.id == transaction_id,
        Transaction.owner_id == owner_id,
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_owned_rule(
    session: AsyncSession, rule_id: UUID, owner_id: UUID
) -> FraudRule | None:
    """Return a fraud rule only if it belongs to ``owner_id``."""
    stmt = select(FraudRule).where(
        FraudRule.id == rule_id,
        FraudRule.owner_id == owner_id,
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_owned_alert(
    session: AsyncSession, alert_id: UUID, owner_id: UUID
) -> Alert | None:
    """Return an alert only if its transaction belongs to ``owner_id``."""
    stmt = (
        select(Alert)
        .join(Transaction, Transaction.id == Alert.transaction_id)
        .where(Alert.id == alert_id, Transaction.owner_id == owner_id)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()
