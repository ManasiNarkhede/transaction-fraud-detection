"""Base class for Redis Stream consumers."""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from typing import Any

from redis.exceptions import ResponseError

from app.infrastructure.redis_client import get_redis
from app.services.stream_producer import STREAM_DEAD_LETTER

logger = logging.getLogger(__name__)


class StreamWorker(ABC):
    """Base class for Redis Stream consumers."""

    def __init__(self, stream_name: str, group_name: str, consumer_name: str) -> None:
        self.stream_name = stream_name
        self.group_name = group_name
        self.consumer_name = consumer_name
        self._redis_override = None
        self.max_retries = 3

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

    async def _create_group(self) -> None:
        """Create the consumer group if it doesn't exist."""
        try:
            await self.redis.xgroup_create(
                self.stream_name, self.group_name, id="0", mkstream=True
            )
            logger.info(
                "Created consumer group %s for stream %s",
                self.group_name,
                self.stream_name,
            )
        except ResponseError as e:
            if "already exists" not in str(e).lower():
                raise

    async def consume(self, count: int = 10, block: int = 5000) -> None:
        """Consume messages from the stream.

        Args:
            count: Maximum number of messages to read.
            block: Milliseconds to block waiting for messages.
        """
        messages = await self.redis.xreadgroup(
            self.group_name,
            self.consumer_name,
            {self.stream_name: ">"},
            count=count,
            block=block,
        )

        for _stream, msgs in messages:
            for msg_id, fields in msgs:
                await self._process_message(msg_id, fields)

    async def _process_message(self, msg_id: str, fields: dict[str, Any]) -> None:
        """Process a single message with retry logic.

        Args:
            msg_id: Redis message ID.
            fields: Message fields dictionary.
        """
        retry_count = int(fields.get("retry_count", 0))

        try:
            data = json.loads(fields.get("data", "{}"))
            await self.process(data)
            await self.redis.xack(self.stream_name, self.group_name, msg_id)
            logger.debug("Processed and acknowledged message %s", msg_id)
        except Exception as exc:
            logger.exception("Failed to process message %s", msg_id)
            if retry_count < self.max_retries:
                await self._retry_message(msg_id, fields, retry_count)
            else:
                await self._dead_letter(msg_id, fields, exc)

    async def _retry_message(
        self, msg_id: str, fields: dict[str, Any], retry_count: int
    ) -> None:
        """Re-queue message with incremented retry count.

        Args:
            msg_id: Original message ID.
            fields: Message fields dictionary.
            retry_count: Current retry count.
        """
        fields["retry_count"] = str(retry_count + 1)
        await self.redis.xadd(self.stream_name, fields)
        await self.redis.xack(self.stream_name, self.group_name, msg_id)
        logger.warning("Retrying message %s (attempt %d)", msg_id, retry_count + 1)

    async def _dead_letter(
        self, msg_id: str, fields: dict[str, Any], error: Exception
    ) -> None:
        """Move message to dead letter queue.

        Args:
            msg_id: Original message ID.
            fields: Message fields dictionary.
            error: The exception that caused final failure.
        """
        fields["error"] = str(error)
        fields["original_stream"] = self.stream_name
        await self.redis.xadd(STREAM_DEAD_LETTER, fields)
        await self.redis.xack(self.stream_name, self.group_name, msg_id)
        logger.error("Message %s moved to dead letter queue", msg_id)

    @abstractmethod
    async def process(self, data: dict[str, Any]) -> None:
        """Process the message data. Implement in subclass."""
        pass
