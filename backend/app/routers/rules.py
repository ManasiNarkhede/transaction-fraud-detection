"""Fraud rules CRUD API with evaluation endpoint."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session, require_analyst
from app.models import FraudRule
from app.models.user import User
from app.services.resource_access import get_owned_rule
from app.services.rule_engine import RuleEngine

router = APIRouter(prefix="/rules", tags=["rules"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class RuleCreate(BaseModel):
    """Schema for creating a new fraud rule."""

    name: str
    description: str | None = None
    rule_type: str
    conditions: dict
    action: str
    priority: int
    score_value: int | None = None


class RuleUpdate(BaseModel):
    """Schema for updating an existing fraud rule."""

    name: str | None = None
    description: str | None = None
    rule_type: str | None = None
    conditions: dict | None = None
    action: str | None = None
    priority: int | None = None
    score_value: int | None = None


class RuleResponse(BaseModel):
    """Schema for fraud rule responses."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    rule_type: str
    conditions: dict | None
    action: str
    priority: int
    score_value: int
    is_active: bool
    created_at: datetime


class RuleEvaluateRequest(BaseModel):
    """Schema for evaluating a transaction against rules."""

    transaction_data: dict


class RuleEvaluateResponse(BaseModel):
    """Schema for rule evaluation results."""

    score_adjustment: int
    rules_triggered: list[str]
    actions: list[str]
    decision: str


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _rule_to_response(rule: FraudRule) -> dict[str, Any]:
    """Convert a FraudRule ORM instance to a response dict."""
    return {
        "id": rule.id,
        "name": rule.name,
        "description": rule.description,
        "rule_type": rule.rule_type,
        "conditions": rule.conditions,
        "action": rule.action,
        "priority": rule.priority,
        "score_value": rule.score_value,
        "is_active": rule.is_active,
        "created_at": rule.created_at,
    }


async def _invalidate_owner_rules_cache(owner_id: UUID) -> None:
    """Drop cached rules so the next evaluation loads fresh data."""
    engine = RuleEngine()
    await engine.invalidate_rules_cache(owner_id)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=list[RuleResponse])
async def list_rules(
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    user: User = Depends(require_analyst),  # noqa: B008
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    include_inactive: bool = Query(
        False,
        description="When true, return both active and inactive rules. "
        "Default false (active rules only). Does not affect rule-engine evaluation.",
    ),
) -> list[dict[str, Any]]:
    """List fraud rules ordered by priority (paginated).

    By default only active rules are returned. Pass ``?include_inactive=true``
    to include inactive rules as well (e.g. for the Rules admin page).
    The rule-engine always loads active rules only regardless of this parameter.
    """
    stmt = select(FraudRule).where(FraudRule.owner_id == user.id)
    if not include_inactive:
        stmt = stmt.where(FraudRule.is_active.is_(True))
    stmt = stmt.order_by(FraudRule.priority.asc()).offset(skip).limit(limit)
    result = await session.execute(stmt)
    rules = result.scalars().all()
    return [_rule_to_response(rule) for rule in rules]


@router.get("/{rule_id}", response_model=RuleResponse)
async def get_rule(
    rule_id: UUID,
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    user: User = Depends(require_analyst),  # noqa: B008
) -> dict[str, Any]:
    """Get a single fraud rule by ID."""
    rule = await get_owned_rule(session, rule_id, user.id)
    if rule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found"
        )
    return _rule_to_response(rule)


@router.post("", response_model=RuleResponse, status_code=status.HTTP_201_CREATED)
async def create_rule(
    request: RuleCreate,
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    user: User = Depends(require_analyst),  # noqa: B008
) -> dict[str, Any]:
    """Create a new fraud rule for the authenticated account."""
    rule = FraudRule(
        name=request.name,
        description=request.description,
        rule_type=request.rule_type,
        conditions=request.conditions,
        action=request.action,
        priority=request.priority,
        score_value=request.score_value or 0,
        is_active=True,
        owner_id=user.id,
    )
    session.add(rule)
    await session.commit()
    await session.refresh(rule)
    await _invalidate_owner_rules_cache(user.id)
    return _rule_to_response(rule)


@router.put("/{rule_id}", response_model=RuleResponse)
async def update_rule(
    rule_id: UUID,
    request: RuleUpdate,
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    user: User = Depends(require_analyst),  # noqa: B008
) -> dict[str, Any]:
    """Update an existing fraud rule owned by the authenticated account."""
    rule = await get_owned_rule(session, rule_id, user.id)
    if rule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found"
        )

    if request.name is not None:
        rule.name = request.name
    if request.description is not None:
        rule.description = request.description
    if request.rule_type is not None:
        rule.rule_type = request.rule_type
    if request.conditions is not None:
        rule.conditions = request.conditions
    if request.action is not None:
        rule.action = request.action
    if request.priority is not None:
        rule.priority = request.priority
    if request.score_value is not None:
        rule.score_value = request.score_value

    await session.commit()
    await session.refresh(rule)
    await _invalidate_owner_rules_cache(user.id)
    return _rule_to_response(rule)


@router.delete(
    "/{rule_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None
)
async def delete_rule(
    rule_id: UUID,
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    user: User = Depends(require_analyst),  # noqa: B008
) -> None:
    """Soft-delete a fraud rule owned by the authenticated account."""
    rule = await get_owned_rule(session, rule_id, user.id)
    if rule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found"
        )

    rule.is_active = False
    await session.commit()
    await _invalidate_owner_rules_cache(user.id)


@router.post("/{rule_id}/activate", response_model=RuleResponse)
async def activate_rule(
    rule_id: UUID,
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    user: User = Depends(require_analyst),  # noqa: B008
) -> dict[str, Any]:
    """Activate a fraud rule owned by the authenticated account."""
    rule = await get_owned_rule(session, rule_id, user.id)
    if rule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found"
        )

    rule.is_active = True
    await session.commit()
    await session.refresh(rule)
    await _invalidate_owner_rules_cache(user.id)
    return _rule_to_response(rule)


@router.post("/{rule_id}/deactivate", response_model=RuleResponse)
async def deactivate_rule(
    rule_id: UUID,
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    user: User = Depends(require_analyst),  # noqa: B008
) -> dict[str, Any]:
    """Deactivate a fraud rule owned by the authenticated account."""
    rule = await get_owned_rule(session, rule_id, user.id)
    if rule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found"
        )

    rule.is_active = False
    await session.commit()
    await session.refresh(rule)
    await _invalidate_owner_rules_cache(user.id)
    return _rule_to_response(rule)


@router.post("/evaluate", response_model=RuleEvaluateResponse)
async def evaluate_transaction(
    request: RuleEvaluateRequest,
    user: User = Depends(require_analyst),  # noqa: B008
) -> dict[str, Any]:
    """Evaluate a transaction against all active rules without saving."""
    engine = RuleEngine()
    result = await engine.evaluate_transaction(
        request.transaction_data, owner_id=user.id
    )
    return result
