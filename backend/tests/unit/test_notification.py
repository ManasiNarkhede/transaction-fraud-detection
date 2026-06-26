"""Unit tests for notification service."""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest

from app.services.notification import NotificationService


@pytest.fixture
def notification_service() -> NotificationService:
    return NotificationService()


@pytest.fixture
def sample_tx_id() -> UUID:
    return UUID("12345678-1234-5678-1234-567812345678")


RECIPIENT = {
    "recipient_email": "user@example.com",
    "recipient_phone": "+15551234567",
}


@pytest.mark.asyncio
async def test_send_fraud_alert_deduplicates(
    notification_service: NotificationService, sample_tx_id: UUID
) -> None:
    with patch(
        "app.services.notification.get_redis", return_value=AsyncMock()
    ) as mock_get:
        mock_redis = mock_get.return_value
        mock_redis.set.return_value = None

        result = await notification_service.send_fraud_alert(
            transaction_id=sample_tx_id,
            decision="block",
            score=95,
            reason="high_risk",
            **RECIPIENT,
        )

    assert result == {"deduplicated": True}


@pytest.mark.asyncio
async def test_send_fraud_alert_no_channels(
    notification_service: NotificationService, sample_tx_id: UUID
) -> None:
    with patch(
        "app.services.notification.get_redis", return_value=AsyncMock()
    ) as mock_get:
        mock_redis = mock_get.return_value
        mock_redis.set.return_value = True

        result = await notification_service.send_fraud_alert(
            transaction_id=sample_tx_id,
            decision="approve",
            score=30,
            reason="clean",
            **RECIPIENT,
        )

    assert result == {}


@pytest.mark.asyncio
async def test_send_fraud_alert_email_success(
    notification_service: NotificationService, sample_tx_id: UUID
) -> None:
    with patch(
        "app.services.notification.get_redis", return_value=AsyncMock()
    ) as mock_get:
        mock_redis = mock_get.return_value
        mock_redis.set.return_value = True

        with patch.object(
            notification_service.email, "send", new=AsyncMock(return_value=True)
        ) as mock_email:
            result = await notification_service.send_fraud_alert(
                transaction_id=sample_tx_id,
                decision="block",
                score=85,
                reason="high_amount",
                **RECIPIENT,
            )

    assert result["email"] is True
    mock_email.assert_awaited_once()
    assert mock_email.call_args.kwargs["to"] == "user@example.com"


@pytest.mark.asyncio
async def test_send_fraud_alert_email_failure(
    notification_service: NotificationService, sample_tx_id: UUID
) -> None:
    with patch(
        "app.services.notification.get_redis", return_value=AsyncMock()
    ) as mock_get:
        mock_redis = mock_get.return_value
        mock_redis.set.return_value = True

        with patch.object(
            notification_service.email, "send", new=AsyncMock(return_value=False)
        ) as mock_email:
            result = await notification_service.send_fraud_alert(
                transaction_id=sample_tx_id,
                decision="block",
                score=85,
                reason="high_amount",
                **RECIPIENT,
            )

    assert result["email"] is False
    assert mock_email.await_count == 3


@pytest.mark.asyncio
async def test_send_fraud_alert_sms_success(
    notification_service: NotificationService, sample_tx_id: UUID
) -> None:
    with patch(
        "app.services.notification.get_redis", return_value=AsyncMock()
    ) as mock_get:
        mock_redis = mock_get.return_value
        mock_redis.set.return_value = True

        with (
            patch.object(
                notification_service.email, "send", new=AsyncMock(return_value=True)
            ),
            patch.object(
                notification_service.sms, "send", new=AsyncMock(return_value=True)
            ) as mock_sms,
        ):
            result = await notification_service.send_fraud_alert(
                transaction_id=sample_tx_id,
                decision="block",
                score=95,
                reason="critical",
                **RECIPIENT,
            )

    assert result["sms"] is True
    mock_sms.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_fraud_alert_no_sms_for_medium_score(
    notification_service: NotificationService, sample_tx_id: UUID
) -> None:
    with patch(
        "app.services.notification.get_redis", return_value=AsyncMock()
    ) as mock_get:
        mock_redis = mock_get.return_value
        mock_redis.set.return_value = True

        with (
            patch.object(
                notification_service.sms, "send", new=AsyncMock(return_value=True)
            ) as mock_sms,
            patch.object(
                notification_service.email, "send", new=AsyncMock(return_value=True)
            ),
        ):
            result = await notification_service.send_fraud_alert(
                transaction_id=sample_tx_id,
                decision="block",
                score=85,
                reason="high_amount",
                **RECIPIENT,
            )

    assert "sms" not in result
    mock_sms.assert_not_awaited()


@pytest.mark.asyncio
async def test_send_fraud_alert_verify_email_only(
    notification_service: NotificationService, sample_tx_id: UUID
) -> None:
    with patch(
        "app.services.notification.get_redis", return_value=AsyncMock()
    ) as mock_get:
        mock_redis = mock_get.return_value
        mock_redis.set.return_value = True

        with (
            patch.object(
                notification_service.email, "send", new=AsyncMock(return_value=True)
            ) as mock_email,
            patch.object(
                notification_service.sms, "send", new=AsyncMock(return_value=True)
            ) as mock_sms,
        ):
            result = await notification_service.send_fraud_alert(
                transaction_id=sample_tx_id,
                decision="verify",
                score=60,
                reason="new_device",
                **RECIPIENT,
            )

    assert result["email"] is True
    assert "sms" not in result
    mock_email.assert_awaited_once()
    mock_sms.assert_not_awaited()


@pytest.mark.asyncio
async def test_send_fraud_alert_retry_then_success(
    notification_service: NotificationService, sample_tx_id: UUID
) -> None:
    with patch(
        "app.services.notification.get_redis", return_value=AsyncMock()
    ) as mock_get:
        mock_redis = mock_get.return_value
        mock_redis.set.return_value = True

        with (
            patch.object(
                notification_service.email,
                "send",
                new=AsyncMock(side_effect=[False, False, True]),
            ) as mock_email,
            patch("asyncio.sleep", new=AsyncMock()),
        ):
            result = await notification_service.send_fraud_alert(
                transaction_id=sample_tx_id,
                decision="block",
                score=85,
                reason="high_amount",
                **RECIPIENT,
            )

    assert result["email"] is True
    assert mock_email.await_count == 3


@pytest.mark.asyncio
async def test_send_fraud_alert_exception_handling(
    notification_service: NotificationService, sample_tx_id: UUID, caplog
) -> None:
    caplog.set_level(logging.ERROR, logger="app.services.notification")

    with patch(
        "app.services.notification.get_redis", return_value=AsyncMock()
    ) as mock_get:
        mock_redis = mock_get.return_value
        mock_redis.set.return_value = True

        with (
            patch.object(
                notification_service.email,
                "send",
                new=AsyncMock(side_effect=Exception("SMTP down")),
            ),
            patch("asyncio.sleep", new=AsyncMock()),
        ):
            result = await notification_service.send_fraud_alert(
                transaction_id=sample_tx_id,
                decision="block",
                score=85,
                reason="high_amount",
                **RECIPIENT,
            )

    assert result["email"] is False
    assert "SMTP down" in caplog.text
