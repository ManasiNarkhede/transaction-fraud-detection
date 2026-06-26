"""Unit tests for the worker runner entrypoint and alert persistence."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.workers import run as worker_run
from app.workers.alert_worker import AlertWorker

# ---------------------------------------------------------------------------
# Worker runner loops
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_worker_consumes_until_stop():
    """_run_worker creates the group and consumes until stop is set."""
    worker = MagicMock()
    worker.stream_name = "fraud:test"
    worker._create_group = AsyncMock()

    stop = asyncio.Event()
    call_count = {"n": 0}

    async def fake_consume(count: int, block: int) -> None:
        call_count["n"] += 1
        if call_count["n"] >= 2:
            stop.set()

    worker.consume = AsyncMock(side_effect=fake_consume)

    await worker_run._run_worker(worker, stop)

    worker._create_group.assert_awaited_once()
    assert call_count["n"] >= 2


@pytest.mark.asyncio
async def test_run_worker_survives_consume_error():
    """A consume error is logged and the loop continues, not crashes."""
    worker = MagicMock()
    worker.stream_name = "fraud:test"
    worker._create_group = AsyncMock()

    stop = asyncio.Event()
    state = {"n": 0}

    async def flaky_consume(count: int, block: int) -> None:
        state["n"] += 1
        if state["n"] == 1:
            raise RuntimeError("redis blip")
        stop.set()

    worker.consume = AsyncMock(side_effect=flaky_consume)

    with patch("app.workers.run.asyncio.sleep", new=AsyncMock()):
        await worker_run._run_worker(worker, stop)

    assert state["n"] >= 2


@pytest.mark.asyncio
async def test_dead_letter_monitor_reports_depth():
    """Monitor queries DLQ depth, then exits when stop is set."""
    handler = MagicMock()
    handler.get_dead_letter_count = AsyncMock(return_value=3)

    stop = asyncio.Event()

    async def stop_soon() -> None:
        await asyncio.sleep(0)
        stop.set()

    with patch("app.workers.run.DEAD_LETTER_POLL_SECONDS", 0.01):
        await asyncio.gather(
            worker_run._run_dead_letter_monitor(handler, stop), stop_soon()
        )

    handler.get_dead_letter_count.assert_awaited()


# ---------------------------------------------------------------------------
# Alert worker persistence
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_alert_worker_persists_alert():
    """AlertWorker persists an Alert row for a block decision."""
    worker = AlertWorker()
    worker.notification_service.send_fraud_alert = AsyncMock()

    tx_id, user_id = uuid4(), uuid4()

    fake_session = AsyncMock()
    fake_maker = MagicMock()
    fake_maker.return_value.__aenter__ = AsyncMock(return_value=fake_session)
    fake_maker.return_value.__aexit__ = AsyncMock(return_value=False)

    mock_repo = MagicMock()
    mock_repo.create_alert = AsyncMock()

    with (
        patch("app.workers.alert_worker.get_session_maker", return_value=fake_maker),
        patch("app.workers.alert_worker.AlertRepository", return_value=mock_repo),
        patch.object(
            worker,
            "_resolve_user_contact",
            new=AsyncMock(
                return_value={"email": "user@example.com", "phone": "+15551234567"}
            ),
        ),
    ):
        await worker.process(
            {
                "transaction_id": str(tx_id),
                "user_id": str(user_id),
                "decision": "block",
                "score": 90,
                "reason": "high_amount",
            }
        )

    mock_repo.create_alert.assert_awaited_once()
    kwargs = mock_repo.create_alert.call_args.kwargs
    assert kwargs["transaction_id"] == tx_id
    assert kwargs["user_id"] == user_id
    assert kwargs["alert_type"] == "block"
    worker.notification_service.send_fraud_alert.assert_awaited_once()


@pytest.mark.asyncio
async def test_alert_worker_skips_persist_for_approve():
    """No alert is persisted for an approve decision."""
    worker = AlertWorker()
    with patch("app.workers.alert_worker.AlertRepository") as mock_repo_cls:
        await worker.process({"decision": "approve", "score": 10})
    mock_repo_cls.assert_not_called()
