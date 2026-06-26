"""FraudDecisionAudit model for tamper-evident audit logging."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.transaction import Transaction


class FraudDecisionAudit(BaseModel):
    """Tamper-evident audit record for fraud detection decisions.

    Each record contains a SHA-256 hash of its contents plus the previous
    record's hash, forming a chain that can be verified for integrity.
    """

    __tablename__ = "fraud_decision_audits"

    transaction_id: Mapped[UUID] = mapped_column(
        ForeignKey("transactions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    decision: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    features: Mapped[dict] = mapped_column(JSONB, nullable=False)
    rules_triggered: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    model_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    hash: Mapped[str] = mapped_column(String(64), nullable=False)
    previous_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Relationship
    transaction: Mapped[Transaction] = relationship(
        "Transaction", back_populates="fraud_decision_audits"
    )
