"""Audit API endpoints for fraud decision audit records."""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field

from app.dependencies import require_analyst
from app.models.user import User
from app.services.audit_service import AuditService

router = APIRouter(prefix="/audit", tags=["audit"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class AuditRecordResponse(BaseModel):
    """Schema for a single fraud decision audit record."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    transaction_id: UUID
    decision: str
    score: int = Field(..., ge=0, le=100)
    reason: str
    features: dict[str, Any]
    rules_triggered: list[str]
    model_version: str | None
    hash: str
    previous_hash: str | None
    created_at: date


class AuditListResponse(BaseModel):
    """Schema for paginated audit record list."""

    total: int
    limit: int
    offset: int
    items: list[AuditRecordResponse]


class IntegrityResponse(BaseModel):
    """Schema for integrity verification response."""

    valid: bool
    total_records: int
    first_broken_id: UUID | None
    message: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=AuditListResponse)
async def list_audits(
    decision: str | None = Query(None, description="Filter by decision"),
    start_date: date | None = Query(None, description="Filter by start date"),  # noqa: B008
    end_date: date | None = Query(None, description="Filter by end date"),  # noqa: B008
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    user: User = Depends(require_analyst),  # noqa: B008
) -> dict[str, Any]:
    """Query fraud decision audit records with optional filters.

    Returns a paginated list of audit records ordered by created_at DESC.
    """
    records, total = await AuditService.query_audits(
        owner_id=user.id,
        decision=decision,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
    )

    items = [
        {
            "id": r.id,
            "transaction_id": r.transaction_id,
            "decision": r.decision,
            "score": r.score,
            "reason": r.reason,
            "features": r.features,
            "rules_triggered": r.rules_triggered,
            "model_version": r.model_version,
            "hash": r.hash,
            "previous_hash": r.previous_hash,
            "created_at": r.created_at.date() if r.created_at else None,
        }
        for r in records
    ]

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": items,
    }


@router.get("/integrity", response_model=IntegrityResponse)
async def verify_integrity(
    user: User = Depends(require_analyst),  # noqa: B008
) -> dict[str, Any]:
    """Verify the integrity of the audit hash chain.

    Recomputes hashes for all audit records to detect tampering.
    """
    result = await AuditService.verify_integrity(owner_id=user.id)
    return result


@router.get("/{transaction_id}", response_model=AuditRecordResponse)
async def get_audit_by_transaction(
    transaction_id: UUID,
    user: User = Depends(require_analyst),  # noqa: B008
) -> dict[str, Any]:
    """Get the most recent audit record for a specific transaction.

    Returns 404 if no audit record exists for the transaction.
    """
    record = await AuditService.get_audit_by_transaction(
        transaction_id, owner_id=user.id
    )

    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit record not found for this transaction",
        )

    return {
        "id": record.id,
        "transaction_id": record.transaction_id,
        "decision": record.decision,
        "score": record.score,
        "reason": record.reason,
        "features": record.features,
        "rules_triggered": record.rules_triggered,
        "model_version": record.model_version,
        "hash": record.hash,
        "previous_hash": record.previous_hash,
        "created_at": record.created_at.date() if record.created_at else None,
    }
