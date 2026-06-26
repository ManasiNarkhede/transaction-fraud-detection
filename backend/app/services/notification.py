"""Main notification service with deduplication."""

from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from app.infrastructure.redis_client import get_redis
from app.services.alert_router import AlertRouter
from app.services.email import EmailProvider
from app.services.sms import SMSProvider

logger = logging.getLogger(__name__)


class NotificationService:
    """Orchestrates fraud notifications to the account owner's contacts."""

    def __init__(self) -> None:
        self.email = EmailProvider()
        self.sms = SMSProvider()
        self.router = AlertRouter()
        self.max_retries = 3

    async def _is_duplicate(self, transaction_id: str) -> bool:
        """Check if notification was already sent for this transaction."""
        redis_client = get_redis()
        if redis_client is None:
            return False
        key = f"fraud:notification:{transaction_id}"
        result = await redis_client.set(key, "1", nx=True, ex=3600)
        return result is None

    async def send_fraud_alert(
        self,
        transaction_id: UUID,
        decision: str,
        score: int,
        reason: str,
        *,
        recipient_email: str | None = None,
        recipient_phone: str | None = None,
    ) -> dict[str, bool]:
        """Send a fraud alert to the account owner's email and/or phone."""
        tx_id = str(transaction_id)

        if await self._is_duplicate(tx_id):
            logger.info("Duplicate notification suppressed for %s", tx_id)
            return {"deduplicated": True}

        channels = self.router.route_alert(decision, score)
        if not channels:
            logger.debug(
                "No channels configured for decision=%s, score=%d", decision, score
            )
            return {}

        priority = self.router.get_priority(decision, score)
        subject = f"Fraud Alert: {decision.upper()} (Score: {score})"
        body = (
            f"Transaction {tx_id} was flagged as {decision} with score {score}.\n"
            f"Reason: {reason}\n"
            f"Priority: {priority}\n\n"
        )
        if decision == "verify":
            body += (
                "Open the Verifications page in FraudGuard to complete OTP "
                "confirmation before this transaction can be approved."
            )
        else:
            body += "Review this transaction in your FraudGuard dashboard."

        results: dict[str, bool] = {}

        for channel in channels:
            if channel == "email" and not recipient_email:
                logger.warning(
                    "alert_email_skipped_no_recipient",
                    extra={"transaction_id": tx_id},
                )
                continue
            if channel == "sms" and not recipient_phone:
                logger.warning(
                    "alert_sms_skipped_no_phone",
                    extra={"transaction_id": tx_id},
                )
                continue

            for attempt in range(self.max_retries):
                try:
                    if channel == "email":
                        success = await self.email.send(
                            to=recipient_email or "",
                            subject=subject,
                            body=body,
                        )
                    elif channel == "sms":
                        success = await self.sms.send(
                            to=recipient_phone or "",
                            message=body[:160],
                        )
                    else:
                        continue

                    results[channel] = success
                    if success:
                        break
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(2**attempt)
                except Exception as exc:
                    logger.exception(
                        "Notification attempt %d failed for %s: %s",
                        attempt + 1,
                        channel,
                        exc,
                    )
                    results[channel] = False

        logger.info("Notification results for %s: %s", tx_id, results)
        return results
