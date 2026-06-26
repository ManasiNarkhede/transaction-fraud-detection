"""SMTP email provider for OTP codes and fraud alerts."""

from __future__ import annotations

import asyncio
import logging
import smtplib
from email.message import EmailMessage

from app.config import settings

logger = logging.getLogger(__name__)


class EmailProvider:
    """Send email via SMTP (STARTTLS or SSL)."""

    def __init__(self) -> None:
        self.smtp_host = settings.smtp_host
        self.smtp_port = settings.smtp_port
        self.smtp_username = settings.smtp_username
        self.smtp_password = settings.smtp_password
        self.smtp_use_tls = settings.smtp_use_tls
        self.from_email = settings.notification_from_email

    def _send_sync(
        self,
        to: str,
        subject: str,
        body: str,
        html_body: str | None = None,
    ) -> bool:
        if not self.smtp_host:
            logger.warning("SMTP host not configured")
            return False

        message = EmailMessage()
        message["From"] = self.from_email
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)
        if html_body:
            message.add_alternative(html_body, subtype="html")

        if self.smtp_use_tls:
            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=30) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                if self.smtp_username:
                    server.login(self.smtp_username, self.smtp_password)
                server.send_message(message)
        else:
            with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, timeout=30) as server:
                if self.smtp_username:
                    server.login(self.smtp_username, self.smtp_password)
                server.send_message(message)

        logger.info("Email sent to %s", to)
        return True

    async def send(
        self, to: str, subject: str, body: str, html_body: str | None = None
    ) -> bool:
        """Send an email via SMTP without blocking the event loop."""
        try:
            return await asyncio.to_thread(
                self._send_sync, to, subject, body, html_body
            )
        except Exception as exc:
            logger.exception("Failed to send email to %s: %s", to, exc)
            return False
