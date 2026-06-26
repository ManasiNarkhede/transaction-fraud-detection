"""Decision Pydantic model for fraud detection."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class Decision(BaseModel):
    """Fraud detection decision for a transaction.

    Contains the final score, decision (approve/verify/block),
    human-readable reason, and metadata about rules and features used.
    """

    model_config = ConfigDict(from_attributes=True)

    transaction_id: UUID = Field(..., description="Transaction UUID")
    score: int = Field(..., ge=0, le=100, description="Fraud risk score (0-100)")
    decision: str = Field(..., description="Final decision: approve, verify, or block")
    reason: str = Field(..., description="Human-readable explanation")
    rules_triggered: list[str] = Field(
        default_factory=list, description="Names of triggered fraud rules"
    )
    features_used: dict[str, Any] = Field(
        default_factory=dict, description="Feature values used in scoring"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Timestamp when the decision was created",
    )
