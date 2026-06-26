"""Device model."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.user import User


class Device(BaseModel):
    """Device fingerprint model linked to a user."""

    __tablename__ = "devices"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    device_fingerprint: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False
    )
    device_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    last_seen: Mapped[datetime | None] = mapped_column(nullable=True)
    trust_score: Mapped[Decimal] = mapped_column(
        default=Decimal("0.50"), nullable=False
    )

    # Relationships
    user: Mapped[User] = relationship("User", back_populates="devices")
