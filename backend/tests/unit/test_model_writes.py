"""Unit tests for blocked-transaction and alert repository writes."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.repositories.alert_repository import AlertRepository
from app.repositories.blocked_transaction_repository import (
    BlockedTransactionRepository,
)


def _mock_session() -> MagicMock:
    session = MagicMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    execute_result = MagicMock()
    execute_result.scalar_one_or_none = MagicMock(return_value=None)
    session.execute = AsyncMock(return_value=execute_result)
    return session


@pytest.mark.asyncio
async def test_record_block_persists_row():
    """record_block adds a BlockedTransaction with the given fields."""
    session = _mock_session()
    repo = BlockedTransactionRepository(session)
    tx_id, user_id = uuid4(), uuid4()

    blocked = await repo.record_block(
        transaction_id=tx_id,
        user_id=user_id,
        reason="high_amount (score=85)",
        rule_triggered="high_amount",
    )

    session.add.assert_called_once()
    session.commit.assert_awaited_once()
    assert blocked.transaction_id == tx_id
    assert blocked.user_id == user_id
    assert blocked.reason == "high_amount (score=85)"
    assert blocked.rule_triggered == "high_amount"
    assert blocked.blocked_at is not None


@pytest.mark.asyncio
async def test_create_alert_persists_row():
    """create_alert adds an Alert with mapped type and severity."""
    session = _mock_session()
    repo = AlertRepository(session)
    tx_id, user_id = uuid4(), uuid4()

    alert = await repo.create_alert(
        transaction_id=tx_id,
        user_id=user_id,
        alert_type="block",
        severity="high",
    )

    session.add.assert_called_once()
    session.commit.assert_awaited_once()
    assert alert.transaction_id == tx_id
    assert alert.user_id == user_id
    assert alert.alert_type == "block"
    assert alert.severity == "high"
    assert alert.status == "open"
