"""Consumer for audit events."""

from __future__ import annotations

import logging
from typing import Any

from app.workers.base_worker import StreamWorker

logger = logging.getLogger(__name__)


class AuditWorker(StreamWorker):
    """Consumer for audit events."""

    def __init__(self) -> None:
        super().__init__("fraud:audit", "audit-group", "audit-consumer-1")

    async def process(self, data: dict[str, Any]) -> None:
        """Process audit event.

        Args:
            data: Audit event data dictionary.
        """
        logger.info(
            "AUDIT: Processing audit event for transaction %s",
            data.get("transaction_id"),
        )
        # Audit logging is already handled synchronously in Phase 8
        # This worker can be used for additional async audit processing
