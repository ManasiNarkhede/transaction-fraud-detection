"""Health check endpoint with infrastructure connectivity verification."""

from fastapi import APIRouter, Request
from sqlalchemy import text

from app.config import settings
from app.infrastructure.database import get_session_maker
from app.infrastructure.redis_client import ping as redis_ping
from app.services.onnx_inference import ONNXInferenceService

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check(
    request: Request,
) -> dict:
    """Return health status including database, Redis, and model connectivity."""
    trace_id = getattr(request.state, "trace_id", "unknown")

    db_status = "disconnected"
    try:
        session_maker = get_session_maker()
        if session_maker is not None:
            async with session_maker() as db_session:
                await db_session.execute(text("SELECT 1"))
                db_status = "connected"
    except Exception:
        db_status = "disconnected"

    redis_status = "disconnected"
    try:
        if await redis_ping():
            redis_status = "connected"
    except Exception:
        redis_status = "disconnected"

    # Check ONNX model status
    model_status = "unavailable"
    model_info = {}
    try:
        onnx_service = ONNXInferenceService(model_dir=settings.model_dir)
        model_status = "ready" if onnx_service.is_ready() else "not_loaded"
        model_info = onnx_service.get_model_info()
    except Exception:
        model_status = "error"

    return {
        "status": "healthy",
        "service": "fraud-api",
        "version": settings.version,
        "trace_id": trace_id,
        "checks": {
            "database": db_status,
            "redis": redis_status,
            "models": model_status,
        },
        "model_info": model_info,
    }
