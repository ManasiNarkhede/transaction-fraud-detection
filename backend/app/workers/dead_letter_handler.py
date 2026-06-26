"""Failed message handler for dead letter queue."""

from __future__ import annotations

import logging
from typing import Any

from redis.exceptions import ResponseError

from app.infrastructure.redis_client import get_redis

logger = logging.getLogger(__name__)


class DeadLetterHandler:
    """Monitor and handle dead letter queue."""

    def __init__(self) -> None:
        self._redis_override = None
        self.stream = "fraud:dead_letter"

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

    async def get_dead_letter_count(self) -> int:
        """Get the number of messages in the dead letter queue.

        Returns:
            Number of messages in the dead letter stream. Returns 0 if the
            stream does not exist yet (nothing has ever been dead-lettered).
        """
        try:
            info = await self.redis.xinfo_stream(self.stream)
        except ResponseError as exc:
            if "no such key" in str(exc).lower():
                return 0
            raise
        return info.get("length", 0)  # type: ignore[no-any-return]

    async def peek_messages(self, count: int = 10) -> list[Any]:
        """Peek at dead letter messages without removing them.

        Args:
            count: Maximum number of messages to return.

        Returns:
            List of messages from the dead letter stream.
        """
        messages = await self.redis.xrange(self.stream, count=count)
        return messages  # type: ignore[no-any-return]

    async def reprocess_message(self, msg_id: str, target_stream: str) -> bool:
        """Move a dead letter message back to its original stream for reprocessing.

        Args:
            msg_id: ID of the dead letter message to reprocess.
            target_stream: The stream to move the message to.

        Returns:
            True if successful, False otherwise.
        """
        try:
            messages = await self.redis.xrange(self.stream, min=msg_id, max=msg_id)
            if not messages:
                return False

            _, fields = messages[0]
            await self.redis.xadd(target_stream, fields)
            await self.redis.xdel(self.stream, msg_id)
            logger.info(
                "Reprocessed dead letter message %s to %s", msg_id, target_stream
            )
            return True
        except Exception:
            logger.exception("Failed to reprocess dead letter message %s", msg_id)
            return False
