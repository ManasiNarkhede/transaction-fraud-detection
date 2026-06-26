"""VerificationLog model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.transaction import Transaction
    from app.models.user import User


class VerificationLog(BaseModel):
    """Log of verification attempts for a transaction."""

    __tablename__ = "verification_logs"

    __table_args__ = (
        Index("ix_verification_logs_transaction_id", "transaction_id"),
        Index("ix_verification_logs_user_id", "user_id"),
        Index("ix_verification_logs_state", "state"),
        Index("ix_verification_logs_created_at", "created_at"),
    )

    transaction_id: Mapped[UUID] = mapped_column(
        ForeignKey("transactions.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    state: Mapped[str] = mapped_column(String(20), default="PENDING", nullable=False)
    otp_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    otp_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    otp_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    channel: Mapped[str | None] = mapped_column(String(20), nullable=True)
    contact_info: Mapped[str | None] = mapped_column(String(255), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    failed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expired_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    transaction: Mapped[Transaction] = relationship(
        "Transaction", back_populates="verification_logs"
    )
    user: Mapped[User] = relationship("User", back_populates="verification_logs")
