"""Unit tests for stream workers."""

from __future__ import annotations

import json
import logging
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest
from redis.exceptions import ResponseError

from app.workers.alert_worker import AlertWorker
from app.workers.audit_worker import AuditWorker
from app.workers.base_worker import StreamWorker
from app.workers.dashboard_worker import DashboardWorker
from app.workers.dead_letter_handler import DeadLetterHandler


class DummyWorker(StreamWorker):
    """Test implementation of StreamWorker."""

    def __init__(self):
        super().__init__("test:stream", "test-group", "test-consumer-1")
        self.processed_data = None

    async def process(self, data: dict) -> None:
        self.processed_data = data


# ---------------------------------------------------------------------------
# Base Worker Tests
# ---------------------------------------------------------------------------


@pytest.fixture
def dummy_worker():
    return DummyWorker()


@pytest.mark.asyncio
async def test_create_group_success(dummy_worker):
    """Should create consumer group on init."""
    mock_redis = AsyncMock()
    mock_redis.xgroup_create.return_value = True

    with patch.object(dummy_worker, "redis", mock_redis):
        await dummy_worker._create_group()

    mock_redis.xgroup_create.assert_awaited_once_with(
        "test:stream", "test-group", id="0", mkstream=True
    )


@pytest.mark.asyncio
async def test_create_group_already_exists(dummy_worker):
    """Should ignore 'already exists' error when creating group."""
    mock_redis = AsyncMock()
    mock_redis.xgroup_create.side_effect = ResponseError(
        "BUSYGROUP Consumer Group name already exists"
    )

    with patch.object(dummy_worker, "redis", mock_redis):
        await dummy_worker._create_group()  # Should not raise


@pytest.mark.asyncio
async def test_create_group_other_error_raises(dummy_worker):
    """Should raise on unexpected ResponseError."""
    mock_redis = AsyncMock()
    mock_redis.xgroup_create.side_effect = ResponseError("Some other error")

    with patch.object(dummy_worker, "redis", mock_redis), pytest.raises(ResponseError):
        await dummy_worker._create_group()


@pytest.mark.asyncio
async def test_consume_processes_messages(dummy_worker):
    """Should read and process messages from the stream."""
    mock_redis = AsyncMock()
    msg_id = "1234567890-0"
    fields = {
        "event_type": "test_event",
        "data": json.dumps({"key": "value"}),
    }
    mock_redis.xreadgroup.return_value = [(b"test:stream", [(msg_id.encode(), fields)])]
    mock_redis.xack.return_value = 1

    with patch.object(dummy_worker, "redis", mock_redis):
        await dummy_worker.consume(count=1, block=1000)

    mock_redis.xreadgroup.assert_awaited_once()
    mock_redis.xack.assert_awaited_once_with(
        "test:stream", "test-group", msg_id.encode()
    )
    assert dummy_worker.processed_data == {"key": "value"}


@pytest.mark.asyncio
async def test_process_message_retries_on_failure(dummy_worker):
    """Should retry message on processing failure."""
    mock_redis = AsyncMock()
    msg_id = "1234567890-0"
    fields = {
        "event_type": "test_event",
        "data": json.dumps({"key": "value"}),
        "retry_count": "0",
    }

    with (
        patch.object(dummy_worker, "redis", mock_redis),
        patch.object(
            dummy_worker, "process", side_effect=Exception("Processing failed")
        ),
    ):
        await dummy_worker._process_message(msg_id, fields)

    # Should re-add to stream with incremented retry count
    mock_redis.xadd.assert_awaited_once()
    call_args = mock_redis.xadd.call_args
    assert call_args[0][0] == "test:stream"
    assert call_args[0][1]["retry_count"] == "1"
    mock_redis.xack.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_message_dead_letter_after_max_retries(dummy_worker):
    """Should move message to dead letter after max retries exceeded."""
    mock_redis = AsyncMock()
    msg_id = "1234567890-0"
    fields = {
        "event_type": "test_event",
        "data": json.dumps({"key": "value"}),
        "retry_count": "3",
    }

    with (
        patch.object(dummy_worker, "redis", mock_redis),
        patch.object(
            dummy_worker, "process", side_effect=Exception("Processing failed")
        ),
    ):
        await dummy_worker._process_message(msg_id, fields)

    # Should add to dead letter stream
    mock_redis.xadd.assert_awaited_once()
    call_args = mock_redis.xadd.call_args
    assert call_args[0][0] == "fraud:dead_letter"
    assert "error" in call_args[0][1]
    assert call_args[0][1]["original_stream"] == "test:stream"
    mock_redis.xack.assert_awaited_once()


# ---------------------------------------------------------------------------
# Alert Worker Tests
# ---------------------------------------------------------------------------


@pytest.fixture
def alert_worker():
    return AlertWorker()


@pytest.mark.asyncio
async def test_alert_worker_processes_block(alert_worker, caplog):
    """Should log alert for block decision."""
    caplog.set_level(logging.INFO, logger="app.workers.alert_worker")
    with patch.object(alert_worker, "redis", AsyncMock()):
        await alert_worker.process(
            {"decision": "block", "score": 85, "reason": "high_amount"}
        )

    assert "ALERT" in caplog.text
    assert "high_amount" in caplog.text


@pytest.mark.asyncio
async def test_alert_worker_processes_verify(alert_worker, caplog):
    """Should log alert for verify decision."""
    caplog.set_level(logging.INFO, logger="app.workers.alert_worker")
    with patch.object(alert_worker, "redis", AsyncMock()):
        await alert_worker.process(
            {"decision": "verify", "score": 60, "reason": "new_device"}
        )

    assert "ALERT" in caplog.text


@pytest.mark.asyncio
async def test_alert_worker_ignores_approve(alert_worker, caplog):
    """Should not log alert for approve decision."""
    caplog.set_level(logging.INFO, logger="app.workers.alert_worker")
    with patch.object(alert_worker, "redis", AsyncMock()):
        await alert_worker.process(
            {"decision": "approve", "score": 30, "reason": "clean"}
        )

    assert "ALERT" not in caplog.text


# ---------------------------------------------------------------------------
# Audit Worker Tests
# ---------------------------------------------------------------------------


@pytest.fixture
def audit_worker():
    return AuditWorker()


@pytest.mark.asyncio
async def test_audit_worker_processes_event(audit_worker, caplog):
    """Should log audit event processing."""
    caplog.set_level(logging.INFO, logger="app.workers.audit_worker")
    tx_id = str(uuid4())
    with patch.object(audit_worker, "redis", AsyncMock()):
        await audit_worker.process({"transaction_id": tx_id})

    assert "AUDIT" in caplog.text
    assert tx_id in caplog.text


# ---------------------------------------------------------------------------
# Dashboard Worker Tests
# ---------------------------------------------------------------------------


@pytest.fixture
def dashboard_worker():
    return DashboardWorker()


@pytest.mark.asyncio
async def test_dashboard_worker_updates_metrics(dashboard_worker):
    """Should update dashboard metrics in Redis."""
    mock_redis = AsyncMock()
    # In redis-py asyncio, pipeline command methods (incr/hincrby/set) are
    # synchronous and return the pipeline; only execute() is awaited. Model the
    # mock the same way so no un-awaited coroutine warnings are emitted.
    mock_pipe = Mock()
    mock_pipe.execute = AsyncMock()
    mock_redis.pipeline = Mock(return_value=mock_pipe)

    with patch.object(dashboard_worker, "redis", mock_redis):
        await dashboard_worker.process({"decision": "block", "score": 85})

    mock_redis.pipeline.assert_called_once()
    mock_pipe.incr.assert_called_once_with("fraud:metrics:total_transactions")
    mock_pipe.hincrby.assert_any_call("fraud:metrics:decisions", "block", 1)
    mock_pipe.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_dashboard_worker_score_distribution(dashboard_worker):
    """Should update score distribution bucket."""
    mock_redis = AsyncMock()
    mock_pipe = Mock()
    mock_pipe.execute = AsyncMock()
    mock_redis.pipeline = Mock(return_value=mock_pipe)

    with patch.object(dashboard_worker, "redis", mock_redis):
        await dashboard_worker.process({"decision": "approve", "score": 35})

    mock_pipe.hincrby.assert_any_call("fraud:metrics:score_distribution", "30-39", 1)


# ---------------------------------------------------------------------------
# Dead Letter Handler Tests
# ---------------------------------------------------------------------------


@pytest.fixture
def dead_letter_handler():
    return DeadLetterHandler()


@pytest.mark.asyncio
async def test_get_dead_letter_count(dead_letter_handler):
    """Should return dead letter queue length."""
    mock_redis = AsyncMock()
    mock_redis.xinfo_stream.return_value = {"length": 5}

    with patch.object(dead_letter_handler, "redis", mock_redis):
        count = await dead_letter_handler.get_dead_letter_count()

    assert count == 5
    mock_redis.xinfo_stream.assert_awaited_once_with("fraud:dead_letter")


@pytest.mark.asyncio
async def test_peek_messages(dead_letter_handler):
    """Should peek at dead letter messages."""
    mock_redis = AsyncMock()
    mock_redis.xrange.return_value = [
        ("1234567890-0", {"data": "test"}),
    ]

    with patch.object(dead_letter_handler, "redis", mock_redis):
        messages = await dead_letter_handler.peek_messages(count=5)

    assert len(messages) == 1
    mock_redis.xrange.assert_awaited_once_with("fraud:dead_letter", count=5)


@pytest.mark.asyncio
async def test_reprocess_message_success(dead_letter_handler):
    """Should move message from dead letter to target stream."""
    mock_redis = AsyncMock()
    msg_id = "1234567890-0"
    fields = {"data": "test", "error": "old error"}
    mock_redis.xrange.return_value = [(msg_id, fields)]
    mock_redis.xadd.return_value = "new-id"

    with patch.object(dead_letter_handler, "redis", mock_redis):
        result = await dead_letter_handler.reprocess_message(msg_id, "fraud:alerts")

    assert result is True
    mock_redis.xadd.assert_awaited_once_with("fraud:alerts", fields)
    mock_redis.xdel.assert_awaited_once_with("fraud:dead_letter", msg_id)


@pytest.mark.asyncio
async def test_reprocess_message_not_found(dead_letter_handler):
    """Should return False when message not found."""
    mock_redis = AsyncMock()
    mock_redis.xrange.return_value = []

    with patch.object(dead_letter_handler, "redis", mock_redis):
        result = await dead_letter_handler.reprocess_message(
            "1234567890-0", "fraud:alerts"
        )

    assert result is False


@pytest.mark.asyncio
async def test_reprocess_message_failure(dead_letter_handler):
    """Should return False on reprocessing error."""
    mock_redis = AsyncMock()
    mock_redis.xrange.side_effect = Exception("Redis error")

    with patch.object(dead_letter_handler, "redis", mock_redis):
        result = await dead_letter_handler.reprocess_message(
            "1234567890-0", "fraud:alerts"
        )

    assert result is False
