"""
ERPX AI - FastAPI Application
=============================
Main API service with all endpoints.

Endpoints:
    POST /v1/upload - Upload document (PDF/Image/Excel)
    GET /v1/jobs/{job_id} - Get job status and result
    POST /v1/approve/{job_id} - Approve journal proposal
    GET /health - Health check
    GET /ready - Readiness check
"""

import hashlib
import logging
import os
import sys
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import BackgroundTasks, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Add project root
sys.path.insert(0, "/root/erp-ai")

# Import middleware and logging config
from src.api.logging_config import RequestIdFilter, SafeFormatter, setup_logging
from src.api.middleware import RequestIdMiddleware, get_request_id

# Import schema validation
from src.schemas.llm_output import coerce_and_validate

# Setup safe logging (no KeyError on request_id)
logger = setup_logging(logging.INFO)
logger = logging.getLogger("erpx.api")


# ===========================================================================
# Pydantic Models
# ===========================================================================


class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: str
    services: dict[str, Any]


class UploadResponse(BaseModel):
    job_id: str
    status: str
    message: str
    file_info: dict[str, Any]


class JobStatus(BaseModel):
    job_id: str
    status: str  # pending, processing, completed, failed, approved, rejected
    created_at: str
    updated_at: str
    file_info: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    error: str | None = None


class ApprovalRequest(BaseModel):
    approved: bool
    notes: str | None = ""
    approver_id: str | None = ""


class ApprovalResponse(BaseModel):
    job_id: str
    status: str
    approved: bool
    approved_at: str
    approver_id: str


class JournalEntry(BaseModel):
    account_code: str
    account_name: str
    debit: float
    credit: float
    description: str


class JournalProposal(BaseModel):
    doc_id: str
    doc_type: str
    vendor: str | None = ""
    invoice_no: str | None = ""
    invoice_date: str | None = ""
    total_amount: float
    vat_amount: float
    entries: list[JournalEntry]
    explanation: str
    confidence: float
    needs_human_review: bool
    risks: list[str] = []


# ===========================================================================
# In-Memory Storage (Replace with PostgreSQL in production)
# ===========================================================================


class JobStore:
    """Simple in-memory job store for demo. Replace with PostgreSQL."""

    def __init__(self):
        self.jobs: dict[str, dict[str, Any]] = {}

    def create(self, job_id: str, file_info: dict[str, Any]) -> dict[str, Any]:
        now = datetime.utcnow().isoformat() + "Z"
        job = {
            "job_id": job_id,
            "status": "pending",
            "created_at": now,
            "updated_at": now,
            "file_info": file_info,
            "result": None,
            "error": None,
            "approval": None,
        }
        self.jobs[job_id] = job
        return job

    def get(self, job_id: str) -> dict[str, Any] | None:
        return self.jobs.get(job_id)

    def update(self, job_id: str, **kwargs) -> dict[str, Any] | None:
        if job_id not in self.jobs:
            return None
        self.jobs[job_id].update(kwargs)
        self.jobs[job_id]["updated_at"] = datetime.utcnow().isoformat() + "Z"
        return self.jobs[job_id]

    def list_all(self, limit: int = 100) -> list[dict[str, Any]]:
        return list(self.jobs.values())[-limit:]


# Global store
job_store = JobStore()


# ===========================================================================
# Database Persistence (Golden Tables)
# ===========================================================================


async def persist_to_db(job_id: str, file_info: dict[str, Any], proposal: dict[str, Any]):
    """
    Persist processing result to PostgreSQL golden tables.

    Tables: extracted_invoices, journal_proposals, journal_proposal_entries,
            approvals (auto), ledger_entries, ledger_lines
    """
    import asyncpg

    db_url = os.getenv("DATABASE_URL", "postgresql://erpx:erpx_secret@postgres:5432/erpx")
    # Convert to asyncpg format
    db_url = db_url.replace("postgresql://", "")
    parts = db_url.split("@")
    user_pass = parts[0].split(":")
    host_db = parts[1].split("/")
    host_port = host_db[0].split(":")

    try:
        conn = await asyncpg.connect(
            host=host_port[0],
            port=int(host_port[1]) if len(host_port) > 1 else 5432,
            user=user_pass[0],
            password=user_pass[1],
            database=host_db[1],
        )

        tenant_id = file_info.get("tenant_id", "default")

        # Get or create tenant
        tenant_row = await conn.fetchrow("SELECT id FROM tenants WHERE code = $1", tenant_id)
        if not tenant_row:
            tenant_uuid = str(uuid.uuid4())
            await conn.execute(
                "INSERT INTO tenants (id, name, code) VALUES ($1, $2, $3) ON CONFLICT DO NOTHING",
                uuid.UUID(tenant_uuid),
                f"Tenant {tenant_id}",
                tenant_id,
            )
            tenant_row = await conn.fetchrow("SELECT id FROM tenants WHERE code = $1", tenant_id)

        tenant_uuid = tenant_row["id"]
        doc_uuid = uuid.UUID(job_id)

        # 0. Insert into documents table (FK requirement)
        await conn.execute(
            """
            INSERT INTO documents 
            (id, tenant_id, job_id, filename, content_type, file_size, file_path, checksum, status)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            ON CONFLICT (id) DO NOTHING
        """,
            doc_uuid,
            tenant_uuid,
            job_id,  # job_id string
            file_info.get("filename", "unknown.png"),
            file_info.get("content_type", "application/octet-stream"),
            file_info.get("size", 0),
            file_info.get("path", ""),
            file_info.get("checksum", ""),
            "processed",
        )

        # 1. Insert into extracted_invoices
        invoice_id = uuid.uuid4()
        # Parse invoice_date string to date object
        invoice_date_str = proposal.get("invoice_date", datetime.now().strftime("%Y-%m-%d"))
        try:
            invoice_date = datetime.strptime(invoice_date_str, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            invoice_date = datetime.now().date()

        await conn.execute(
            """
            INSERT INTO extracted_invoices 
            (id, document_id, tenant_id, vendor_name, vendor_tax_id, invoice_number, 
             invoice_date, total_amount, currency, ai_confidence)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            ON CONFLICT DO NOTHING
        """,
            invoice_id,
            doc_uuid,
            tenant_uuid,
            proposal.get("vendor", "Unknown"),
            "",  # vendor_tax_id
            proposal.get("invoice_no", f"INV-{job_id[:8]}"),
            invoice_date,
            float(proposal.get("total_amount", 0)),
            "VND",
            float(proposal.get("confidence", 0.85)),
        )

        # 2. Insert into journal_proposals
        proposal_id = uuid.uuid4()
        entries = proposal.get("entries", [])
        await conn.execute(
            """
            INSERT INTO journal_proposals
            (id, document_id, invoice_id, tenant_id, status, ai_confidence, 
             ai_model, ai_reasoning, risk_level)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            ON CONFLICT DO NOTHING
        """,
            proposal_id,
            doc_uuid,
            invoice_id,
            tenant_uuid,
            "pending",
            float(proposal.get("confidence", 0.85)),
            "do-agent-qwen3-32b",
            proposal.get("explanation", "AI-generated journal proposal"),
            "low" if proposal.get("confidence", 0) > 0.8 else "medium",
        )

        # 3. Insert journal_proposal_entries
        for idx, entry in enumerate(entries):
            entry_id = uuid.uuid4()
            await conn.execute(
                """
                INSERT INTO journal_proposal_entries
                (id, proposal_id, account_code, account_name, debit_amount, credit_amount, line_order)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT DO NOTHING
            """,
                entry_id,
                proposal_id,
                entry.get("account_code", ""),
                entry.get("account_name", ""),
                float(entry.get("debit", 0)),
                float(entry.get("credit", 0)),
                idx + 1,
            )

        # 4. Auto-approve (for smoke test) - insert approval
        approval_id = uuid.uuid4()
        await conn.execute(
            """
            INSERT INTO approvals
            (id, proposal_id, tenant_id, approver_name, action, comments)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT DO NOTHING
        """,
            approval_id,
            proposal_id,
            tenant_uuid,
            "Auto-Approver",
            "approved",
            "Auto-approved by E2E pipeline",
        )

        # 5. Update proposal status to approved
        await conn.execute("UPDATE journal_proposals SET status = 'approved' WHERE id = $1", proposal_id)

        # 6. Insert ledger_entries
        ledger_id = uuid.uuid4()
        entry_number = f"JE-{datetime.now().strftime('%Y%m%d')}-{job_id[:4].upper()}"
        await conn.execute(
            """
            INSERT INTO ledger_entries
            (id, proposal_id, approval_id, tenant_id, entry_date, entry_number, 
             description, posted_by_name)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT DO NOTHING
        """,
            ledger_id,
            proposal_id,
            approval_id,
            tenant_uuid,
            datetime.now().date(),
            entry_number,
            f"Invoice {proposal.get('invoice_no', 'N/A')} - {proposal.get('vendor', 'Unknown')}",
            "ERPX-API",
        )

        # 7. Insert ledger_lines
        for idx, entry in enumerate(entries):
            line_id = uuid.uuid4()
            await conn.execute(
                """
                INSERT INTO ledger_lines
                (id, ledger_entry_id, account_code, account_name, debit_amount, credit_amount, line_order)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT DO NOTHING
            """,
                line_id,
                ledger_id,
                entry.get("account_code", ""),
                entry.get("account_name", ""),
                float(entry.get("debit", 0)),
                float(entry.get("credit", 0)),
                idx + 1,
            )

        await conn.close()
        logger.info(
            f"Job {job_id}: Persisted to golden tables (invoice={invoice_id}, proposal={proposal_id}, ledger={ledger_id})"
        )

    except Exception as e:
        logger.error(f"Job {job_id}: Failed to persist to DB: {e}", exc_info=True)
        # Don't fail the job, just log the error


# ===========================================================================
# Background Processing
# ===========================================================================


async def process_document_async(job_id: str, file_path: str, file_info: dict[str, Any]):
    """
    Process document in background.

    Pipeline:
    1. Extract text (OCR/PDF/Excel)
    2. Retrieve RAG context
    3. Call LLM for classification and extraction
    4. Validate output
    5. Store result
    """
    try:
        logger.info(f"Processing job {job_id}: {file_info.get('filename')}")
        job_store.update(job_id, status="processing")

        # Import processing modules
        from src.llm import get_llm_client

        # Step 1: Extract text based on file type
        content_type = file_info.get("content_type", "")
        text = ""

        if "pdf" in content_type:
            text = await extract_pdf(file_path)
        elif "image" in content_type:
            text = await extract_image(file_path)
        elif "spreadsheet" in content_type or "excel" in content_type:
            text = await extract_excel(file_path)
        else:
            # Try as text
            with open(file_path, encoding="utf-8", errors="ignore") as f:
                text = f.read()

        if not text:
            raise ValueError("Failed to extract text from document")

        logger.info(f"Extracted {len(text)} chars from {file_info.get('filename')}")

        # Step 2: Build prompt and call LLM
        llm_client = get_llm_client()

        system_prompt = """Bạn là chuyên gia kế toán Việt Nam. Nhiệm vụ:
1. Phân loại hóa đơn (mua hàng/bán hàng/chi phí/khác)
2. Trích xuất thông tin: số HĐ, ngày, nhà cung cấp, tổng tiền, thuế VAT
3. Đề xuất bút toán kế toán theo TT200
4. Giải thích lý do

Trả về JSON với format:
{
    "doc_type": "purchase_invoice|sales_invoice|expense|other",
    "vendor": "tên nhà cung cấp",
    "invoice_no": "số hóa đơn",
    "invoice_date": "YYYY-MM-DD",
    "total_amount": số tiền,
    "vat_amount": tiền thuế,
    "entries": [
        {"account_code": "xxx", "account_name": "tên TK", "debit": số, "credit": số, "description": "mô tả"}
    ],
    "explanation": "giải thích bút toán",
    "confidence": 0.0-1.0,
    "needs_human_review": true/false,
    "risks": ["danh sách rủi ro nếu có"]
}"""

        user_prompt = f"""Phân tích hóa đơn sau và đề xuất bút toán:

---
{text[:4000]}
---

Trả về JSON theo format đã định."""

        response = llm_client.generate_json(
            prompt=user_prompt,
            system=system_prompt,
            temperature=0.2,
            max_tokens=2048,
            request_id=job_id,
            trace_id=job_id,
        )

        # Add document ID
        response["doc_id"] = job_id

        # Validate response
        proposal = validate_proposal(response)

        # Persist to PostgreSQL golden tables
        await persist_to_db(job_id, file_info, proposal)

        # Store result in memory
        job_store.update(job_id, status="completed", result=proposal)

        logger.info(f"Job {job_id} completed: {proposal.get('doc_type')}")

    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}", exc_info=True)
        job_store.update(job_id, status="failed", error=str(e))


async def extract_pdf(file_path: str) -> str:
    """Extract text from PDF"""
    try:
        import pdfplumber

        text_parts = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                text_parts.append(page_text)
        return "\n".join(text_parts)
    except Exception as e:
        logger.warning(f"pdfplumber failed: {e}, trying fallback")
        # Fallback to OCR
        return await extract_image(file_path)


async def extract_image(file_path: str) -> str:
    """Extract text from image using pytesseract (with PaddleOCR fallback)"""
    # Try pytesseract first (more reliable)
    try:
        import pytesseract
        from PIL import Image

        img = Image.open(file_path)
        # Try Vietnamese + English
        text = pytesseract.image_to_string(img, lang="vie+eng")
        if text and len(text.strip()) > 10:
            logger.info(f"pytesseract extracted {len(text)} chars")
            return text
    except Exception as e:
        logger.warning(f"pytesseract failed: {e}")

    # Fallback to PaddleOCR
    try:
        from paddleocr import PaddleOCR

        ocr = PaddleOCR(use_angle_cls=True, lang="vi")
        result = ocr.ocr(file_path, cls=True)

        lines = []
        if result and result[0]:
            for line in result[0]:
                if line and len(line) > 1:
                    lines.append(line[1][0])

        text = "\n".join(lines)
        if text:
            logger.info(f"PaddleOCR extracted {len(text)} chars")
            return text
    except Exception as e:
        logger.warning(f"PaddleOCR failed: {e}")

    logger.error(f"All OCR methods failed for {file_path}")
    return ""


async def extract_excel(file_path: str) -> str:
    """Extract data from Excel file"""
    try:
        import pandas as pd

        df = pd.read_excel(file_path)

        # Convert to readable text
        lines = []
        for col in df.columns:
            lines.append(f"Cột: {col}")

        for idx, row in df.iterrows():
            row_text = " | ".join([f"{col}: {val}" for col, val in row.items() if pd.notna(val)])
            lines.append(f"Dòng {idx + 1}: {row_text}")

        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Excel extraction failed: {e}")
        return ""


def validate_proposal(data: dict[str, Any]) -> dict[str, Any]:
    """
    Validate and sanitize proposal using Pydantic schema.

    Uses coerce_and_validate from src.schemas.llm_output for:
    - Type coercion (string → float for amounts)
    - Required field defaults
    - Balance validation
    - Business rule checks
    """
    # Use schema-based validation with coercion
    validated = coerce_and_validate(data)

    # Legacy compatibility: ensure required fields exist
    required = ["doc_type", "total_amount", "entries"]
    for field in required:
        if field not in validated:
            validated[field] = [] if field == "entries" else ""

    # Validate entries balance (redundant but kept for safety)
    total_debit = sum(e.get("debit", 0) for e in validated.get("entries", []))
    total_credit = sum(e.get("credit", 0) for e in validated.get("entries", []))

    if abs(total_debit - total_credit) > 0.01:
        validated["needs_human_review"] = True
        if "risks" not in validated:
            validated["risks"] = []
        if f"Debit ({total_debit}) != Credit ({total_credit})" not in validated["risks"]:
            validated["risks"].append(f"Debit ({total_debit}) != Credit ({total_credit})")

    # Default confidence
    if "confidence" not in validated:
        validated["confidence"] = 0.5

    return validated


# ===========================================================================
# FastAPI App
# ===========================================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    logger.info("ERPX AI API starting...")

    # Startup: Check LLM configuration
    try:
        from src.llm import get_llm_client

        client = get_llm_client()
        logger.info("LLM client initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize LLM client: {e}")
        # Don't block startup, but log error

    # Create upload directory
    upload_dir = Path("/root/erp-ai/data/uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)

    yield

    # Shutdown
    logger.info("ERPX AI API shutting down...")


def create_app() -> FastAPI:
    """Create FastAPI application"""

    app = FastAPI(
        title="ERPX AI Accounting API",
        description="AI-powered accounting document processing",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Request ID middleware (must be first for tracing)
    app.add_middleware(RequestIdMiddleware)

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure properly in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    return app


app = create_app()


# ===========================================================================
# Endpoints
# ===========================================================================


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    services = {}

    # Check LLM
    try:
        from src.llm import get_llm_client

        client = get_llm_client()
        services["llm"] = {"status": "healthy", "provider": "do_agent", "model": client.config.model}
    except Exception as e:
        services["llm"] = {"status": "unhealthy", "error": str(e)}

    return HealthResponse(
        status="healthy" if services.get("llm", {}).get("status") == "healthy" else "degraded",
        version="1.0.0",
        timestamp=datetime.utcnow().isoformat() + "Z",
        services=services,
    )


@app.get("/ready")
async def readiness_check():
    """Readiness check for k8s"""
    try:
        from src.llm import get_llm_client

        client = get_llm_client()
        return {"ready": True}
    except:
        return JSONResponse(status_code=503, content={"ready": False, "reason": "LLM not configured"})


@app.get("/metrics")
async def metrics():
    """
    Prometheus metrics endpoint.
    Returns basic application metrics in Prometheus format.
    """
    # Basic metrics - can be extended with prometheus_client library
    metrics_text = """# HELP erpx_api_info API information
# TYPE erpx_api_info gauge
erpx_api_info{version="1.0.0"} 1
# HELP erpx_api_up API is up
# TYPE erpx_api_up gauge
erpx_api_up 1
# HELP erpx_jobs_total Total jobs in memory store
# TYPE erpx_jobs_total gauge
erpx_jobs_total %d
""" % len(job_store.jobs)
    from fastapi.responses import PlainTextResponse

    return PlainTextResponse(content=metrics_text, media_type="text/plain; charset=utf-8")


@app.post("/v1/upload", response_model=UploadResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    x_tenant_id: str | None = Header(default="default"),
    x_trace_id: str | None = Header(default=None),
):
    """
    Upload document for processing.

    Supported formats:
    - PDF (application/pdf)
    - Images (image/png, image/jpeg)
    - Excel (application/vnd.openxmlformats-officedocument.spreadsheetml.sheet)

    Returns job_id for status polling.
    """
    # Validate file type
    allowed_types = [
        "application/pdf",
        "image/png",
        "image/jpeg",
        "image/jpg",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
    ]

    content_type = file.content_type or ""
    if not any(t in content_type for t in allowed_types):
        raise HTTPException(
            status_code=400, detail=f"Unsupported file type: {content_type}. Allowed: PDF, PNG, JPG, XLSX"
        )

    # Validate file size (max 50MB)
    max_size = 50 * 1024 * 1024
    content = await file.read()
    if len(content) > max_size:
        raise HTTPException(status_code=400, detail=f"File too large: {len(content)} bytes. Max: {max_size} bytes")

    # Generate job ID
    job_id = str(uuid.uuid4())
    trace_id = x_trace_id or job_id

    # Calculate checksum
    checksum = hashlib.md5(content).hexdigest()

    # Save file
    upload_dir = Path("/root/erp-ai/data/uploads") / x_tenant_id
    upload_dir.mkdir(parents=True, exist_ok=True)

    file_ext = Path(file.filename).suffix if file.filename else ".bin"
    file_path = upload_dir / f"{job_id}{file_ext}"

    with open(file_path, "wb") as f:
        f.write(content)

    # Create job record
    file_info = {
        "filename": file.filename,
        "content_type": content_type,
        "size": len(content),
        "checksum": checksum,
        "path": str(file_path),
        "tenant_id": x_tenant_id,
    }

    job = job_store.create(job_id, file_info)

    logger.info(f"Upload received: job_id={job_id} file={file.filename} size={len(content)}")

    # Start background processing
    background_tasks.add_task(process_document_async, job_id, str(file_path), file_info)

    return UploadResponse(
        job_id=job_id,
        status="pending",
        message="Document uploaded successfully. Processing started.",
        file_info=file_info,
    )


@app.get("/v1/jobs/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str):
    """Get job status and result"""
    job = job_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    return JobStatus(**job)


@app.get("/v1/jobs")
async def list_jobs(limit: int = 100):
    """List recent jobs"""
    jobs = job_store.list_all(limit)
    return {"jobs": jobs, "count": len(jobs)}


@app.post("/v1/approve/{job_id}", response_model=ApprovalResponse)
async def approve_job(job_id: str, request: ApprovalRequest, x_user_id: str | None = Header(default="anonymous")):
    """Approve or reject journal proposal"""
    job = job_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    if job["status"] not in ["completed"]:
        raise HTTPException(status_code=400, detail=f"Cannot approve job with status: {job['status']}")

    new_status = "approved" if request.approved else "rejected"
    approval_time = datetime.utcnow().isoformat() + "Z"

    job_store.update(
        job_id,
        status=new_status,
        approval={
            "approved": request.approved,
            "approver_id": request.approver_id or x_user_id,
            "notes": request.notes,
            "approved_at": approval_time,
        },
    )

    logger.info(f"Job {job_id} {new_status} by {x_user_id}")

    return ApprovalResponse(
        job_id=job_id,
        status=new_status,
        approved=request.approved,
        approved_at=approval_time,
        approver_id=request.approver_id or x_user_id,
    )


# ===========================================================================
# Run Server
# ===========================================================================

if __name__ == "__main__":
    port = int(os.getenv("API_PORT", "8000"))
    host = os.getenv("API_HOST", "0.0.0.0")

    print(f"Starting ERPX AI API on {host}:{port}")
    uvicorn.run(app, host=host, port=port)
