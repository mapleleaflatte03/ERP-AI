"""
Request ID Middleware for ERPX API
==================================
Adds request_id to every request for tracing.
"""

import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

# Import from core.logging for centralized request_id management
from core.logging import get_request_id, reset_request_id, set_request_id


class RequestIdMiddleware(BaseHTTPMiddleware):
    """
    Middleware that extracts or generates a request ID for every request.

    Priority:
    1. X-Request-Id header
    2. X-Trace-Id header
    3. Generate new UUID
    """

    async def dispatch(self, request: Request, call_next):
        # Extract from headers or generate new
        request_id = (
            request.headers.get("X-Request-Id")
            or request.headers.get("X-Trace-Id")
            or str(uuid.uuid4())[:8]  # Short UUID for readability
        )

        # Store in request.state for endpoint access
        request.state.request_id = request_id

        # Store in context var for logging - get token for proper reset
        token = set_request_id(request_id)

        try:
            response = await call_next(request)
            # Add request_id to response headers for tracing
            response.headers["X-Request-Id"] = request_id
            return response
        finally:
            # Reset to previous context value using token (async-safe)
            reset_request_id(token)


# Re-export get_request_id for backward compatibility
__all__ = ["RequestIdMiddleware", "get_request_id"]
