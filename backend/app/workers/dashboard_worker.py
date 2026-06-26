"""Consumer for dashboard update events."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.workers.base_worker import StreamWorker

logger = logging.getLogger(__name__)


class DashboardWorker(StreamWorker):
    """Consumer for dashboard update events."""

    def __init__(self) -> None:
        super().__init__("fraud:dashboard", "dashboard-group", "dashboard-consumer-1")

    async def process(self, data: dict[str, Any]) -> None:
        """Update dashboard metrics in Redis.

        The producer publishes the metrics dictionary directly as the stream
        event payload (see ``RedisStreamProducer.publish_dashboard_update``),
        so ``data`` *is* the metrics dict — e.g. ``{"decision": ..., "score": ...}``.

        Args:
            data: Dashboard metrics dictionary (decision, score, ...).
        """
        metrics = data

        pipe = self.redis.pipeline()

        # Increment total transactions counter
        pipe.incr("fraud:metrics:total_transactions")

        # Increment decision counters
        decision = metrics.get("decision")
        if decision:
            pipe.hincrby("fraud:metrics:decisions", decision, 1)

        # Update score distribution
        score = metrics.get("score", 0)
        score_bucket = min(score // 10, 9) * 10  # 0-9, 10-19, ..., 90-100
        pipe.hincrby(
            "fraud:metrics:score_distribution",
            f"{score_bucket}-{score_bucket + 9}",
            1,
        )

        # Update last transaction timestamp
        pipe.set("fraud:metrics:last_transaction", json.dumps(metrics))

        await pipe.execute()
        logger.info(
            "DASHBOARD: Updated metrics for decision=%s, score=%s",
            decision,
            score,
        )
