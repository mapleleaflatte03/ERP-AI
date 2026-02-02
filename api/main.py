"""
ERPX AI Accounting - FastAPI Main Application
=============================================
Endpoints:
- POST /v1/accounting/coding - Process document for accounting coding
- POST /v1/accounting/reconcile - Reconcile invoices with bank transactions
- GET  /health - Health check
"""

import asyncio
import os
import sys
from datetime import datetime

# Build info from environment (set by Docker build or CD)
GIT_SHA = os.getenv("GIT_SHA", "unknown")
BUILD_TIME = os.getenv("BUILD_TIME", "unknown")

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.document_routes import router as document_router
from api.approval_routes import router as approval_router
from api.config_routes import router as config_router
from api.analyst_routes import router as analyst_router
from api.reconciliation_routes import router as reconciliation_router
from api.agent_routes import router as agent_router
from api.analyze_routes import router as analyze_router
from api.middleware import RateLimitMiddleware, RequestLoggingMiddleware, TenantMiddleware
from api.routes import router
from core.config import settings
from core.constants import API_PREFIX, API_VERSION
from core.exceptions import ERPXBaseException, QuotaExceeded, TenantNotFound, ValidationError
from core.schemas import (
    HealthResponse,
)

from pydantic import BaseModel

class VersionResponse(BaseModel):
    """Version info response"""
    git_sha: str
    build_time: str
    api_version: str
    service: str = "ERPX AI Accounting"
from src.db import get_pool
from src.rag import get_qdrant_client
from src.storage import get_minio_client


def create_app() -> FastAPI:
    """Create and configure FastAPI application"""

    app = FastAPI(
        title="ERPX AI Accounting API",
        description="""
        AI-powered Accounting Coding and Bank Reconciliation API.
        
        ## Features
        - Document classification (receipt, VAT invoice, bank slip)
        - Field extraction with evidence tracking
        - Bank transaction reconciliation
        - STRICT/RELAXED processing modes
        - Approval workflow integration
        
        ## Anti-Drift Rules
        - R1: Scope Lock - Only accounting operations
        - R2: No Hallucination - Extract only from source
        - R3: Amount/Date Integrity - Verbatim extraction
        - R4: Doc-Type Truth - Correct type handling
        - R5: Evidence First - All fields have evidence
        - R6: Approval Gate - Human review when needed
        - R7: Fixed Schema - Consistent output format
        """,
        version=API_VERSION,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Custom middleware
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(TenantMiddleware)

    # Include routes
    app.include_router(router, prefix=API_PREFIX)

    # Document routes (UI-facing)
    app.include_router(document_router, prefix=API_PREFIX)
    # Approval routes (UI-facing)
    app.include_router(approval_router, prefix=API_PREFIX)
    # Config and Import routes
    app.include_router(config_router, prefix=API_PREFIX)
    app.include_router(analyst_router, prefix=API_PREFIX)
    app.include_router(reconciliation_router, prefix=API_PREFIX)
    # Agent routes (Copilot action proposals)
    app.include_router(agent_router, prefix=API_PREFIX)
    # Analyze module (unified Reports + Data Analyst + Datasets)
    app.include_router(analyze_router, prefix=API_PREFIX)

    # Exception handlers
    @app.exception_handler(ERPXBaseException)
    async def erpx_exception_handler(request: Request, exc: ERPXBaseException):
        return JSONResponse(
            status_code=400, content={"success": False, "error": exc.message, "code": exc.code, "details": exc.details}
        )

    @app.exception_handler(ValidationError)
    async def validation_exception_handler(request: Request, exc: ValidationError):
        return JSONResponse(
            status_code=422, content={"success": False, "error": exc.message, "code": exc.code, "field": exc.field}
        )

    @app.exception_handler(QuotaExceeded)
    async def quota_exception_handler(request: Request, exc: QuotaExceeded):
        return JSONResponse(
            status_code=429,
            content={"success": False, "error": exc.message, "code": exc.code, "tenant_id": exc.tenant_id},
        )

    @app.exception_handler(TenantNotFound)
    async def tenant_exception_handler(request: Request, exc: TenantNotFound):
        return JSONResponse(
            status_code=404,
            content={"success": False, "error": exc.message, "code": exc.code, "tenant_id": exc.tenant_id},
        )

    # Health endpoint at root level
    @app.get("/health", response_model=HealthResponse, tags=["Health"])
    async def health_check():
        """Health check endpoint"""

        async def check_database() -> dict:
            """Check database connectivity"""
            try:
                pool = await get_pool()
                async with pool.acquire() as conn:
                    # Execute simple query with timeout
                    await asyncio.wait_for(conn.execute("SELECT 1"), timeout=2.0)
                return {"status": "healthy"}
            except asyncio.TimeoutError:
                return {"status": "unhealthy", "error": "Connection timed out"}
            except Exception as e:
                return {"status": "unhealthy", "error": str(e)}

        async def check_vector_db() -> dict:
            """Check vector database connectivity"""
            try:
                client = get_qdrant_client()
                # Use sync client in thread or async method if available
                # QdrantClient has async health_check method
                is_healthy = await asyncio.wait_for(client.health_check(), timeout=2.0)
                if is_healthy:
                    return {"status": "healthy"}
                else:
                    return {"status": "unhealthy", "error": "Health check returned false"}
            except asyncio.TimeoutError:
                return {"status": "unhealthy", "error": "Connection timed out"}
            except Exception as e:
                return {"status": "unhealthy", "error": str(e)}

        def check_storage_sync() -> dict:
            """Synchronous storage check"""
            try:
                client = get_minio_client()
                # Lightweight check: bucket existence
                if client.bucket_exists(settings.MINIO_BUCKET):
                    return {"status": "healthy", "bucket": settings.MINIO_BUCKET}
                else:
                    return {"status": "unhealthy", "error": f"Bucket '{settings.MINIO_BUCKET}' missing"}
            except Exception as e:
                # Shorten error message
                error_msg = str(e).split("\n")[0][:200]
                return {"status": "unhealthy", "error": error_msg}

        # Run checks in parallel
        storage_task = asyncio.to_thread(check_storage_sync)
        db_task = check_database()
        vector_db_task = check_vector_db()

        # Gather results with safety
        results = await asyncio.gather(storage_task, db_task, vector_db_task, return_exceptions=True)

        storage_status = (
            results[0] if not isinstance(results[0], Exception) else {"status": "unhealthy", "error": str(results[0])}
        )
        db_status = (
            results[1] if not isinstance(results[1], Exception) else {"status": "unhealthy", "error": str(results[1])}
        )
        vector_db_status = (
            results[2] if not isinstance(results[2], Exception) else {"status": "unhealthy", "error": str(results[2])}
        )

        overall_status = "ok"
        if (
            storage_status.get("status") != "healthy"
            or db_status.get("status") != "healthy"
            or vector_db_status.get("status") != "healthy"
        ):
            overall_status = "degraded"

        return HealthResponse(
            status=overall_status,
            version=API_VERSION,
            timestamp=datetime.utcnow().isoformat(),
            components={
                "api": "healthy",
                "database": db_status,
                "vector_db": vector_db_status,
                "storage": storage_status,
            },
        )


    # Version endpoint (for deployment verification)
    @app.get("/version", response_model=VersionResponse, tags=["Health"])
    async def get_version():
        """Get build version info for deployment verification"""
        return VersionResponse(
            git_sha=GIT_SHA,
            build_time=BUILD_TIME,
            api_version=API_VERSION,
        )

    # Root endpoint
    @app.get("/", tags=["Root"])
    async def root():
        return {"service": "ERPX AI Accounting", "version": API_VERSION, "docs": "/docs", "health": "/health"}

    return app


# Create app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=os.getenv("API_HOST", "0.0.0.0"),
        port=int(os.getenv("API_PORT", 8000)),
        reload=os.getenv("API_RELOAD", "false").lower() == "true",
    )
