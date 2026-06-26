"""Alert model."""

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


class Alert(BaseModel):
    """Fraud alert for analysts."""

    __tablename__ = "alerts"

    transaction_id: Mapped[UUID] = mapped_column(
        ForeignKey("transactions.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    alert_type: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), default="medium", nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="open", nullable=False)
    assigned_to: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Relationships
    transaction: Mapped[Transaction] = relationship(
        "Transaction", back_populates="alerts"
    )
    user: Mapped[User] = relationship(
        "User", back_populates="alerts", foreign_keys=[user_id]
    )
    assignee: Mapped[User | None] = relationship(
        "User", back_populates="assigned_alerts", foreign_keys=[assigned_to]
    )
