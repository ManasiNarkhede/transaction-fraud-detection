"""Unit tests for the RedisStreamProducer."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.services.stream_producer import (
    STREAM_ALERTS,
    STREAM_AUDIT,
    STREAM_DASHBOARD,
    STREAM_RESULTS,
    RedisStreamProducer,
)


@pytest.fixture
def producer():
    return RedisStreamProducer()


@pytest.mark.asyncio
async def test_publish_scoring_result(producer):
    """Should publish scoring result to fraud:results stream."""
    tx_id = uuid4()
    mock_redis = AsyncMock()
    mock_redis.xadd.return_value = "1234567890-0"

    with patch.object(producer, "redis", mock_redis):
        msg_id = await producer.publish_scoring_result(
            transaction_id=tx_id,
            decision="block",
            score=85,
            reason="high_amount",
            features={"amount_zscore": 2.5},
            trace_id="trace-123",
        )

    assert msg_id == "1234567890-0"
    mock_redis.xadd.assert_awaited_once()
    call_args = mock_redis.xadd.call_args
    assert call_args[0][0] == STREAM_RESULTS
    assert call_args[1]["maxlen"] == 10000
    assert call_args[1]["approximate"] is True


@pytest.mark.asyncio
async def test_publish_alert(producer):
    """Should publish alert to fraud:alerts stream."""
    tx_id = uuid4()
    mock_redis = AsyncMock()
    mock_redis.xadd.return_value = "1234567890-1"

    with patch.object(producer, "redis", mock_redis):
        msg_id = await producer.publish_alert(
            transaction_id=tx_id,
            decision="block",
            score=85,
            reason="high_amount",
            trace_id="trace-123",
        )

    assert msg_id == "1234567890-1"
    mock_redis.xadd.assert_awaited_once()
    call_args = mock_redis.xadd.call_args
    assert call_args[0][0] == STREAM_ALERTS


@pytest.mark.asyncio
async def test_publish_audit_event(producer):
    """Should publish audit event to fraud:audit stream."""
    tx_id = uuid4()
    mock_redis = AsyncMock()
    mock_redis.xadd.return_value = "1234567890-2"

    with patch.object(producer, "redis", mock_redis):
        msg_id = await producer.publish_audit_event(
            transaction_id=tx_id,
            audit_data={"action": "decision_made", "details": "test"},
            trace_id="trace-123",
        )

    assert msg_id == "1234567890-2"
    mock_redis.xadd.assert_awaited_once()
    call_args = mock_redis.xadd.call_args
    assert call_args[0][0] == STREAM_AUDIT


@pytest.mark.asyncio
async def test_publish_dashboard_update(producer):
    """Should publish dashboard update to fraud:dashboard stream."""
    tx_id = uuid4()
    mock_redis = AsyncMock()
    mock_redis.xadd.return_value = "1234567890-3"

    with patch.object(producer, "redis", mock_redis):
        msg_id = await producer.publish_dashboard_update(
            transaction_id=tx_id,
            metrics={"decision": "approve", "score": 30},
            trace_id="trace-123",
        )

    assert msg_id == "1234567890-3"
    mock_redis.xadd.assert_awaited_once()
    call_args = mock_redis.xadd.call_args
    assert call_args[0][0] == STREAM_DASHBOARD


@pytest.mark.asyncio
async def test_publish_uses_default_trace_id(producer):
    """Should use 'unknown' as default trace_id when not provided."""
    tx_id = uuid4()
    mock_redis = AsyncMock()
    mock_redis.xadd.return_value = "1234567890-4"

    with patch.object(producer, "redis", mock_redis):
        await producer.publish_scoring_result(
            transaction_id=tx_id,
            decision="approve",
            score=30,
            reason="No risk signals detected",
            features={},
        )

    call_args = mock_redis.xadd.call_args
    assert call_args[0][1]["trace_id"] == "unknown"


@pytest.mark.asyncio
async def test_publish_includes_timestamp(producer):
    """Should include ISO timestamp in published message."""
    tx_id = uuid4()
    mock_redis = AsyncMock()
    mock_redis.xadd.return_value = "1234567890-5"

    with patch.object(producer, "redis", mock_redis):
        await producer.publish_scoring_result(
            transaction_id=tx_id,
            decision="approve",
            score=30,
            reason="test",
            features={},
        )

    call_args = mock_redis.xadd.call_args
    assert "timestamp" in call_args[0][1]
    assert "T" in call_args[0][1]["timestamp"]  # ISO format check
