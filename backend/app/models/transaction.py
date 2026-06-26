"""Transaction model."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.alert import Alert
    from app.models.blocked_transaction import BlockedTransaction
    from app.models.fraud_decision_audit import FraudDecisionAudit
    from app.models.fraud_score import FraudScore
    from app.models.user import User
    from app.models.verification_log import VerificationLog


class Transaction(BaseModel):
    """Financial transaction model."""

    __tablename__ = "transactions"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    owner_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    amount: Mapped[Decimal] = mapped_column(nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    merchant_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    merchant_category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    card_last_four: Mapped[str | None] = mapped_column(String(4), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    device_fingerprint: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)

    # Relationships
    user: Mapped[User] = relationship(
        "User",
        back_populates="transactions",
        foreign_keys=[user_id],
    )
    owner: Mapped[User] = relationship(
        "User",
        back_populates="owned_transactions",
        foreign_keys=[owner_id],
    )
    fraud_scores: Mapped[list[FraudScore]] = relationship(
        "FraudScore", back_populates="transaction", cascade="all, delete-orphan"
    )
    fraud_decision_audits: Mapped[list[FraudDecisionAudit]] = relationship(
        "FraudDecisionAudit",
        back_populates="transaction",
        cascade="all, delete-orphan",
    )
    blocked_transactions: Mapped[list[BlockedTransaction]] = relationship(
        "BlockedTransaction",
        back_populates="transaction",
        cascade="all, delete-orphan",
    )
    verification_logs: Mapped[list[VerificationLog]] = relationship(
        "VerificationLog",
        back_populates="transaction",
        cascade="all, delete-orphan",
    )
    alerts: Mapped[list[Alert]] = relationship(
        "Alert", back_populates="transaction", cascade="all, delete-orphan"
    )
