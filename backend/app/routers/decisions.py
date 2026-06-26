"""Decision API endpoints for fraud detection."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session, require_analyst
from app.models.decision import Decision
from app.models.feature_vector import FeatureVector
from app.models.fraud_score import FraudScore
from app.models.user import User
from app.services.audit_service import AuditService
from app.services.decision_engine import DecisionEngine
from app.services.resource_access import get_owned_transaction

router = APIRouter(prefix="/decisions", tags=["decisions"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class DecisionEvaluateRequest(BaseModel):
    """Schema for evaluating a transaction and producing a decision."""

    model_config = ConfigDict(from_attributes=True)

    transaction_id: UUID
    features: FeatureVector
    rule_result: dict[str, Any]


class DecisionEvaluateResponse(Decision):
    """Schema for decision evaluation responses."""

    pass


class DecisionOverrideRequest(BaseModel):
    """Schema for overriding a prior decision."""

    new_decision: str = Field(..., min_length=1, max_length=20)
    reason: str = Field(..., min_length=1, max_length=1000)


class DecisionOverrideResponse(BaseModel):
    """Schema for a decision override response."""

    transaction_id: UUID
    old_decision: str
    new_decision: str
    reason: str
    audit_id: UUID | None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/evaluate", response_model=DecisionEvaluateResponse)
async def evaluate_decision(
    request: DecisionEvaluateRequest,
    user: User = Depends(require_analyst),  # noqa: B008
) -> Decision:
    """Evaluate a transaction and return a fraud detection decision.

    The endpoint calculates a risk score from the provided features and
    rule result, determines whether to approve, verify, or block the
    transaction, and updates the transaction status in the database.
    """
    engine = DecisionEngine()
    decision = await engine.make_decision(
        transaction_id=request.transaction_id,
        features=request.features,
        rule_result=request.rule_result,
    )
    return decision


@router.get("/{transaction_id}", response_model=DecisionEvaluateResponse)
async def get_decision(
    transaction_id: UUID,
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    user: User = Depends(require_analyst),  # noqa: B008
) -> Decision:
    """Get the current decision/status for a transaction by ID.

    Queries the database for the transaction and returns its current
    status as a Decision. Returns 404 if the transaction is not found.
    """
    transaction = await get_owned_transaction(session, transaction_id, user.id)

    if transaction is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found",
        )

    score_row = (
        await session.execute(
            select(FraudScore)
            .where(FraudScore.transaction_id == transaction_id)
            .order_by(FraudScore.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    audit = await AuditService.get_audit_by_transaction(
        transaction_id, owner_id=user.id
    )

    status_value = transaction.status
    if status_value == "blocked":
        status_value = "block"

    return Decision(
        transaction_id=transaction_id,
        score=int(score_row.score)
        if score_row is not None
        else (audit.score if audit else 0),
        decision=status_value,
        reason=audit.reason if audit else "Current transaction status from database",
        rules_triggered=list(audit.rules_triggered)
        if audit and audit.rules_triggered
        else [],
        features_used=(
            score_row.features_used
            if score_row and score_row.features_used
            else (audit.features if audit else {})
        ),
        created_at=(
            audit.created_at
            if audit and audit.created_at
            else (transaction.created_at or datetime.now(UTC))
        ),
    )


@router.post(
    "/{transaction_id}/override",
    response_model=DecisionOverrideResponse,
    status_code=status.HTTP_200_OK,
)
async def override_decision(
    transaction_id: UUID,
    request: DecisionOverrideRequest,
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    user: User = Depends(require_analyst),  # noqa: B008
) -> dict[str, Any]:
    """Override the current decision for a transaction owned by this account.

    Writes a new audit log entry capturing who overrode, old->new decision,
    and reason, preserving the hash-chain integrity (append-only).
    Updates the transaction status to reflect the new decision.

    Args:
        transaction_id: UUID of the transaction to override.
        request: Override payload containing new_decision and reason.
        session: The async database session.
        user: The authenticated admin user.

    Returns:
        Override summary including old/new decisions and audit record ID.

    Raises:
        HTTPException: 404 if the transaction is not found.
    """
    transaction = await get_owned_transaction(session, transaction_id, user.id)

    if transaction is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found",
        )

    old_decision = transaction.status

    # Update transaction status to the new decision
    transaction.status = request.new_decision
    await session.commit()

    # Append override audit record to the hash chain (never mutate prior records)
    audit_record = await AuditService.log_override(
        transaction_id=transaction_id,
        old_decision=old_decision,
        new_decision=request.new_decision,
        reason=request.reason,
        analyst_id=user.id,
    )

    return {
        "transaction_id": transaction_id,
        "old_decision": old_decision,
        "new_decision": request.new_decision,
        "reason": request.reason,
        "audit_id": audit_record.id if audit_record else None,
    }
