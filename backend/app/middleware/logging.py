"""Request logging middleware with structured JSON output."""

import logging
import time
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("fraud-api")


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware that logs all requests with method, path, status, and duration."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Log request details including trace_id."""
        start_time = time.time()
        trace_id = getattr(request.state, "trace_id", "unknown")

        response = await call_next(request)

        duration_ms = (time.time() - start_time) * 1000

        extra = {
            "trace_id": trace_id,
            "event": "http_request",
            "extra": {
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round(duration_ms, 2),
            },
        }

        logger.info(
            "%s %s - %s - %.2fms",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            extra=extra,
        )

        return response
