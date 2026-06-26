"""Alerts API endpoints for fraud alert management."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session, require_analyst
from app.models.user import User
from app.services.alert_service import AlertService

router = APIRouter(prefix="/alerts", tags=["alerts"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class AlertResponse(BaseModel):
    """Schema for a single alert record."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    transaction_id: UUID
    user_id: UUID
    alert_type: str
    severity: str
    status: str
    assigned_to: UUID | None
    resolved_at: datetime | None
    created_at: datetime


class AlertListResponse(BaseModel):
    """Schema for paginated alert list."""

    total: int
    limit: int
    offset: int
    items: list[AlertResponse]


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _alert_to_dict(alert: Any) -> dict[str, Any]:
    """Convert an Alert ORM instance to a response dict."""
    return {
        "id": alert.id,
        "transaction_id": alert.transaction_id,
        "user_id": alert.user_id,
        "alert_type": alert.alert_type,
        "severity": alert.severity,
        "status": alert.status,
        "assigned_to": alert.assigned_to,
        "resolved_at": alert.resolved_at,
        "created_at": alert.created_at,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=AlertListResponse)
async def list_alerts(
    status: str | None = Query(None, description="Filter by status"),
    severity: str | None = Query(None, description="Filter by severity"),
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    user: User = Depends(require_analyst),  # noqa: B008
) -> dict[str, Any]:
    """List alerts, newest first, with optional status/severity filters.

    Args:
        status: Optional status filter (open/investigating/resolved/dismissed).
        severity: Optional severity filter (low/medium/high/critical).
        limit: Maximum number of records to return.
        offset: Number of records to skip.
        session: The async database session.
        user: The authenticated analyst or admin user.

    Returns:
        Paginated list of alert records.
    """
    alerts, total = await AlertService.list_alerts(
        session=session,
        owner_id=user.id,
        status=status,
        severity=severity,
        limit=limit,
        offset=offset,
    )
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [_alert_to_dict(a) for a in alerts],
    }


@router.get("/{alert_id}", response_model=AlertResponse)
async def get_alert(
    alert_id: UUID,
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    user: User = Depends(require_analyst),  # noqa: B008
) -> dict[str, Any]:
    """Get a single alert by ID.

    Args:
        alert_id: The UUID of the alert.
        session: The async database session.
        user: The authenticated analyst or admin user.

    Returns:
        The alert record.

    Raises:
        HTTPException: 404 if the alert is not found.
    """
    alert = await AlertService.get_alert(
        session=session, alert_id=alert_id, owner_id=user.id
    )
    if alert is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found"
        )
    return _alert_to_dict(alert)


@router.post("/{alert_id}/acknowledge", response_model=AlertResponse)
async def acknowledge_alert(
    alert_id: UUID,
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    user: User = Depends(require_analyst),  # noqa: B008
) -> dict[str, Any]:
    """Acknowledge an open alert, transitioning it to 'investigating'.

    Args:
        alert_id: The UUID of the alert.
        session: The async database session.
        user: The authenticated analyst or admin user.

    Returns:
        The updated alert record.

    Raises:
        HTTPException: 404 if the alert is not found.
    """
    alert = await AlertService.acknowledge_alert(
        session=session, alert_id=alert_id, owner_id=user.id
    )
    if alert is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found"
        )
    return _alert_to_dict(alert)


@router.post("/{alert_id}/resolve", response_model=AlertResponse)
async def resolve_alert(
    alert_id: UUID,
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    user: User = Depends(require_analyst),  # noqa: B008
) -> dict[str, Any]:
    """Resolve an alert, setting its status to 'resolved'.

    Args:
        alert_id: The UUID of the alert.
        session: The async database session.
        user: The authenticated analyst or admin user.

    Returns:
        The updated alert record.

    Raises:
        HTTPException: 404 if the alert is not found.
    """
    alert = await AlertService.resolve_alert(
        session=session, alert_id=alert_id, owner_id=user.id
    )
    if alert is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found"
        )
    return _alert_to_dict(alert)
