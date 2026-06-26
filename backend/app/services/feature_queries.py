"""SQL query functions for feature engineering aggregations.

All functions are async and accept an AsyncSession. They use SQLAlchemy 2.0
style select() queries and handle None results gracefully by returning
sensible defaults.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Device, Transaction


async def get_user_transaction_stats(
    session: AsyncSession,
    user_id: UUID,
    days: int,
    *,
    exclude_transaction_id: UUID | None = None,
) -> dict[str, Any]:
    """Return transaction statistics for a user over the given number of days.

    Returns a dict with keys: count, avg_amount, max_amount, min_amount,
    std_amount. When ``exclude_transaction_id`` is set, that row is omitted
    (used for z-score baselines that compare the current amount to prior history).

    If no transactions exist, returns zeros and None for min_amount.
    """
    stmt = select(
        func.count(Transaction.id).label("count"),
        func.avg(Transaction.amount).label("avg_amount"),
        func.max(Transaction.amount).label("max_amount"),
        func.min(Transaction.amount).label("min_amount"),
        func.stddev_pop(Transaction.amount).label("std_amount"),
    ).where(
        Transaction.user_id == user_id,
        Transaction.created_at >= func.now() - timedelta(days=days),
    )
    if exclude_transaction_id is not None:
        stmt = stmt.where(Transaction.id != exclude_transaction_id)
    result = await session.execute(stmt)
    row = result.mappings().first()

    if row is None:
        return {
            "count": 0,
            "avg_amount": Decimal("0.00"),
            "max_amount": Decimal("0.00"),
            "min_amount": None,
            "std_amount": Decimal("0"),
        }

    return {
        "count": row["count"] or 0,
        "avg_amount": row["avg_amount"] or Decimal("0.00"),
        "max_amount": row["max_amount"] or Decimal("0.00"),
        "min_amount": row["min_amount"],
        "std_amount": row["std_amount"] or Decimal("0"),
    }


async def get_recent_transaction_counts(
    session: AsyncSession,
    user_id: UUID,
    hours: int,
) -> int:
    """Return the number of transactions for a user in the last N hours.

    Returns 0 if no transactions exist in the time window.
    """
    stmt = select(func.count(Transaction.id)).where(
        Transaction.user_id == user_id,
        Transaction.created_at >= func.now() - timedelta(hours=hours),
    )
    result = await session.execute(stmt)
    count = result.scalar()
    return count if count is not None else 0


async def get_unique_merchants(
    session: AsyncSession,
    user_id: UUID,
    hours: int,
) -> int:
    """Return the count of unique merchants for a user in the last N hours.

    Returns 0 if no transactions exist in the time window.
    """
    stmt = select(func.count(func.distinct(Transaction.merchant_id))).where(
        Transaction.user_id == user_id,
        Transaction.created_at >= func.now() - timedelta(hours=hours),
        Transaction.merchant_id.is_not(None),
    )
    result = await session.execute(stmt)
    count = result.scalar()
    return count if count is not None else 0


async def get_unique_countries(
    session: AsyncSession,
    user_id: UUID,
    hours: int,
) -> int:
    """Return the count of unique countries for a user in the last N hours.

    Uses the currency field as a proxy for country. Returns 0 if no
    transactions exist in the time window.
    """
    stmt = select(func.count(func.distinct(Transaction.currency))).where(
        Transaction.user_id == user_id,
        Transaction.created_at >= func.now() - timedelta(hours=hours),
        Transaction.currency.is_not(None),
    )
    result = await session.execute(stmt)
    count = result.scalar()
    return count if count is not None else 0


async def get_last_transaction(
    session: AsyncSession,
    user_id: UUID,
    *,
    exclude_transaction_id: UUID | None = None,
) -> datetime | None:
    """Return the created_at timestamp of the user's most recent transaction.

    When ``exclude_transaction_id`` is set, skip that row so callers can
    measure time since the *previous* transaction during ingest.

    Returns None if the user has no transactions.
    """
    stmt = (
        select(Transaction.created_at)
        .where(Transaction.user_id == user_id)
        .order_by(Transaction.created_at.desc())
        .limit(1)
    )
    if exclude_transaction_id is not None:
        stmt = stmt.where(Transaction.id != exclude_transaction_id)
    result = await session.execute(stmt)
    return result.scalar()


async def get_device_trust_score(
    session: AsyncSession,
    user_id: UUID,
    fingerprint: str,
) -> Decimal:
    """Return the trust score for a user's device fingerprint.

    Returns 0.50 (default neutral trust) if the device is not found.
    """
    stmt = select(Device.trust_score).where(
        Device.user_id == user_id,
        Device.device_fingerprint == fingerprint,
    )
    result = await session.execute(stmt)
    score = result.scalar()
    return score if score is not None else Decimal("0.50")


async def is_new_device_for_user(
    session: AsyncSession,
    user_id: UUID,
    fingerprint: str,
) -> bool:
    """Return True if the device fingerprint is new for the user.

    A device is considered new if no record exists in the devices table
    for the given user and fingerprint.
    """
    stmt = select(func.count(Device.id)).where(
        Device.user_id == user_id,
        Device.device_fingerprint == fingerprint,
    )
    result = await session.execute(stmt)
    count = result.scalar()
    return count == 0 if count is not None else True


async def get_failed_attempt_count(
    session: AsyncSession,
    user_id: UUID,
    hours: int = 24,
) -> int:
    """Return the number of blocked transaction attempts for a user in N hours.

    A "failed attempt" is a transaction whose status was set to ``block``
    by the decision engine. Returns 0 if none exist in the window.
    """
    stmt = select(func.count(Transaction.id)).where(
        Transaction.user_id == user_id,
        Transaction.status == "block",
        Transaction.created_at >= func.now() - timedelta(hours=hours),
    )
    result = await session.execute(stmt)
    count = result.scalar()
    return count if count is not None else 0


async def get_merchant_risk_score(
    session: AsyncSession,
    merchant_id: str | None,
    days: int = 30,
) -> float:
    """Return a merchant's historical fraud-block rate over N days.

    Computed as ``blocked_count / total_count`` across all users for the
    merchant. Returns 0.0 when the merchant is unknown or has no history
    (neutral, non-penalizing default).
    """
    if not merchant_id:
        return 0.0

    stmt = select(
        func.count(Transaction.id).label("total"),
        func.coalesce(
            func.sum(case((Transaction.status == "block", 1), else_=0)), 0
        ).label("blocked"),
    ).where(
        Transaction.merchant_id == merchant_id,
        Transaction.created_at >= func.now() - timedelta(days=days),
    )
    result = await session.execute(stmt)
    row = result.mappings().first()

    if row is None:
        return 0.0

    total = row["total"] or 0
    blocked = row["blocked"] or 0
    if total == 0:
        return 0.0

    return min(1.0, max(0.0, blocked / total))
