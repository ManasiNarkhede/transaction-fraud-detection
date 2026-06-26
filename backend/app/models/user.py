"""User model."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.alert import Alert
    from app.models.blocked_transaction import BlockedTransaction
    from app.models.device import Device
    from app.models.fraud_score import FraudScore
    from app.models.transaction import Transaction
    from app.models.verification_log import VerificationLog


class User(BaseModel):
    """User account model."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    role: Mapped[str] = mapped_column(String(50), default="analyst", nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    # Relationships
    devices: Mapped[list[Device]] = relationship(
        "Device", back_populates="user", cascade="all, delete-orphan"
    )
    transactions: Mapped[list[Transaction]] = relationship(
        "Transaction",
        back_populates="user",
        foreign_keys="Transaction.user_id",
        cascade="all, delete-orphan",
    )
    owned_transactions: Mapped[list[Transaction]] = relationship(
        "Transaction",
        back_populates="owner",
        foreign_keys="Transaction.owner_id",
        cascade="all, delete-orphan",
    )
    fraud_scores: Mapped[list[FraudScore]] = relationship(
        "FraudScore", back_populates="user", cascade="all, delete-orphan"
    )
    blocked_transactions: Mapped[list[BlockedTransaction]] = relationship(
        "BlockedTransaction",
        back_populates="user",
        foreign_keys="BlockedTransaction.user_id",
        cascade="all, delete-orphan",
    )
    verification_logs: Mapped[list[VerificationLog]] = relationship(
        "VerificationLog", back_populates="user", cascade="all, delete-orphan"
    )
    alerts: Mapped[list[Alert]] = relationship(
        "Alert",
        back_populates="user",
        foreign_keys="Alert.user_id",
        cascade="all, delete-orphan",
    )
    reviewed_blocks: Mapped[list[BlockedTransaction]] = relationship(
        "BlockedTransaction",
        back_populates="reviewer",
        foreign_keys="BlockedTransaction.reviewed_by",
        cascade="all, delete-orphan",
    )
    assigned_alerts: Mapped[list[Alert]] = relationship(
        "Alert",
        back_populates="assignee",
        foreign_keys="Alert.assigned_to",
        cascade="all, delete-orphan",
    )
