"""Unit tests for alert_service module."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.services.alert_service import AlertService


def _make_mock_alert(status: str = "open", severity: str = "medium") -> MagicMock:
    """Return a MagicMock with Alert-like attributes."""
    alert = MagicMock()
    alert.id = uuid4()
    alert.transaction_id = uuid4()
    alert.user_id = uuid4()
    alert.alert_type = "velocity"
    alert.severity = severity
    alert.status = status
    alert.assigned_to = None
    alert.resolved_at = None
    alert.created_at = datetime(2024, 6, 1, 12, 0, 0, tzinfo=UTC)
    return alert


@pytest.mark.asyncio
async def test_list_alerts_no_filters() -> None:
    """list_alerts should execute a query and return results with count."""
    mock_alert = _make_mock_alert()
    mock_session = AsyncMock()

    # count result
    mock_count_result = MagicMock()
    mock_count_result.scalar_one.return_value = 1

    # rows result
    mock_rows_result = MagicMock()
    mock_rows_result.scalars.return_value.all.return_value = [mock_alert]

    mock_session.execute = AsyncMock(side_effect=[mock_count_result, mock_rows_result])

    alerts, total = await AlertService.list_alerts(
        session=mock_session, owner_id=uuid4()
    )

    assert total == 1
    assert len(alerts) == 1
    assert alerts[0] is mock_alert


@pytest.mark.asyncio
async def test_get_alert_found() -> None:
    """get_alert should return the alert when found."""
    mock_alert = _make_mock_alert()
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_alert
    mock_session.execute = AsyncMock(return_value=mock_result)

    result = await AlertService.get_alert(
        session=mock_session, alert_id=mock_alert.id, owner_id=uuid4()
    )

    assert result is mock_alert


@pytest.mark.asyncio
async def test_get_alert_not_found() -> None:
    """get_alert should return None when not found."""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)

    result = await AlertService.get_alert(
        session=mock_session, alert_id=uuid4(), owner_id=uuid4()
    )

    assert result is None


@pytest.mark.asyncio
async def test_acknowledge_alert_transitions_open_to_investigating() -> None:
    """acknowledge_alert should set status to 'investigating' when open."""
    mock_alert = _make_mock_alert(status="open")
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_alert
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()

    result = await AlertService.acknowledge_alert(
        session=mock_session, alert_id=mock_alert.id, owner_id=uuid4()
    )

    assert result is mock_alert
    assert mock_alert.status == "investigating"
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_acknowledge_alert_no_op_when_already_resolved() -> None:
    """acknowledge_alert should not mutate status when already resolved."""
    mock_alert = _make_mock_alert(status="resolved")
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_alert
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()

    result = await AlertService.acknowledge_alert(
        session=mock_session, alert_id=mock_alert.id, owner_id=uuid4()
    )

    assert result is mock_alert
    # Status should remain 'resolved', no commit called
    assert mock_alert.status == "resolved"
    mock_session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_acknowledge_alert_not_found() -> None:
    """acknowledge_alert should return None when alert not found."""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)

    result = await AlertService.acknowledge_alert(
        session=mock_session, alert_id=uuid4(), owner_id=uuid4()
    )

    assert result is None


@pytest.mark.asyncio
async def test_resolve_alert_sets_resolved_status() -> None:
    """resolve_alert should set status to 'resolved' and resolved_at."""
    mock_alert = _make_mock_alert(status="investigating")
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_alert
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()

    result = await AlertService.resolve_alert(
        session=mock_session, alert_id=mock_alert.id, owner_id=uuid4()
    )

    assert result is mock_alert
    assert mock_alert.status == "resolved"
    assert mock_alert.resolved_at is not None
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_resolve_alert_not_found() -> None:
    """resolve_alert should return None when alert not found."""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)

    result = await AlertService.resolve_alert(
        session=mock_session, alert_id=uuid4(), owner_id=uuid4()
    )

    assert result is None
