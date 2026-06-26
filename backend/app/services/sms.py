"""Twilio SMS provider."""

from __future__ import annotations

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class SMSProvider:
    """Twilio SMS provider."""

    def __init__(self) -> None:
        self.account_sid = settings.twilio_account_sid
        self.auth_token = settings.twilio_auth_token
        self.from_number = settings.twilio_from_number
        self.base_url = "https://api.twilio.com/2010-04-01"

    async def send(self, to: str, message: str) -> bool:
        """Send an SMS via Twilio."""
        if not self.account_sid or not self.auth_token:
            logger.warning("Twilio credentials not configured")
            return False

        url = f"{self.base_url}/Accounts/{self.account_sid}/Messages.json"
        payload = {
            "To": to,
            "From": self.from_number,
            "Body": message,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    auth=(self.account_sid, self.auth_token),
                    data=payload,
                )
                response.raise_for_status()
                logger.info("SMS sent to %s", to)
                return True
        except Exception as exc:
            logger.exception("Failed to send SMS to %s: %s", to, exc)
            return False
