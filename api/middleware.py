"""
ERPX AI Accounting - API Middleware
===================================
Middleware for:
- Tenant identification
- Rate limiting
- Request logging
- Authentication (skeleton)
"""

import os
import sys
import time
import uuid
from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging

from core.constants import RATE_LIMIT_REQUESTS_PER_MINUTE

logger = logging.getLogger("erpx.api.middleware")


# =============================================================================
# Tenant Middleware
# =============================================================================


class TenantMiddleware(BaseHTTPMiddleware):
    """
    Extract and validate tenant information from request.
    Sets tenant_id in request.state for downstream use.
    """

    # Mock tenant database
    MOCK_TENANTS = {
        "tenant-001": {"name": "Demo Company", "quota": 10000, "active": True},
        "tenant-002": {"name": "Test Corp", "quota": 5000, "active": True},
        "default": {"name": "Default Tenant", "quota": 1000, "active": True},
    }

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Get tenant ID from header or use default
        tenant_id = request.headers.get("X-Tenant-ID", "default")

        # Validate tenant (mock)
        if tenant_id not in self.MOCK_TENANTS:
            # For now, allow unknown tenants with default settings
            tenant_id = "default"

        # Set in request state
        request.state.tenant_id = tenant_id
        request.state.tenant_info = self.MOCK_TENANTS.get(tenant_id, self.MOCK_TENANTS["default"])

        response = await call_next(request)

        # Add tenant info to response headers
        response.headers["X-Tenant-ID"] = tenant_id

        return response


# =============================================================================
# Rate Limit Middleware
# =============================================================================


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Simple in-memory rate limiting per tenant.
    In production, use Redis or similar.
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.request_counts = {}  # tenant_id -> {minute: count}
        self.limit = RATE_LIMIT_REQUESTS_PER_MINUTE

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip rate limiting for health check
        if request.url.path in ["/health", "/", "/docs", "/redoc", "/openapi.json"]:
            return await call_next(request)

        tenant_id = getattr(request.state, "tenant_id", "default")
        current_minute = int(time.time() / 60)

        # Initialize or reset counter
        if tenant_id not in self.request_counts:
            self.request_counts[tenant_id] = {}

        # Clean old minutes
        self.request_counts[tenant_id] = {
            k: v for k, v in self.request_counts[tenant_id].items() if k >= current_minute - 1
        }

        # Check limit
        current_count = self.request_counts[tenant_id].get(current_minute, 0)

        if current_count >= self.limit:
            # Rate limit exceeded
            return Response(
                content='{"success": false, "error": "Rate limit exceeded", "code": "RATE_LIMIT"}',
                status_code=429,
                media_type="application/json",
            )

        # Increment counter
        self.request_counts[tenant_id][current_minute] = current_count + 1

        response = await call_next(request)

        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(self.limit)
        response.headers["X-RateLimit-Remaining"] = str(self.limit - current_count - 1)

        return response


# =============================================================================
# Request Logging Middleware
# =============================================================================


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Log all requests with timing information.
    Assigns unique request ID for tracing.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate request ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        # Start time
        start_time = time.time()

        # Log request
        logger.info(
            f"[{request_id}] {request.method} {request.url.path} "
            f"tenant={getattr(request.state, 'tenant_id', 'unknown')}"
        )

        # Process request
        response = await call_next(request)

        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000

        # Log response
        logger.info(
            f"[{request_id}] {request.method} {request.url.path} "
            f"status={response.status_code} duration={duration_ms:.2f}ms"
        )

        # Add headers
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Processing-Time-Ms"] = f"{duration_ms:.2f}"

        return response


# =============================================================================
# Authentication Middleware (Skeleton)
# =============================================================================


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Skeleton for authentication middleware.
    In production, integrate with OAuth2/JWT.
    """

    # Paths that don't require authentication
    PUBLIC_PATHS = ["/health", "/", "/docs", "/redoc", "/openapi.json"]

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip auth for public paths
        if request.url.path in self.PUBLIC_PATHS:
            return await call_next(request)

        # Get authorization header
        auth_header = request.headers.get("Authorization")

        if auth_header:
            # Mock token validation
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]
                # In production: validate JWT token
                request.state.user_id = "mock-user"
                request.state.user_role = "accounting_user"
        else:
            # No auth header - allow for development
            request.state.user_id = "anonymous"
            request.state.user_role = "guest"

        return await call_next(request)
