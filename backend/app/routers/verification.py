"""Verification API endpoints for transaction verification workflows."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db_session, require_analyst
from app.models.user import User
from app.services.verification_service import VerificationService, _mask_contact

router = APIRouter(prefix="/verify", tags=["verification"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class SendVerificationRequest(BaseModel):
    """Schema for initiating a verification request."""

    transaction_id: UUID
    user_id: UUID
    channel: str = Field(..., min_length=1, max_length=20)
    contact_info: str = Field(..., min_length=1, max_length=255)


class SendVerificationResponse(BaseModel):
    """Schema for the response after initiating verification."""

    verification_id: UUID
    state: str
    expires_at: datetime


class SubmitOtpRequest(BaseModel):
    """Schema for submitting an OTP code."""

    verification_id: UUID
    otp: str = Field(..., min_length=1, max_length=10)


class SubmitOtpResponse(BaseModel):
    """Schema for the response after submitting an OTP."""

    state: str
    message: str
    success: bool = False


class DeliverOtpRequest(BaseModel):
    """Schema for requesting OTP delivery on a pending verification."""

    channel: Literal["email", "sms"]


class DeliverOtpResponse(BaseModel):
    """Schema for OTP delivery response."""

    verification_id: UUID
    channel: str
    contact_info: str | None
    expires_at: str
    delivery_attempted: bool


class VerificationStatusResponse(BaseModel):
    """Schema for verification status response."""

    state: str
    attempts: int
    max_attempts: int
    expires_at: datetime | None


class EscalateResponse(BaseModel):
    """Schema for escalation response."""

    state: str
    message: str


class QueueItemResponse(BaseModel):
    """Schema for a single item in the verification queue."""

    model_config = ConfigDict(from_attributes=True)

    verification_id: UUID
    transaction_id: UUID
    user_id: UUID
    state: str
    channel: str | None
    contact_info: str | None
    attempts: int
    max_attempts: int
    created_at: datetime
    expires_at: datetime | None
    amount: str | None = None
    currency: str | None = None
    transaction_status: str | None = None
    risk_score: int | None = None


class QueueListResponse(BaseModel):
    """Schema for paginated verification queue list."""

    total: int
    limit: int
    offset: int
    items: list[QueueItemResponse]


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _success_response(
    data: dict[str, Any], status_code: int = status.HTTP_200_OK
) -> JSONResponse:
    """Build a structured JSON success response."""
    return JSONResponse(
        status_code=status_code,
        content={"success": True, "data": data},
    )


def _error_response(
    code: str, message: str, status_code: int = status.HTTP_400_BAD_REQUEST
) -> JSONResponse:
    """Build a structured JSON error response."""
    return JSONResponse(
        status_code=status_code,
        content={"success": False, "error": {"code": code, "message": message}},
    )


# ---------------------------------------------------------------------------
# Endpoints — static paths before /{verification_id} routes
# ---------------------------------------------------------------------------


@router.get("/queue")
async def list_verification_queue(
    state: str | None = Query(None, description="Filter by verification state"),
    limit: int = Query(50, ge=1, le=1000, description="Maximum items to return"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    user: User = Depends(require_analyst),  # noqa: B008
) -> JSONResponse:
    """List verifications for this account's medium-risk transactions."""
    service = VerificationService()
    rows = await service.get_queue(
        session=session,
        owner_id=user.id,
        state=state or "PENDING",
        limit=limit,
        offset=offset,
    )

    response_items = []
    for row in rows:
        item = row["verification"]
        response_items.append(
            {
                "verification_id": str(item.id),
                "transaction_id": str(item.transaction_id),
                "user_id": str(item.user_id),
                "state": item.state,
                "channel": item.channel,
                "contact_info": _mask_contact(item.contact_info),
                "attempts": item.attempts,
                "max_attempts": item.max_attempts,
                "created_at": (
                    item.created_at.isoformat() if item.created_at else None
                ),
                "expires_at": (
                    item.otp_expires_at.isoformat() if item.otp_expires_at else None
                ),
                "amount": str(row["amount"]) if row["amount"] is not None else None,
                "currency": row["currency"],
                "transaction_status": row["transaction_status"],
                "risk_score": row["risk_score"],
            }
        )

    return _success_response(
        {
            "total": len(response_items),
            "limit": limit,
            "offset": offset,
            "items": response_items,
        },
        status_code=status.HTTP_200_OK,
    )


@router.post("/send")
async def send_verification(
    request: SendVerificationRequest,
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> JSONResponse:
    """Initiate a verification workflow for a transaction.

    Args:
        request: Verification initiation details.
        session: The async database session.
        user: The currently authenticated user.

    Returns:
        A JSON response containing the verification ID, state, and expiry.

    Raises:
        HTTPException: 400 if the request is invalid.
    """
    try:
        service = VerificationService()
        verification = await service.create_verification(
            session=session,
            transaction_id=request.transaction_id,
            user_id=request.user_id,
            channel=request.channel,
            contact_info=request.contact_info,
        )
    except ValueError as exc:
        return _error_response(
            code="BAD_REQUEST",
            message=str(exc),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return _success_response(
        {
            "verification_id": str(verification.id),
            "state": verification.state,
            "expires_at": (
                verification.otp_expires_at.isoformat()
                if verification.otp_expires_at
                else None
            ),
        },
        status_code=status.HTTP_200_OK,
    )


@router.post("/otp")
async def submit_otp(
    request: SubmitOtpRequest,
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> JSONResponse:
    """Submit an OTP code for verification.

    Args:
        request: OTP submission details.
        session: The async database session.
        user: The currently authenticated user.

    Returns:
        A JSON response containing the verification state and message.

    Raises:
        HTTPException: 404 if the verification is not found.
    """
    try:
        service = VerificationService()
        result = await service.validate_otp(
            session=session,
            verification_id=request.verification_id,
            otp=request.otp,
            owner_id=user.id,
        )
    except ValueError as exc:
        return _error_response(
            code="BAD_REQUEST",
            message=str(exc),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return _success_response(
        {
            "state": result.get("state", "UNKNOWN"),
            "message": result.get("message", ""),
            "success": result.get("success", False),
        },
        status_code=status.HTTP_200_OK,
    )


@router.post("/{verification_id}/deliver-otp")
async def deliver_verification_otp(
    verification_id: UUID,
    request: DeliverOtpRequest,
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> JSONResponse:
    """Send an OTP via email or SMS for a pending medium-risk verification."""
    try:
        service = VerificationService()
        result = await service.deliver_otp(
            session=session,
            verification_id=verification_id,
            owner_id=user.id,
            channel=request.channel,
        )
    except ValueError as exc:
        return _error_response(
            code="BAD_REQUEST",
            message=str(exc),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return _success_response(result, status_code=status.HTTP_200_OK)


@router.get("/{verification_id}/status")
async def get_verification_status(
    verification_id: UUID,
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> JSONResponse:
    """Check the status of a verification request.

    Args:
        verification_id: The unique verification ID.
        session: The async database session.
        user: The currently authenticated user.

    Returns:
        A JSON response containing the verification state, attempts, and expiry.

    Raises:
        HTTPException: 404 if the verification is not found.
    """
    service = VerificationService()
    result = await service.get_status(
        session=session,
        verification_id=verification_id,
        owner_id=user.id,
    )

    if not result.get("found", False):
        return _error_response(
            code="NOT_FOUND",
            message="Verification not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    return _success_response(
        {
            "state": result.get("state", "UNKNOWN"),
            "attempts": result.get("attempts", 0),
            "max_attempts": result.get("max_attempts", 0),
            "channel": result.get("channel"),
            "contact_info": result.get("contact_info"),
            "expires_at": result.get("expires_at"),
        },
        status_code=status.HTTP_200_OK,
    )


@router.post("/{verification_id}/approve")
async def approve_verification(
    verification_id: UUID,
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    user: User = Depends(require_analyst),  # noqa: B008
) -> JSONResponse:
    """Manually approve a pending verification (analyst/admin manual review).

    Marks the verification as VERIFIED and the linked transaction as approved.

    Args:
        verification_id: The unique verification ID.
        session: The async database session.
        user: The authenticated analyst or admin user.

    Returns:
        A JSON response containing the updated state.
    """
    try:
        service = VerificationService()
        verification = await service.approve(
            session=session, verification_id=verification_id, owner_id=user.id
        )
    except ValueError as exc:
        return _error_response(
            code="BAD_REQUEST",
            message=str(exc),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return _success_response(
        {
            "verification_id": str(verification.id),
            "state": verification.state,
            "transaction_id": str(verification.transaction_id),
            "message": "Verification approved",
        },
        status_code=status.HTTP_200_OK,
    )


@router.post("/{verification_id}/reject")
async def reject_verification(
    verification_id: UUID,
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    user: User = Depends(require_analyst),  # noqa: B008
) -> JSONResponse:
    """Manually reject a pending verification (analyst/admin manual review).

    Marks the verification as FAILED and the linked transaction as blocked.

    Args:
        verification_id: The unique verification ID.
        session: The async database session.
        user: The authenticated analyst or admin user.

    Returns:
        A JSON response containing the updated state.
    """
    try:
        service = VerificationService()
        verification = await service.reject(
            session=session, verification_id=verification_id, owner_id=user.id
        )
    except ValueError as exc:
        return _error_response(
            code="BAD_REQUEST",
            message=str(exc),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return _success_response(
        {
            "verification_id": str(verification.id),
            "state": verification.state,
            "transaction_id": str(verification.transaction_id),
            "message": "Verification rejected",
        },
        status_code=status.HTTP_200_OK,
    )


@router.post("/{verification_id}/escalate")
async def escalate_verification(
    verification_id: UUID,
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    user: User = Depends(require_analyst),  # noqa: B008
) -> JSONResponse:
    """Manually escalate a verification request for this account."""
    try:
        service = VerificationService()
        verification = await service.escalate(
            session=session, verification_id=verification_id, owner_id=user.id
        )
    except ValueError as exc:
        return _error_response(
            code="BAD_REQUEST",
            message=str(exc),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if verification is None:
        return _error_response(  # type: ignore[unreachable]
            code="NOT_FOUND",
            message="Verification not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    return _success_response(
        {
            "state": verification.state,
            "message": "Verification escalated successfully",
        },
        status_code=status.HTTP_200_OK,
    )
