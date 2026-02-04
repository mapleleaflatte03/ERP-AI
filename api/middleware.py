"""
ERPX AI Accounting - API Middleware
===================================
Middleware for:
- Tenant identification
- Rate limiting
- Request logging
- Authentication (skeleton)
- Idempotency (PR-10)
- Resource monitoring (Quantum Performance)
"""

import os
import sys
import time
import uuid
import json
import hashlib
import psutil
from collections.abc import Callable
from typing import Any

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging

from core.constants import RATE_LIMIT_REQUESTS_PER_MINUTE

logger = logging.getLogger("erpx.api.middleware")


# =============================================================================
# Idempotency Middleware (Quantum Performance)
# =============================================================================


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """
    Global idempotency middleware for all mutation endpoints.
    Prevents duplicate processing of identical requests.
    
    Usage: Client sends X-Idempotency-Key header with unique request ID.
    """

    # Methods that require idempotency
    MUTATION_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
    
    # Paths excluded from idempotency check
    EXCLUDED_PATHS = {
        "/health", "/", "/docs", "/redoc", "/openapi.json",
        "/v1/copilot/chat",  # Chat is inherently non-idempotent
    }
    
    def __init__(self, app: ASGIApp, ttl_seconds: int = 86400):
        super().__init__(app)
        self.cache: dict[str, dict[str, Any]] = {}
        self.ttl_seconds = ttl_seconds

    def _compute_request_hash(self, method: str, path: str, body: bytes) -> str:
        """Compute hash of request for validation."""
        content = f"{method}:{path}:{body.decode('utf-8', errors='ignore')}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _clean_expired(self):
        """Remove expired entries from cache."""
        now = time.time()
        expired_keys = [
            k for k, v in self.cache.items()
            if now - v.get("created_at", 0) > self.ttl_seconds
        ]
        for k in expired_keys:
            del self.cache[k]

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip non-mutation methods
        if request.method not in self.MUTATION_METHODS:
            return await call_next(request)

        # Skip excluded paths
        if request.url.path in self.EXCLUDED_PATHS:
            return await call_next(request)

        # Get idempotency key from header
        idempotency_key = request.headers.get("X-Idempotency-Key")
        
        if not idempotency_key:
            # No key provided - proceed normally but warn
            return await call_next(request)

        # Clean expired entries periodically
        if len(self.cache) > 1000:
            self._clean_expired()

        # Check if request was already processed
        cached = self.cache.get(idempotency_key)
        
        if cached:
            # Validate request hash matches
            body = await request.body()
            request_hash = self._compute_request_hash(
                request.method, request.url.path, body
            )
            
            if cached.get("request_hash") != request_hash:
                return Response(
                    content=json.dumps({
                        "success": False,
                        "error": "Idempotency key reused with different request body",
                        "code": "IDEMPOTENCY_CONFLICT"
                    }),
                    status_code=422,
                    media_type="application/json",
                )

            # Return cached response
            logger.info(f"[Idempotency] Returning cached response for key: {idempotency_key}")
            return Response(
                content=cached["response_body"],
                status_code=cached["response_code"],
                media_type="application/json",
                headers={"X-Idempotency-Replayed": "true"}
            )

        # Mark as processing
        body = await request.body()
        request_hash = self._compute_request_hash(
            request.method, request.url.path, body
        )
        
        self.cache[idempotency_key] = {
            "status": "processing",
            "request_hash": request_hash,
            "created_at": time.time(),
        }

        # Process request
        response = await call_next(request)

        # Cache response for successful requests
        if response.status_code < 500:
            # Read response body
            response_body = b""
            async for chunk in response.body_iterator:
                response_body += chunk

            self.cache[idempotency_key] = {
                "status": "completed",
                "request_hash": request_hash,
                "response_code": response.status_code,
                "response_body": response_body,
                "created_at": time.time(),
            }

            # Return new response with body
            return Response(
                content=response_body,
                status_code=response.status_code,
                media_type=response.media_type,
                headers=dict(response.headers),
            )

        return response


# =============================================================================
# Resource Monitor Middleware (Quantum Performance)
# =============================================================================


class ResourceMonitorMiddleware(BaseHTTPMiddleware):
    """
    Monitor system resources and reject requests when under pressure.
    Prevents OOM and ensures system stability.
    """

    # Memory threshold (reject if available < 15%)
    MEMORY_THRESHOLD_PERCENT = 15
    
    # Disk threshold for /tmp (reject if < 500MB)
    DISK_THRESHOLD_MB = 500
    
    # Heavy endpoints that need resource check
    HEAVY_ENDPOINTS = {
        "/v1/documents/upload",
        "/v1/documents/extract",
        "/v1/batch",
        "/v1/ocr",
    }

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Only check heavy endpoints
        is_heavy = any(request.url.path.startswith(ep) for ep in self.HEAVY_ENDPOINTS)
        
        if is_heavy and request.method == "POST":
            # Check memory
            memory = psutil.virtual_memory()
            available_percent = memory.available * 100 / memory.total
            
            if available_percent < self.MEMORY_THRESHOLD_PERCENT:
                logger.warning(
                    f"[ResourceMonitor] Memory pressure: {available_percent:.1f}% available. "
                    f"Rejecting heavy request to {request.url.path}"
                )
                return Response(
                    content=json.dumps({
                        "success": False,
                        "error": "Server under memory pressure. Please retry later.",
                        "code": "RESOURCE_PRESSURE",
                        "retry_after": 30,
                        "details": {
                            "available_memory_percent": round(available_percent, 1),
                            "threshold": self.MEMORY_THRESHOLD_PERCENT
                        }
                    }),
                    status_code=503,
                    media_type="application/json",
                    headers={"Retry-After": "30"}
                )

            # Check disk space for /tmp
            try:
                disk = psutil.disk_usage("/tmp")
                available_mb = disk.free / (1024 * 1024)
                
                if available_mb < self.DISK_THRESHOLD_MB:
                    logger.warning(
                        f"[ResourceMonitor] Disk pressure: {available_mb:.0f}MB available in /tmp. "
                        f"Triggering cleanup."
                    )
                    # Trigger async cleanup (don't block request)
                    self._cleanup_tmp_files()
                    
                    if available_mb < self.DISK_THRESHOLD_MB / 2:
                        return Response(
                            content=json.dumps({
                                "success": False,
                                "error": "Server under disk pressure. Please retry later.",
                                "code": "DISK_PRESSURE",
                                "retry_after": 60,
                            }),
                            status_code=503,
                            media_type="application/json",
                            headers={"Retry-After": "60"}
                        )
            except Exception as e:
                logger.debug(f"[ResourceMonitor] Could not check disk: {e}")

        return await call_next(request)

    def _cleanup_tmp_files(self):
        """Clean up old temporary OCR files."""
        import glob
        import os
        from datetime import datetime, timedelta

        patterns = ["/tmp/ocr_*", "/tmp/erpx_*", "/tmp/batch_*"]
        cutoff = datetime.now() - timedelta(hours=2)
        cleaned = 0

        for pattern in patterns:
            for filepath in glob.glob(pattern):
                try:
                    mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
                    if mtime < cutoff:
                        if os.path.isfile(filepath):
                            os.remove(filepath)
                        elif os.path.isdir(filepath):
                            import shutil
                            shutil.rmtree(filepath, ignore_errors=True)
                        cleaned += 1
                except Exception:
                    pass

        if cleaned > 0:
            logger.info(f"[ResourceMonitor] Cleaned {cleaned} old temp files")


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
