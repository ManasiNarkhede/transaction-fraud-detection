"""Verification service for OTP-based transaction verification.

Implements a state machine for verification records with OTP generation,
validation, expiration handling, and rate limiting.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fraud_score import FraudScore
from app.models.transaction import Transaction
from app.models.user import User
from app.models.verification_log import VerificationLog
from app.services import otp_service
from app.services.notification import NotificationService

logger = logging.getLogger(__name__)

OTP_TTL_SECONDS = 600

# Valid state transitions: PENDING -> VERIFIED/FAILED/EXPIRED
_VALID_TRANSITIONS = {
    "PENDING": {"VERIFIED", "FAILED", "EXPIRED"},
}

_EMAIL_RE = re.compile(r"^([^@]{1,3})[^@]*@([^.]{1,3})[^.]*\.(.+)$")
_DIGITS_RE = re.compile(r"\d")


def _mask_contact(value: str | None) -> str | None:
    """Mask PII in a contact_info value before returning it in API responses.

    Email addresses are masked as ``a***@d***.com`` (first 1-3 chars of local
    part and domain visible, rest replaced with ``***``).
    Phone numbers and any other strings are masked to show only the last 4
    digits/characters with the rest replaced by ``***``.

    The original value stored in the database is never modified.
    """
    if value is None:
        return None
    email_match = _EMAIL_RE.match(value)
    if email_match:
        local_prefix, domain_prefix, tld = email_match.groups()
        return f"{local_prefix}***@{domain_prefix}***.{tld}"
    # Phone or generic string: keep last 4, mask the rest.
    if len(value) <= 4:
        return "***"
    return f"***{value[-4:]}"


class VerificationService:
    """Service for managing transaction verification lifecycle."""

    def __init__(self) -> None:
        self.notification = NotificationService()

    async def create_verification(
        self,
        session: AsyncSession,
        transaction_id: UUID,
        user_id: UUID,
        channel: str,
        contact_info: str,
    ) -> VerificationLog:
        """Create a new verification record.

        Args:
            session: Active async SQLAlchemy session.
            transaction_id: UUID of the transaction to verify.
            user_id: UUID of the user owning the transaction.
            channel: Notification channel (e.g., "sms", "email").
            contact_info: Contact address for OTP delivery.

        Returns:
            The created VerificationLog record.
        """
        verification = VerificationLog(
            transaction_id=transaction_id,
            user_id=user_id,
            state="PENDING",
            channel=channel,
            contact_info=contact_info,
            attempts=0,
            max_attempts=3,
        )
        session.add(verification)
        await session.commit()
        await session.refresh(verification)

        logger.info(
            "verification_created",
            extra={
                "verification_id": str(verification.id),
                "transaction_id": str(transaction_id),
                "user_id": str(user_id),
                "channel": channel,
            },
        )
        return verification

    async def create_pending_for_verify_transaction(
        self,
        session: AsyncSession,
        transaction_id: UUID,
        owner_id: UUID,
    ) -> VerificationLog | None:
        """Create (or return) a PENDING verification for a medium-risk transaction."""
        tx_stmt = select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.owner_id == owner_id,
        )
        tx_result = await session.execute(tx_stmt)
        transaction = tx_result.scalar_one_or_none()
        if transaction is None or transaction.status != "verify":
            return None

        existing_stmt = select(VerificationLog).where(
            VerificationLog.transaction_id == transaction_id,
            VerificationLog.state == "PENDING",
        )
        existing_result = await session.execute(existing_stmt)
        existing = existing_result.scalar_one_or_none()
        if existing is not None:
            return existing

        verification = VerificationLog(
            transaction_id=transaction_id,
            user_id=owner_id,
            state="PENDING",
            channel=None,
            contact_info=None,
            attempts=0,
            max_attempts=3,
        )
        session.add(verification)
        await session.commit()
        await session.refresh(verification)
        logger.info(
            "verification_pending_created",
            extra={
                "verification_id": str(verification.id),
                "transaction_id": str(transaction_id),
            },
        )
        return verification

    async def deliver_otp(
        self,
        session: AsyncSession,
        verification_id: UUID,
        owner_id: UUID,
        channel: str,
    ) -> dict[str, Any]:
        """Generate and send an OTP for a pending verification via email or SMS."""
        verification = await self._get_verification(
            session, verification_id, owner_id=owner_id
        )
        if verification is None:
            raise ValueError("Verification not found")
        if verification.state != "PENDING":
            raise ValueError(f"Verification is already {verification.state}")

        user_stmt = select(User).where(User.id == owner_id)
        user_result = await session.execute(user_stmt)
        user = user_result.scalar_one_or_none()
        if user is None:
            raise ValueError("User not found")

        normalized_channel = channel.lower().strip()
        contact: str
        if normalized_channel == "email":
            if not user.email:
                raise ValueError("No email on file for this account")
            contact = user.email
        elif normalized_channel == "sms":
            if not user.phone:
                raise ValueError(
                    "No phone number on file. Register with a phone number to use SMS OTP."
                )
            contact = user.phone
        else:
            raise ValueError("Channel must be 'email' or 'sms'")

        if await otp_service.is_rate_limited(owner_id):
            raise ValueError("Too many OTP requests. Please try again later.")

        otp = otp_service.generate_otp()
        expires_at = datetime.now(UTC) + timedelta(seconds=OTP_TTL_SECONDS)
        verification.channel = normalized_channel
        verification.contact_info = contact
        verification.otp_sent_at = datetime.now(UTC)
        verification.otp_expires_at = expires_at
        await session.commit()

        await otp_service.store_otp(verification_id, otp, ttl=OTP_TTL_SECONDS)
        sent = await self._send_otp_notification(
            normalized_channel,
            contact,
            otp,
            verification.transaction_id,
        )
        if not sent:
            logger.warning(
                "otp_delivery_failed",
                extra={
                    "verification_id": str(verification_id),
                    "channel": normalized_channel,
                },
            )

        return {
            "verification_id": str(verification_id),
            "channel": normalized_channel,
            "contact_info": _mask_contact(contact),
            "expires_at": expires_at.isoformat(),
            "delivery_attempted": sent,
        }

    async def send_otp(self, verification_id: UUID, otp: str) -> None:
        """Store OTP in Redis (legacy helper; prefer deliver_otp)."""
        await otp_service.store_otp(verification_id, otp, ttl=OTP_TTL_SECONDS)
        logger.info(
            "otp_stored",
            extra={"verification_id": str(verification_id)},
        )

    async def validate_otp(
        self,
        session: AsyncSession,
        verification_id: UUID,
        otp: str,
        owner_id: UUID | None = None,
    ) -> dict:
        """Validate an OTP, update verification state, and return result.

        Args:
            session: Active async SQLAlchemy session.
            verification_id: UUID of the verification record.
            otp: The plain-text OTP submitted by the user.

        Returns:
            Dict with success (bool), state (str), and message (str).
        """
        verification = await self._get_verification(
            session, verification_id, owner_id=owner_id
        )
        if verification is None:
            return {
                "success": False,
                "state": "NOT_FOUND",
                "message": "Verification record not found",
            }

        if verification.state != "PENDING":
            return {
                "success": False,
                "state": verification.state,
                "message": f"Verification is already {verification.state}",
            }

        # Check if OTP has expired (DB datetimes are naive UTC; normalize)
        otp_expires_at = verification.otp_expires_at
        if otp_expires_at is not None and otp_expires_at.tzinfo is None:
            otp_expires_at = otp_expires_at.replace(tzinfo=UTC)
        if otp_expires_at and datetime.now(UTC) > otp_expires_at:
            await self.handle_expiration(session, verification_id)
            return {
                "success": False,
                "state": "EXPIRED",
                "message": "OTP has expired",
            }

        # Increment attempt counter
        verification.attempts += 1
        await session.commit()

        # Check max attempts
        if verification.attempts > verification.max_attempts:
            await self._transition_state(verification, "FAILED")
            await self._update_transaction_status(
                session, verification.transaction_id, "manual_review"
            )
            await session.commit()
            return {
                "success": False,
                "state": "FAILED",
                "message": "Maximum attempts exceeded",
            }

        # Validate OTP against stored hash
        otp_data = await otp_service.get_otp_data(verification_id)
        if otp_data is None:
            return {
                "success": False,
                "state": "PENDING",
                "message": "OTP not found or expired",
            }

        is_valid = otp_service.verify_otp(otp, otp_data["hash"])
        if is_valid:
            await self._transition_state(verification, "VERIFIED")
            await self._update_transaction_status(
                session, verification.transaction_id, "approved"
            )
            await otp_service.delete_otp(verification_id)
            await session.commit()
            return {
                "success": True,
                "state": "VERIFIED",
                "message": "OTP verified successfully",
            }

        # Invalid OTP - check if this was the last attempt
        if verification.attempts >= verification.max_attempts:
            await self._transition_state(verification, "FAILED")
            await self._update_transaction_status(
                session, verification.transaction_id, "manual_review"
            )
            await otp_service.delete_otp(verification_id)
            await session.commit()
            return {
                "success": False,
                "state": "FAILED",
                "message": "Maximum attempts exceeded",
            }

        await session.commit()
        return {
            "success": False,
            "state": "PENDING",
            "message": "Invalid OTP",
        }

    async def approve(
        self,
        session: AsyncSession,
        verification_id: UUID,
        owner_id: UUID | None = None,
    ) -> VerificationLog:
        """Manually approve a pending verification (analyst/admin manual review).

        Marks the verification as VERIFIED and updates the linked transaction
        status to 'approved'.

        Args:
            session: Active async SQLAlchemy session.
            verification_id: UUID of the verification record.

        Returns:
            The updated VerificationLog record.

        Raises:
            ValueError: If the verification is not found or not in PENDING state.
        """
        verification = await self._get_verification(
            session, verification_id, owner_id=owner_id
        )
        if verification is None:
            raise ValueError(f"Verification {verification_id} not found")

        await self._transition_state(verification, "VERIFIED")
        await self._update_transaction_status(
            session, verification.transaction_id, "approved"
        )
        await otp_service.delete_otp(verification_id)
        await session.commit()

        logger.info(
            "verification_approved",
            extra={
                "verification_id": str(verification_id),
                "transaction_id": str(verification.transaction_id),
            },
        )
        return verification

    async def reject(
        self,
        session: AsyncSession,
        verification_id: UUID,
        owner_id: UUID | None = None,
    ) -> VerificationLog:
        """Manually reject a pending verification (analyst/admin manual review).

        Marks the verification as FAILED and updates the linked transaction
        status to 'block'.

        Args:
            session: Active async SQLAlchemy session.
            verification_id: UUID of the verification record.

        Returns:
            The updated VerificationLog record.

        Raises:
            ValueError: If the verification is not found or not in PENDING state.
        """
        verification = await self._get_verification(
            session, verification_id, owner_id=owner_id
        )
        if verification is None:
            raise ValueError(f"Verification {verification_id} not found")

        await self._transition_state(verification, "FAILED")
        await self._update_transaction_status(
            session, verification.transaction_id, "block"
        )
        await otp_service.delete_otp(verification_id)
        await session.commit()

        logger.info(
            "verification_rejected",
            extra={
                "verification_id": str(verification_id),
                "transaction_id": str(verification.transaction_id),
            },
        )
        return verification

    async def escalate(
        self,
        session: AsyncSession,
        verification_id: UUID,
        owner_id: UUID | None = None,
    ) -> VerificationLog:
        """Manually escalate a verification to FAILED.

        Args:
            session: Active async SQLAlchemy session.
            verification_id: UUID of the verification record.

        Returns:
            The updated VerificationLog record.

        Raises:
            ValueError: If the verification is not in PENDING state.
        """
        verification = await self._get_verification(
            session, verification_id, owner_id=owner_id
        )
        if verification is None:
            raise ValueError(f"Verification {verification_id} not found")

        await self._transition_state(verification, "FAILED")
        await self._update_transaction_status(
            session, verification.transaction_id, "manual_review"
        )
        await otp_service.delete_otp(verification_id)
        await session.commit()

        logger.info(
            "verification_escalated",
            extra={
                "verification_id": str(verification_id),
                "transaction_id": str(verification.transaction_id),
            },
        )
        return verification

    async def get_status(
        self,
        session: AsyncSession,
        verification_id: UUID,
        owner_id: UUID | None = None,
    ) -> dict:
        """Get the current status of a verification.

        Args:
            session: Active async SQLAlchemy session.
            verification_id: UUID of the verification record.

        Returns:
            Dict with verification details and current state.
        """
        verification = await self._get_verification(
            session, verification_id, owner_id=owner_id
        )
        if verification is None:
            return {
                "found": False,
                "verification_id": str(verification_id),
                "state": "NOT_FOUND",
            }

        return {
            "found": True,
            "verification_id": str(verification.id),
            "transaction_id": str(verification.transaction_id),
            "user_id": str(verification.user_id),
            "state": verification.state,
            "attempts": verification.attempts,
            "max_attempts": verification.max_attempts,
            "channel": verification.channel,
            "contact_info": _mask_contact(verification.contact_info),
            "created_at": verification.created_at.isoformat()
            if verification.created_at
            else None,
            "verified_at": verification.verified_at.isoformat()
            if verification.verified_at
            else None,
            "failed_at": verification.failed_at.isoformat()
            if verification.failed_at
            else None,
            "expired_at": verification.expired_at.isoformat()
            if verification.expired_at
            else None,
            "expires_at": verification.otp_expires_at.isoformat()
            if verification.otp_expires_at
            else None,
        }

    async def get_queue(
        self,
        session: AsyncSession,
        owner_id: UUID,
        state: str = "PENDING",
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List verifications for transactions owned by this account."""
        stmt = (
            select(
                VerificationLog,
                Transaction.amount,
                Transaction.currency,
                Transaction.status,
                FraudScore.score,
            )
            .join(Transaction, Transaction.id == VerificationLog.transaction_id)
            .outerjoin(
                FraudScore, FraudScore.transaction_id == VerificationLog.transaction_id
            )
            .where(
                Transaction.owner_id == owner_id,
                VerificationLog.state == state,
            )
            .order_by(VerificationLog.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await session.execute(stmt)
        items: list[dict[str, Any]] = []
        for row in result.all():
            verification, amount, currency, tx_status, risk_score = row
            items.append(
                {
                    "verification": verification,
                    "amount": amount,
                    "currency": currency,
                    "transaction_status": tx_status,
                    "risk_score": int(risk_score) if risk_score is not None else None,
                }
            )
        return items

    async def handle_expiration(
        self,
        session: AsyncSession,
        verification_id: UUID,
    ) -> VerificationLog:
        """Mark a verification as EXPIRED.

        Args:
            session: Active async SQLAlchemy session.
            verification_id: UUID of the verification record.

        Returns:
            The updated VerificationLog record.

        Raises:
            ValueError: If the verification is not in PENDING state.
        """
        verification = await self._get_verification(session, verification_id)
        if verification is None:
            raise ValueError(f"Verification {verification_id} not found")

        await self._transition_state(verification, "EXPIRED")
        await self._update_transaction_status(
            session, verification.transaction_id, "manual_review"
        )
        await otp_service.delete_otp(verification_id)
        await session.commit()

        logger.info(
            "verification_expired",
            extra={
                "verification_id": str(verification_id),
                "transaction_id": str(verification.transaction_id),
            },
        )
        return verification

    async def _transition_state(
        self,
        verification: VerificationLog,
        new_state: str,
    ) -> None:
        """Validate and perform a state transition.

        Args:
            verification: The VerificationLog to update.
            new_state: The target state.

        Raises:
            ValueError: If the transition is not allowed.
        """
        current_state = verification.state
        allowed = _VALID_TRANSITIONS.get(current_state, set())

        if new_state not in allowed:
            raise ValueError(
                f"Invalid state transition: {current_state} -> {new_state}"
            )

        now = datetime.now(UTC)

        if new_state == "VERIFIED":
            verification.verified_at = now
        elif new_state == "FAILED":
            verification.failed_at = now
        elif new_state == "EXPIRED":
            verification.expired_at = now

        verification.state = new_state

        logger.info(
            "verification_state_transition",
            extra={
                "verification_id": str(verification.id),
                "transaction_id": str(verification.transaction_id),
                "from_state": current_state,
                "to_state": new_state,
            },
        )

    async def _get_verification(
        self,
        session: AsyncSession,
        verification_id: UUID,
        owner_id: UUID | None = None,
    ) -> VerificationLog | None:
        """Fetch a verification record by ID, optionally scoped to an owner."""
        if owner_id is not None:
            stmt = (
                select(VerificationLog)
                .join(Transaction, Transaction.id == VerificationLog.transaction_id)
                .where(
                    VerificationLog.id == verification_id,
                    Transaction.owner_id == owner_id,
                )
            )
        else:
            stmt = select(VerificationLog).where(VerificationLog.id == verification_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def _update_transaction_status(
        self,
        session: AsyncSession,
        transaction_id: UUID,
        status: str,
    ) -> None:
        """Update the status of a transaction.

        Args:
            session: Active async SQLAlchemy session.
            transaction_id: UUID of the transaction to update.
            status: New status string.
        """
        stmt = select(Transaction).where(Transaction.id == transaction_id)
        result = await session.execute(stmt)
        transaction = result.scalar_one_or_none()

        if transaction is not None:
            transaction.status = status
            logger.info(
                "transaction_status_updated",
                extra={
                    "transaction_id": str(transaction_id),
                    "status": status,
                },
            )
        else:
            logger.warning(
                "transaction_not_found_for_status_update",
                extra={"transaction_id": str(transaction_id)},
            )

    async def _send_otp_notification(
        self,
        channel: str,
        contact: str,
        otp: str,
        transaction_id: UUID,
    ) -> bool:
        """Deliver OTP via SMTP (email) or Twilio (SMS)."""
        subject = "Verify your transaction — FraudGuard"
        body = (
            f"Your verification code is {otp}.\n"
            f"It expires in {OTP_TTL_SECONDS // 60} minutes.\n"
            f"Transaction ID: {transaction_id}"
        )
        if channel == "email":
            return await self.notification.email.send(
                to=contact,
                subject=subject,
                body=body,
            )
        if channel == "sms":
            sms_body = (
                f"FraudGuard verification code: {otp}. "
                f"Expires in {OTP_TTL_SECONDS // 60} min."
            )
            return await self.notification.sms.send(to=contact, message=sms_body)
        return False
