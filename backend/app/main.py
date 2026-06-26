"""FastAPI application factory with lifespan events."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.core.exceptions import FraudDetectionError
from app.core.logging_config import configure_logging
from app.infrastructure.database import close_db, init_db
from app.infrastructure.redis_client import close_redis, init_redis
from app.middleware import LoggingMiddleware, RequestIDMiddleware
from app.routers import (
    alerts,
    audit,
    auth,
    dashboard,
    decisions,
    health,
    rules,
    transactions,
    verification,
)
from app.workers.alert_worker import AlertWorker
from app.workers.audit_worker import AuditWorker
from app.workers.dashboard_worker import DashboardWorker
from app.workers.runner import start_workers, stop_workers

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application lifespan events."""
    import asyncio

    configure_logging()
    await init_db()
    await init_redis()

    # Initialize stream workers (create consumer groups).
    alert_worker = AlertWorker()
    audit_worker = AuditWorker()
    dashboard_worker = DashboardWorker()
    await alert_worker._create_group()
    await audit_worker._create_group()
    await dashboard_worker._create_group()

    # When workers_in_process=True (set via Azure App Settings), run the
    # consume loops as asyncio background tasks in this process.
    # When False (default), workers run as a separate process via run.py.
    _worker_stop: asyncio.Event | None = None
    _worker_tasks: list[asyncio.Task[None]] = []

    if settings.workers_in_process:
        _worker_stop = asyncio.Event()
        _worker_tasks = start_workers(_worker_stop)

    yield

    if settings.workers_in_process and _worker_stop is not None:
        _worker_stop.set()
        await stop_workers(_worker_tasks)

    await close_db()
    await close_redis()


def _get_trace_id(request: Request) -> str:
    """Extract trace_id from request state."""
    return getattr(request.state, "trace_id", "unknown")


def _error_response(
    code: str, message: str, trace_id: str, details: dict | None = None
) -> JSONResponse:
    """Build a structured JSON error response."""
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": code,
                "message": message,
                "trace_id": trace_id,
                "details": details or {},
            }
        },
    )


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    # Disable API docs in production to avoid exposing the schema publicly.
    is_production = settings.environment == "production"
    app = FastAPI(
        title=settings.project_name,
        version=settings.version,
        debug=settings.debug,
        lifespan=lifespan,
        docs_url=None if is_production else "/docs",
        redoc_url=None if is_production else "/redoc",
        openapi_url=None if is_production else "/openapi.json",
    )

    # Middleware order: RequestID first, then Logging, then CORS
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        """Handle HTTP exceptions including 404 Not Found."""
        trace_id = _get_trace_id(request)
        if exc.status_code == 404:
            return JSONResponse(
                status_code=404,
                content={
                    "error": {
                        "code": "NOT_FOUND",
                        "message": exc.detail or "Resource not found",
                        "trace_id": trace_id,
                        "details": {},
                    }
                },
            )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": f"HTTP_{exc.status_code}",
                    "message": exc.detail or "HTTP error",
                    "trace_id": trace_id,
                    "details": {},
                }
            },
        )

    @app.exception_handler(FraudDetectionError)
    async def fraud_detection_error_handler(
        request: Request, exc: FraudDetectionError
    ) -> JSONResponse:
        """Handle custom FraudDetectionError exceptions."""
        trace_id = _get_trace_id(request)
        status_map = {
            "NOT_FOUND": 404,
            "VALIDATION_ERROR": 422,
            "AUTHENTICATION_ERROR": 401,
            "AUTHORIZATION_ERROR": 403,
        }
        status_code = status_map.get(exc.error_code, 500)
        return JSONResponse(
            status_code=status_code,
            content={
                "error": {
                    "code": exc.error_code,
                    "message": exc.message,
                    "trace_id": trace_id,
                    "details": {},
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Handle 422 Validation Errors."""
        trace_id = _get_trace_id(request)
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Request validation failed",
                    "trace_id": trace_id,
                    "details": {"errors": jsonable_encoder(exc.errors())},
                }
            },
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """Handle unhandled exceptions (500 Internal Server Error)."""
        trace_id = _get_trace_id(request)
        # Always log the full traceback with the trace_id so 500s are diagnosable.
        logger.exception(
            "unhandled_exception",
            extra={
                "trace_id": trace_id,
                "path": request.url.path,
                "exc_type": type(exc).__name__,
            },
        )
        # Surface the exception type/message outside production to aid debugging.
        details: dict = {}
        if settings.environment != "production":
            details = {"type": type(exc).__name__, "message": str(exc)}
        return _error_response(
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
            trace_id=trace_id,
            details=details,
        )

    app.include_router(health.router, prefix=settings.api_v1_prefix)
    app.include_router(auth.router, prefix=settings.api_v1_prefix)
    app.include_router(rules.router, prefix=settings.api_v1_prefix)
    app.include_router(decisions.router, prefix=settings.api_v1_prefix)
    app.include_router(transactions.router, prefix=settings.api_v1_prefix)
    app.include_router(audit.router, prefix=settings.api_v1_prefix)
    app.include_router(verification.router, prefix=settings.api_v1_prefix)
    app.include_router(dashboard.router, prefix=settings.api_v1_prefix)
    app.include_router(alerts.router, prefix=settings.api_v1_prefix)

    return app


app = create_app()
