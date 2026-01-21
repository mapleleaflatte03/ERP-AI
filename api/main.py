"""
ERPX AI Accounting - FastAPI Main Application
=============================================
Endpoints:
- POST /v1/accounting/coding - Process document for accounting coding
- POST /v1/accounting/reconcile - Reconcile invoices with bank transactions
- GET  /health - Health check
"""

import os
import sys
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.middleware import RateLimitMiddleware, RequestLoggingMiddleware, TenantMiddleware
from api.routes import router
from core.constants import API_PREFIX, API_VERSION
from core.exceptions import ERPXBaseException, QuotaExceeded, TenantNotFound, ValidationError
from core.schemas import (
    HealthResponse,
)


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
        return HealthResponse(
            status="ok",
            version=API_VERSION,
            timestamp=datetime.utcnow().isoformat(),
            components={
                "api": "healthy",
                "database": "mock",  # TODO: Real check
                "vector_db": "mock",  # TODO: Real check
                "storage": "mock",  # TODO: Real check
            },
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
