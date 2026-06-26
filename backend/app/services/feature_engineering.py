"""Feature engineering service that computes ML feature vectors.

Ties together the FeatureVector Pydantic model, SQL aggregation queries,
and Redis caching to provide fast, reusable feature computation for fraud
scoring.
"""

from __future__ import annotations

import logging
import math
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database import get_session_maker
from app.models import FeatureVector
from app.services.cache import Cache
from app.services.feature_queries import (
    get_device_trust_score,
    get_failed_attempt_count,
    get_last_transaction,
    get_merchant_risk_score,
    get_recent_transaction_counts,
    get_unique_countries,
    get_unique_merchants,
    get_user_transaction_stats,
    is_new_device_for_user,
)
from app.services.key_builder import KeyBuilder

logger = logging.getLogger(__name__)


class FeatureEngineeringService:
    """Service for computing and caching fraud-detection feature vectors."""

    def __init__(self) -> None:
        self.cache = Cache()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    async def compute_features(
        self,
        user_id: UUID,
        transaction_amount: Decimal,
        device_fingerprint: str,
        merchant_id: str,
        timestamp: datetime,
    ) -> FeatureVector:
        """Main entry point: compute features with cache fallback."""
        cached = await self.get_cached_features(user_id)
        if cached is not None:
            return cached

        session_maker = get_session_maker()
        if session_maker is None:
            logger.warning("database_not_initialized", extra={"user_id": str(user_id)})
            return self.get_cold_start_features(
                transaction_amount, device_fingerprint, timestamp
            )

        async with session_maker() as session:
            features = await self.compute_features_from_db(
                session,
                user_id,
                transaction_amount,
                device_fingerprint,
                merchant_id,
                timestamp,
            )

        await self.cache_features(user_id, features)
        return features

    async def compute_features_from_db(
        self,
        session: AsyncSession,
        user_id: UUID,
        amount: Decimal,
        fingerprint: str,
        merchant_id: str,
        timestamp: datetime,
        *,
        transaction_id: UUID | None = None,
    ) -> FeatureVector:
        """Compute all features from database aggregations for one transaction."""
        # Historical transaction stats (30 days), including current for display.
        stats = await get_user_transaction_stats(session, user_id, days=30)
        # Prior-only stats for z-score (current amount vs history before this tx).
        prior_stats = await get_user_transaction_stats(
            session,
            user_id,
            days=30,
            exclude_transaction_id=transaction_id,
        )

        # Recent transaction counts
        tx_count_1h = await get_recent_transaction_counts(session, user_id, hours=1)
        tx_count_24h = await get_recent_transaction_counts(session, user_id, hours=24)
        tx_count_7d = await get_recent_transaction_counts(session, user_id, hours=168)

        # Unique merchants / countries in last 24h
        unique_merchants_24h = await get_unique_merchants(session, user_id, hours=24)
        unique_countries_24h = await get_unique_countries(session, user_id, hours=24)

        # Device risk signals
        device_trust_score = await get_device_trust_score(session, user_id, fingerprint)
        is_new_device = await is_new_device_for_user(session, user_id, fingerprint)

        # Spec-named behavioral risk signals
        failed_attempt_count = await get_failed_attempt_count(
            session, user_id, hours=24
        )
        merchant_risk_score = await get_merchant_risk_score(session, merchant_id)

        # Time since the previous transaction (exclude the one being scored).
        last_tx = await get_last_transaction(
            session, user_id, exclude_transaction_id=transaction_id
        )
        time_since_last_tx = self._hours_since(last_tx, timestamp)

        # Z-score of amount relative to prior user history.
        amount_zscore = self._calculate_zscore(amount, prior_stats)

        # Temporal cyclical features
        hour_of_day = timestamp.hour
        day_of_week = timestamp.weekday()
        is_weekend = day_of_week >= 5

        # Cold-start adjustments for aggregations.
        # DB AVG() returns high-precision Decimals; quantize money values to 2
        # places to satisfy the FeatureVector decimal_places=2 contract.
        if stats["count"] == 0:
            avg_amount_30d = amount
            max_amount_30d = amount
        else:
            avg_amount_30d = stats["avg_amount"] or amount
            max_amount_30d = stats["max_amount"] or amount
        avg_amount_30d = self._money(avg_amount_30d)
        max_amount_30d = self._money(max_amount_30d)

        return FeatureVector(
            amount=amount,
            log_amount=self._log_amount(amount),
            amount_zscore=amount_zscore,
            time_since_last_tx=time_since_last_tx,
            tx_count_1h=tx_count_1h,
            tx_count_24h=tx_count_24h,
            tx_count_7d=tx_count_7d,
            avg_amount_30d=avg_amount_30d,
            max_amount_30d=max_amount_30d,
            unique_merchants_24h=unique_merchants_24h or 1,
            unique_countries_24h=unique_countries_24h or 1,
            device_trust_score=float(device_trust_score),
            is_new_device=is_new_device,
            hour_of_day=hour_of_day,
            day_of_week=day_of_week,
            is_weekend=is_weekend,
            failed_attempt_count=failed_attempt_count,
            merchant_risk_score=merchant_risk_score,
        )

    async def get_cached_features(self, user_id: UUID) -> FeatureVector | None:
        """Retrieve a cached FeatureVector from Redis."""
        key = KeyBuilder.feature_vector(str(user_id))
        data = await self.cache.get(key)
        if data is None:
            return None
        try:
            return FeatureVector(**data)
        except Exception as exc:
            logger.warning(
                "cached_feature_parse_failed",
                extra={"user_id": str(user_id), "error": str(exc)},
            )
            return None

    async def cache_features(
        self, user_id: UUID, features: FeatureVector, ttl: int = 300
    ) -> bool:
        """Store a FeatureVector in Redis with the given TTL."""
        key = KeyBuilder.feature_vector(str(user_id))
        return await self.cache.set(key, features.model_dump(), ttl=ttl)

    def get_cold_start_features(
        self,
        amount: Decimal,
        fingerprint: str,
        timestamp: datetime,
    ) -> FeatureVector:
        """Return default features for a brand-new user (cold start)."""
        hour_of_day = timestamp.hour
        day_of_week = timestamp.weekday()
        is_weekend = day_of_week >= 5

        return FeatureVector(
            amount=amount,
            log_amount=self._log_amount(amount),
            amount_zscore=0.0,
            time_since_last_tx=999.0,
            tx_count_1h=0,
            tx_count_24h=0,
            tx_count_7d=0,
            avg_amount_30d=amount,
            max_amount_30d=amount,
            unique_merchants_24h=1,
            unique_countries_24h=1,
            device_trust_score=0.5,
            is_new_device=True,
            hour_of_day=hour_of_day,
            day_of_week=day_of_week,
            is_weekend=is_weekend,
            failed_attempt_count=0,
            merchant_risk_score=0.0,
        )

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _log_amount(amount: Decimal) -> float:
        """Return log1p(amount), clamped at 0 for non-positive amounts."""
        value = float(amount)
        if value <= 0:
            return 0.0
        return math.log1p(value)

    @staticmethod
    def _money(value: Decimal) -> Decimal:
        """Quantize a monetary Decimal to 2 places (DB AVG returns more)."""
        return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @staticmethod
    def _calculate_zscore(amount: Decimal, stats: dict[str, Any]) -> float:
        """Calculate amount z-score against prior transaction history.

        Uses population std when at least two prior amounts exist. With exactly
        one prior amount (std=0), falls back to relative deviation from mean.
        """
        count = stats.get("count", 0)
        avg = stats.get("avg_amount", Decimal("0"))
        std = stats.get("std_amount", Decimal("0"))

        if count == 0 or avg is None or avg == 0:
            return 0.0

        try:
            deviation = amount - avg
            if std is None or std == 0:
                if count == 1:
                    return float(deviation / avg)
                return 0.0
            return float(deviation / std)
        except Exception:
            return 0.0

    @staticmethod
    def _hours_since(last_tx: datetime | None, current: datetime) -> float:
        """Return hours since last transaction, or 999.0 if none.

        Normalizes both sides to tz-aware UTC before subtracting. Postgres
        ``TIMESTAMP WITHOUT TIME ZONE`` columns return naive datetimes (stored
        as UTC), while ``current`` is tz-aware (datetime.now(UTC)); subtracting
        mixed-awareness datetimes raises TypeError.
        """
        if last_tx is None:
            return 999.0
        if last_tx.tzinfo is None:
            last_tx = last_tx.replace(tzinfo=UTC)
        if current.tzinfo is None:
            current = current.replace(tzinfo=UTC)
        delta = current - last_tx
        hours = delta.total_seconds() / 3600.0
        return max(0.0, hours)
