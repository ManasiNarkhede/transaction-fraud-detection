"""Redis Stream producer for fraud detection events."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.infrastructure.redis_client import get_redis

logger = logging.getLogger(__name__)

STREAM_RESULTS = "fraud:results"
STREAM_ALERTS = "fraud:alerts"
STREAM_AUDIT = "fraud:audit"
STREAM_DASHBOARD = "fraud:dashboard"
STREAM_DEAD_LETTER = "fraud:dead_letter"


class RedisStreamProducer:
    """Publish fraud detection events to Redis Streams."""

    def __init__(self) -> None:
        self._redis_override = None

    @property
    def redis(self):  # type: ignore[no-untyped-def]
        """Live Redis client, resolved at access time.

        Resolving here (rather than binding in ``__init__``) avoids capturing
        the import-time ``None`` before ``init_redis()`` runs. Tests may set
        this attribute directly to inject a mock.
        """
        if self._redis_override is not None:
            return self._redis_override  # type: ignore[unreachable]
        return get_redis()

    @redis.setter
    def redis(self, value) -> None:  # type: ignore[no-untyped-def]
        self._redis_override = value

    @redis.deleter
    def redis(self) -> None:
        self._redis_override = None

    async def _publish(
        self,
        stream: str,
        event_type: str,
        transaction_id: UUID,
        data: dict[str, Any],
        trace_id: str | None = None,
    ) -> str:
        """Publish an event to a Redis Stream.

        Args:
            stream: The Redis stream name.
            event_type: Type of event being published.
            transaction_id: UUID of the transaction.
            data: Event payload dictionary.
            trace_id: Optional trace ID for distributed tracing.

        Returns:
            The message ID assigned by Redis.
        """
        message = {
            "event_type": event_type,
            "transaction_id": str(transaction_id),
            "timestamp": datetime.now(UTC).isoformat(),
            "trace_id": trace_id or "unknown",
            # default=str so any non-JSON-native value (Decimal, UUID, datetime)
            # serializes instead of crashing the publish/worker.
            "data": json.dumps(data, default=str),
        }
        msg_id = await self.redis.xadd(stream, message, maxlen=10000, approximate=True)
        logger.info("Published %s to %s (id=%s)", event_type, stream, msg_id)
        return msg_id  # type: ignore[no-any-return]

    async def publish_scoring_result(
        self,
        transaction_id: UUID,
        decision: str,
        score: int,
        reason: str,
        features: dict[str, Any],
        trace_id: str | None = None,
    ) -> str:
        """Publish a scoring result event.

        Args:
            transaction_id: UUID of the transaction.
            decision: Final decision (approve/verify/block).
            score: Fraud risk score (0-100).
            reason: Human-readable explanation.
            features: Feature values used in scoring.
            trace_id: Optional trace ID.

        Returns:
            The message ID assigned by Redis.
        """
        return await self._publish(
            STREAM_RESULTS,
            "scoring_result",
            transaction_id,
            {
                "decision": decision,
                "score": score,
                "reason": reason,
                "features": features,
            },
            trace_id,
        )

    async def publish_alert(
        self,
        transaction_id: UUID,
        decision: str,
        score: int,
        reason: str,
        user_id: UUID | None = None,
        trace_id: str | None = None,
    ) -> str:
        """Publish an alert event for blocked/verified transactions.

        Args:
            transaction_id: UUID of the transaction.
            decision: Final decision (approve/verify/block).
            score: Fraud risk score (0-100).
            reason: Human-readable explanation.
            user_id: UUID of the transaction's user (for alert persistence).
            trace_id: Optional trace ID.

        Returns:
            The message ID assigned by Redis.
        """
        return await self._publish(
            STREAM_ALERTS,
            "alert",
            transaction_id,
            {
                "transaction_id": str(transaction_id),
                "user_id": str(user_id) if user_id else None,
                "decision": decision,
                "score": score,
                "reason": reason,
            },
            trace_id,
        )

    async def publish_audit_event(
        self,
        transaction_id: UUID,
        audit_data: dict[str, Any],
        trace_id: str | None = None,
    ) -> str:
        """Publish an audit event.

        Args:
            transaction_id: UUID of the transaction.
            audit_data: Audit payload dictionary.
            trace_id: Optional trace ID.

        Returns:
            The message ID assigned by Redis.
        """
        return await self._publish(
            STREAM_AUDIT, "audit", transaction_id, audit_data, trace_id
        )

    async def publish_dashboard_update(
        self,
        transaction_id: UUID,
        metrics: dict[str, Any],
        trace_id: str | None = None,
    ) -> str:
        """Publish a dashboard update event.

        Args:
            transaction_id: UUID of the transaction.
            metrics: Dashboard metrics dictionary.
            trace_id: Optional trace ID.

        Returns:
            The message ID assigned by Redis.
        """
        return await self._publish(
            STREAM_DASHBOARD, "dashboard_update", transaction_id, metrics, trace_id
        )
