"""API schemas for the live transaction ingestion endpoint.

These are the request/response contracts for ``POST /api/v1/transactions``.
They are deliberately separate from the SQLAlchemy ``Transaction`` ORM model
and from the internal ``Decision`` model.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TransactionIngestRequest(BaseModel):
    """Incoming live transaction payload to be scored.

    Mirrors the problem statement's transaction input data. ``device_id``
    maps to the stored ``device_fingerprint``. ``location`` and
    ``payment_method`` are accepted for rule-engine context and are not
    persisted as dedicated columns.
    """

    model_config = ConfigDict(from_attributes=True)

    user_id: UUID = Field(..., description="ID of the user making the transaction")
    amount: Decimal = Field(
        ..., gt=0, description="Transaction amount", decimal_places=2
    )
    currency: str = Field(default="USD", min_length=3, max_length=3)
    merchant_id: str | None = Field(
        default=None, max_length=255, description="Merchant identifier"
    )
    merchant_category: str | None = Field(default=None, max_length=100)
    location: str | None = Field(
        default=None, max_length=255, description="Geographic location / country"
    )
    device_id: str | None = Field(
        default=None, max_length=255, description="Device fingerprint / id"
    )
    ip_address: str | None = Field(default=None, max_length=45)
    card_last_four: str | None = Field(default=None, max_length=4)
    payment_method: str | None = Field(
        default=None, max_length=50, description="e.g. card, wallet, transfer"
    )
    transaction_time: datetime | None = Field(
        default=None,
        description="Client-supplied transaction timestamp; defaults to now (UTC)",
    )


class TransactionDecisionResponse(BaseModel):
    """Decision returned for an ingested transaction."""

    model_config = ConfigDict(from_attributes=True)

    transaction_id: UUID = Field(..., description="Persisted transaction UUID")
    decision: str = Field(..., description="approve | verify | block")
    score: int = Field(..., ge=0, le=100, description="Fraud risk score (0-100)")
    reason: str = Field(..., description="Human-readable explanation")
    rules_triggered: list[str] = Field(
        default_factory=list, description="Names of triggered fraud rules"
    )
    requires_verification: bool = Field(
        default=False, description="True when decision == verify"
    )


class TransactionSummaryResponse(BaseModel):
    """Single transaction row for list endpoints."""

    model_config = ConfigDict(from_attributes=True)

    transaction_id: UUID
    amount: Decimal
    currency: str
    decision: str = Field(..., description="approve | verify | block")
    score: int = Field(..., ge=0, le=100)
    reason: str
    rules_triggered: list[str] = Field(default_factory=list)
    created_at: datetime


class TransactionListResponse(BaseModel):
    """Paginated list of transaction decisions."""

    total: int
    limit: int
    offset: int
    items: list[TransactionSummaryResponse]
