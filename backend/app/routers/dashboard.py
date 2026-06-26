"""Dashboard API endpoints for aggregate fraud metrics."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.dependencies import require_analyst
from app.models.user import User
from app.schemas.dashboard import DashboardMetricsResponse
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/metrics", response_model=DashboardMetricsResponse)
async def get_dashboard_metrics(
    user: User = Depends(require_analyst),  # noqa: B008
) -> DashboardMetricsResponse:
    """Return aggregate fraud dashboard metrics.

    Includes total transactions, blocked transactions, high-risk user count,
    false-positive rate, and a daily fraud trend time series. Restricted to
    analyst/admin roles.
    """
    service = DashboardService()
    return await service.get_metrics(owner_id=user.id)
