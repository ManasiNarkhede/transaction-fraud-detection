"""BlockedTransaction model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.transaction import Transaction
    from app.models.user import User


class BlockedTransaction(BaseModel):
    """Record of a transaction that was blocked by fraud rules."""

    __tablename__ = "blocked_transactions"

    transaction_id: Mapped[UUID] = mapped_column(
        ForeignKey("transactions.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    rule_triggered: Mapped[str | None] = mapped_column(String(255), nullable=True)
    blocked_at: Mapped[datetime | None] = mapped_column(nullable=True)
    reviewed_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    review_decision: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Relationships
    transaction: Mapped[Transaction] = relationship(
        "Transaction", back_populates="blocked_transactions"
    )
    user: Mapped[User] = relationship(
        "User", back_populates="blocked_transactions", foreign_keys=[user_id]
    )
    reviewer: Mapped[User | None] = relationship(
        "User", back_populates="reviewed_blocks", foreign_keys=[reviewed_by]
    )
