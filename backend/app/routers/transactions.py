"""Transaction ingestion API endpoint.

Thin router for ``POST /api/v1/transactions``: validates input, delegates the
full scoring flow to ``TransactionIngestService``, and returns the decision.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session, require_analyst
from app.models.user import User
from app.repositories.transaction_repository import TransactionRepository
from app.schemas.transaction import (
    TransactionDecisionResponse,
    TransactionIngestRequest,
    TransactionListResponse,
)
from app.services.transaction_ingest_service import TransactionIngestService

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("", response_model=TransactionListResponse)
async def list_transactions(
    decision: str | None = Query(None, description="Filter by decision status"),
    start_date: date | None = Query(None, description="Filter by start date"),  # noqa: B008
    end_date: date | None = Query(None, description="Filter by end date"),  # noqa: B008
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    user: User = Depends(require_analyst),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """List scored transactions for the authenticated account."""
    repo = TransactionRepository(session)
    items, total = await repo.list_decisions(
        owner_id=user.id,
        decision=decision,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
    )
    return {"total": total, "limit": limit, "offset": offset, "items": items}


@router.post(
    "",
    response_model=TransactionDecisionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def ingest_transaction(
    request: TransactionIngestRequest,
    user: User = Depends(require_analyst),  # noqa: B008
) -> TransactionDecisionResponse:
    """Ingest a live transaction and return its fraud decision.

    Persists the transaction, computes features from user history server-side,
    scores it (ML primary with rule-based fallback), applies the threshold
    decision (approve / verify / block), and triggers alert + audit pipelines.
    """
    service = TransactionIngestService()
    return await service.ingest(request, owner_id=user.id)
