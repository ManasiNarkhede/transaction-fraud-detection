"""Request ID middleware for tracing."""

import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware that generates or propagates a request ID for tracing."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Generate or reuse request ID and attach it to request state and response."""
        trace_id = request.headers.get("X-Request-ID")
        if not trace_id:
            trace_id = str(uuid.uuid4())

        request.state.trace_id = trace_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = trace_id
        return response
