"""FraudScore model."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.transaction import Transaction
    from app.models.user import User


class FraudScore(BaseModel):
    """ML fraud score for a transaction."""

    __tablename__ = "fraud_scores"

    transaction_id: Mapped[UUID] = mapped_column(
        ForeignKey("transactions.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    model_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    score: Mapped[Decimal] = mapped_column(nullable=False)
    features_used: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Milliseconds elapsed from ingest start to decision; nullable for old rows.
    decision_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Relationships
    transaction: Mapped[Transaction] = relationship(
        "Transaction", back_populates="fraud_scores"
    )
    user: Mapped[User] = relationship("User", back_populates="fraud_scores")
