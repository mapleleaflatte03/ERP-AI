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

# Import approval inbox module
from src.approval.service import (
    approve_proposal,
    get_approval_by_id,
    list_pending_approvals,
    reject_proposal,
)

# Import audit module
from src.audit.store import (
    append_audit_event,
    create_audit_evidence,
    get_audit_evidence,
    get_audit_timeline,
    update_audit_decision,
)

# Import data zones and idempotency
from src.datazones import (
    DataZone,
    JobState,
    check_document_duplicate,
    compute_checksum,
    create_job_state,
    get_idempotency_key,
    get_job_state,
    get_job_zones,
    register_document_checksum,
    track_zone_entry,
    update_job_state,
)

# Import observability
from src.observability import (
    check_alerts,
    get_evaluation_run,
    get_metric_stats,
    list_active_alerts,
    list_evaluation_runs,
    list_metric_names,
    record_counter,
)

# Import outbox
from src.outbox import (
    get_outbox_stats,
    get_pending_events,
)

# Import policy engine
from src.policy.engine import (
    evaluate_proposal as policy_evaluate_proposal,
)
from src.policy.engine import (
    get_active_rules,
    get_policy_evaluation,
)

# Import schema validation
from src.schemas.llm_output import coerce_and_validate

# Import Temporal workflow starter (PR16)
from src.workflows.temporal_client import start_document_workflow

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


# PR-8: Approval Inbox Models
class ApprovalActionRequest(BaseModel):
    approver: str
    comment: str | None = None


class ApprovalItem(BaseModel):
    id: str
    proposal_id: str | None = None
    job_id: str | None = None
    tenant_id: str | None = None
    status: str | None = None
    approver_name: str | None = None
    comment: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    ai_confidence: float | None = None
    ai_model: str | None = None
    risk_level: str | None = None
    vendor_name: str | None = None
    invoice_number: str | None = None
    total_amount: float | None = None
    currency: str | None = None


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

        # 4. Auto-approve (for smoke test) - insert approval with job_id
        approval_id = uuid.uuid4()
        await conn.execute(
            """
            INSERT INTO approvals
            (id, proposal_id, tenant_id, job_id, approver_name, action, status, comments)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT DO NOTHING
        """,
            approval_id,
            proposal_id,
            tenant_uuid,
            doc_uuid,
            "Auto-Approver",
            "approved",
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
# Background Processing (PR13 Integration)
# ===========================================================================


async def process_document_async(job_id: str, file_path: str, file_info: dict[str, Any]):
    """
    Process document in background with full PR7-12 integration.

    Pipeline:
    1. Initialize state tracking (PR10)
    2. Record audit evidence start (PR7)
    3. Extract text (OCR/PDF/Excel) + track zone (PR10) + metrics (PR12)
    4. Call LLM for classification + audit (PR7) + metrics (PR12)
    5. Validate output + policy evaluation (PR9)
    6. Persist to DB + track zone (PR10)
    7. Emit outbox events (PR11)
    8. Complete audit trail (PR7)
    """
    import time

    from src.api.middleware import get_request_id
    from src.observability import record_latency
    from src.outbox import AggregateType, EventType, publish_event
    from src.policy.engine import evaluate_proposal as policy_evaluate

    request_id = get_request_id() or job_id
    tenant_id = file_info.get("tenant_id", "default")
    pipeline_start = time.time()
    conn = None
    tenant_uuid = None  # Initialize for exception handler

    try:
        logger.info(f"[{request_id}] Processing job {job_id}: {file_info.get('filename')}")
        job_store.update(job_id, status="processing")

        # Get DB connection for all tracking
        conn = await get_db_connection()

        # =========== STEP 0: Create Document + Initialize State ===========
        # First, ensure tenant exists
        tenant_row = await conn.fetchrow("SELECT id FROM tenants WHERE code = $1", tenant_id)
        if not tenant_row:
            tenant_uuid_str = str(uuid.uuid4())
            await conn.execute(
                "INSERT INTO tenants (id, name, code) VALUES ($1, $2, $3) ON CONFLICT DO NOTHING",
                uuid.UUID(tenant_uuid_str),
                f"Tenant {tenant_id}",
                tenant_id,
            )
            tenant_row = await conn.fetchrow("SELECT id FROM tenants WHERE code = $1", tenant_id)

        tenant_uuid = tenant_row["id"]
        doc_uuid = uuid.UUID(job_id)

        # Create document record first (required for FK in data_zones)
        await conn.execute(
            """
            INSERT INTO documents 
            (id, tenant_id, job_id, filename, content_type, file_size, file_path, checksum, status)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            ON CONFLICT (id) DO NOTHING
            """,
            doc_uuid,
            tenant_uuid,
            job_id,
            file_info.get("filename", "unknown.bin"),
            file_info.get("content_type", "application/octet-stream"),
            file_info.get("size", 0),
            file_info.get("path", ""),
            file_info.get("checksum", ""),
            "processing",
        )

        # =========== PR14: MinIO Durable Storage ===========
        from src.core import config as core_config
        
        minio_bucket = None
        minio_key = None
        
        if core_config.ENABLE_MINIO:
            try:
                from src.storage import upload_document as minio_upload
                
                # Read file content
                with open(file_path, "rb") as f:
                    file_data = f.read()
                
                minio_bucket, minio_key, minio_checksum, minio_size = minio_upload(
                    file_data=file_data,
                    filename=file_info.get("filename", "unknown.bin"),
                    content_type=file_info.get("content_type", "application/octet-stream"),
                    company_id=tenant_id,
                    job_id=job_id,
                )
                
                # Update document record with MinIO location
                await conn.execute(
                    """
                    UPDATE documents 
                    SET minio_bucket = $1, minio_key = $2, checksum = $3
                    WHERE id = $4
                    """,
                    minio_bucket,
                    minio_key,
                    minio_checksum,
                    doc_uuid,
                )
                
                logger.info(f"[{request_id}] MinIO upload: s3://{minio_bucket}/{minio_key}")
            except Exception as minio_err:
                logger.warning(f"[{request_id}] MinIO upload failed (non-fatal): {minio_err}")
        else:
            logger.info(f"[{request_id}] MinIO disabled (ENABLE_MINIO=0)")

        # Now initialize state and audit
        await create_job_state(conn, job_id, JobState.UPLOADED, str(tenant_uuid), request_id)
        await append_audit_event(
            conn,
            job_id=job_id,
            tenant_id=str(tenant_uuid),
            event_type="received",
            event_data={
                "filename": file_info.get("filename"),
                "content_type": file_info.get("content_type"),
                "size": file_info.get("size"),
                "checksum": file_info.get("checksum"),
            },
            actor="system",
            request_id=request_id,
        )

        # Track RAW zone
        await track_zone_entry(
            conn,
            job_id=job_id,
            zone=DataZone.RAW,
            tenant_id=str(tenant_uuid),
            document_id=job_id,
            raw_file_uri=file_info.get("path"),
            checksum=file_info.get("checksum"),
            byte_count=file_info.get("size"),
            request_id=request_id,
        )

        # Record upload metric
        await record_counter(conn, "uploads_total", 1.0, {"tenant": tenant_id})

        # =========== STEP 1: Extract Text ===========
        await update_job_state(conn, job_id, JobState.EXTRACTING, request_id=request_id)

        from src.llm import get_llm_client

        content_type = file_info.get("content_type", "")
        text = ""
        ocr_start = time.time()

        if "pdf" in content_type:
            text = await extract_pdf(file_path)
        elif "image" in content_type:
            text = await extract_image(file_path)
        elif "spreadsheet" in content_type or "excel" in content_type:
            text = await extract_excel(file_path)
        else:
            with open(file_path, encoding="utf-8", errors="ignore") as f:
                text = f.read()

        ocr_latency_ms = int((time.time() - ocr_start) * 1000)

        if not text:
            raise ValueError("Failed to extract text from document")

        logger.info(f"[{request_id}] Extracted {len(text)} chars in {ocr_latency_ms}ms")

        # Record OCR metrics (ms-based histogram buckets)
        await record_counter(conn, "ocr_calls_total", 1.0, {"tenant": tenant_id})
        await record_latency(conn, "ocr_latency", float(ocr_latency_ms), labels={"tenant": tenant_id})

        # Update state and track EXTRACTED zone
        await update_job_state(
            conn,
            job_id,
            JobState.EXTRACTED,
            checkpoint_data={"text_length": len(text)},
            request_id=request_id,
        )
        await track_zone_entry(
            conn,
            job_id=job_id,
            zone=DataZone.EXTRACTED,
            tenant_id=str(tenant_uuid),
            document_id=job_id,
            extracted_text_preview=text[:4000],
            byte_count=len(text.encode("utf-8")),
            processing_time_ms=ocr_latency_ms,
            request_id=request_id,
        )
        await append_audit_event(
            conn,
            job_id=job_id,
            tenant_id=str(tenant_uuid),
            event_type="extracted",
            event_data={"text_length": len(text), "ocr_latency_ms": ocr_latency_ms},
            actor="system",
            request_id=request_id,
        )

        # =========== PR14: Qdrant Embedding Storage ===========
        qdrant_points_upserted = 0
        
        if core_config.ENABLE_QDRANT:
            try:
                from src.rag import generate_embedding, get_qdrant_client
                
                # Generate embedding for extracted text (truncate to 4k chars)
                text_for_embedding = text[:4000] if len(text) > 4000 else text
                embedding = generate_embedding(text_for_embedding)
                
                if embedding:
                    qdrant_client = get_qdrant_client()
                    
                    # Upsert to documents_ingested collection
                    qdrant_points_upserted = qdrant_client.upsert_documents(
                        texts=[text_for_embedding],
                        metadatas=[{
                            "job_id": job_id,
                            "tenant_id": str(tenant_uuid),
                            "filename": file_info.get("filename", "unknown"),
                            "doc_type": "invoice",
                            "source": "upload",
                        }],
                        collection_name="documents_ingested",
                    )
                    
                    logger.info(f"[{request_id}] Qdrant upsert: {qdrant_points_upserted} points to documents_ingested")
                else:
                    logger.warning(f"[{request_id}] Qdrant: embedding generation returned None")
            except Exception as qdrant_err:
                logger.warning(f"[{request_id}] Qdrant upsert failed (non-fatal): {qdrant_err}")
        else:
            logger.info(f"[{request_id}] Qdrant disabled (ENABLE_QDRANT=0)")

        # =========== STEP 2: Call LLM ===========
        await update_job_state(conn, job_id, JobState.PROPOSING, request_id=request_id)

        llm_client = get_llm_client()
        model_name = llm_client.config.model

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

        llm_start = time.time()
        response = llm_client.generate_json(
            prompt=user_prompt,
            system=system_prompt,
            temperature=0.2,
            max_tokens=2048,
            request_id=request_id,
            trace_id=job_id,
        )
        llm_latency_ms = int((time.time() - llm_start) * 1000)

        # Record LLM metrics (ms-based histogram buckets)
        await record_counter(conn, "llm_calls_total", 1.0, {"tenant": tenant_id, "model": model_name})
        await record_latency(conn, "llm_latency", float(llm_latency_ms), labels={"tenant": tenant_id})

        response["doc_id"] = job_id
        proposal = validate_proposal(response)

        logger.info(f"[{request_id}] LLM response in {llm_latency_ms}ms, confidence={proposal.get('confidence')}")

        await update_job_state(conn, job_id, JobState.PROPOSED, request_id=request_id)

        await append_audit_event(
            conn,
            job_id=job_id,
            tenant_id=str(tenant_uuid),
            event_type="llm_proposed",
            event_data={
                "model": model_name,
                "llm_latency_ms": llm_latency_ms,
                "confidence": proposal.get("confidence"),
                "doc_type": proposal.get("doc_type"),
            },
            actor="llm",
            request_id=request_id,
        )

        # =========== STEP 3: Policy Evaluation ===========
        policy_result = await policy_evaluate(
            conn,
            proposal=proposal,
            job_id=job_id,
            tenant_id=str(tenant_uuid),
            request_id=request_id,
        )

        await append_audit_event(
            conn,
            job_id=job_id,
            tenant_id=str(tenant_uuid),
            event_type="policy_evaluated",
            event_data={
                "overall_result": policy_result.overall_result.value,
                "auto_approved": policy_result.auto_approved,
                "rules_passed": policy_result.rules_passed,
                "rules_failed": policy_result.rules_failed,
            },
            actor="policy_engine",
            request_id=request_id,
        )

        # Create audit evidence with full details
        await create_audit_evidence(
            conn,
            job_id=job_id,
            tenant_id=str(tenant_uuid),
            request_id=request_id,
            document_id=job_id,
            raw_file_uri=file_info.get("path"),
            extracted_text=text,
            prompt_version="v1",
            model_name=model_name,
            llm_stage="direct",
            llm_input=user_prompt,
            llm_output_json=proposal,
            llm_output_raw=str(response),
            llm_latency_ms=llm_latency_ms,
            validation_errors=proposal.get("risks", []),
            risk_flags=proposal.get("risks", []),
            decision="proposed",
        )

        # Track PROPOSED zone (silver)
        await track_zone_entry(
            conn,
            job_id=job_id,
            zone=DataZone.PROPOSED,
            tenant_id=str(tenant_uuid),
            document_id=job_id,
            processing_time_ms=llm_latency_ms,
            request_id=request_id,
        )

        # =========== STEP 4: GOVERNANCE GATING (PR13.3) ===========
        # Branch based on policy result - MUST check BEFORE posting ledger
        needs_approval = policy_result.overall_result.value == "requires_review" or not policy_result.auto_approved

        if needs_approval:
            # =========== BRANCH A: NEEDS APPROVAL ===========
            # MUST NOT post ledger, MUST NOT emit outbox, MUST stop workflow
            logger.info(f"[{request_id}] Job {job_id} requires approval - NOT posting ledger")

            # 1. Insert approval PENDING with job_id (NOT NULL)
            approval_id = uuid.uuid4()
            await conn.execute(
                """
                INSERT INTO approvals
                (id, proposal_id, tenant_id, job_id, approver_name, action, status, comments)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT DO NOTHING
                """,
                approval_id,
                None,  # proposal_id - will link later when approved
                tenant_uuid,
                doc_uuid,  # job_id = canonical_job_id (NOT NULL)
                "System",
                "pending",
                "pending",
                f"Pending approval (policy: {policy_result.overall_result.value})",
            )

            # 2. Audit events
            await append_audit_event(
                conn,
                job_id,
                str(tenant_uuid),
                "needs_approval",
                {
                    "reason": f"Policy result: {policy_result.overall_result.value}",
                    "rules_failed": policy_result.rules_failed,
                    "auto_approved": policy_result.auto_approved,
                },
                "policy_engine",
                request_id,
            )
            await update_audit_decision(
                conn, job_id, "waiting_approval", policy_result.overall_result.value, request_id
            )

            # 3. State machine - WAITING_FOR_APPROVAL
            await update_job_state(conn, job_id, JobState.WAITING_FOR_APPROVAL, request_id=request_id)

            # 4. Metrics
            await record_counter(conn, "approvals_pending_total", 1.0, {"tenant": str(tenant_uuid)})

            # 5. Update job store and STOP
            e2e_latency_ms = int((time.time() - pipeline_start) * 1000)
            await record_latency(conn, "end_to_end_latency", float(e2e_latency_ms), labels={"tenant": str(tenant_uuid)})

            job_store.update(job_id, status="waiting_for_approval", result=proposal)
            logger.info(f"[{request_id}] Job {job_id} stopped at WAITING_FOR_APPROVAL in {e2e_latency_ms}ms")

            # STOP WORKFLOW - do NOT continue to ledger/outbox
            return

        # =========== BRANCH B: AUTO APPROVED ===========
        # Continue to post ledger and emit outbox
        logger.info(f"[{request_id}] Job {job_id} auto-approved - posting ledger")

        # 1. Audit auto_approved
        await append_audit_event(
            conn,
            job_id,
            str(tenant_uuid),
            "auto_approved",
            {"reason": "Policy rules passed", "rules_passed": policy_result.rules_passed},
            "policy_engine",
            request_id,
        )
        await record_counter(conn, "auto_approved_total", 1.0, {"tenant": str(tenant_uuid)})
        await update_audit_decision(conn, job_id, "auto_approved", "Policy rules passed", request_id)

        # =========== STEP 5: Persist to Golden Tables (only if auto-approved) ===========
        await update_job_state(conn, job_id, JobState.POSTING, request_id=request_id)

        # Call existing persist function with our connection
        persist_result = await persist_to_db_with_conn(conn, job_id, file_info, proposal, str(tenant_uuid), request_id)

        # Track POSTED zone (gold)
        await track_zone_entry(
            conn,
            job_id=job_id,
            zone=DataZone.POSTED,
            tenant_id=str(tenant_uuid),
            document_id=job_id,
            proposal_id=persist_result.get("proposal_id"),
            ledger_entry_id=persist_result.get("ledger_id"),
            request_id=request_id,
        )

        # =========== STEP 6: Emit Outbox Event (only if auto-approved) ===========
        await publish_event(
            conn,
            event_type=EventType.LEDGER_POSTED,
            aggregate_type=AggregateType.LEDGER,
            aggregate_id=persist_result.get("ledger_id", job_id),
            payload={
                "job_id": job_id,
                "proposal_id": persist_result.get("proposal_id"),
                "ledger_entry_id": persist_result.get("ledger_id"),
                "invoice_no": proposal.get("invoice_no"),
                "vendor": proposal.get("vendor"),
                "total_amount": proposal.get("total_amount"),
                "currency": "VND",
            },
            tenant_id=str(tenant_uuid),
            request_id=request_id,
        )

        await record_counter(conn, "ledger_posted_total", 1.0, {"tenant": str(tenant_uuid)})
        await append_audit_event(
            conn,
            job_id,
            str(tenant_uuid),
            "posted_to_ledger",
            {
                "ledger_id": persist_result.get("ledger_id"),
                "entry_number": persist_result.get("entry_number"),
            },
            "system",
            request_id,
        )

        # =========== STEP 7: Complete ===========
        await update_job_state(conn, job_id, JobState.COMPLETED, request_id=request_id)

        e2e_latency_ms = int((time.time() - pipeline_start) * 1000)
        await record_latency(conn, "end_to_end_latency", float(e2e_latency_ms), labels={"tenant": str(tenant_uuid)})

        await append_audit_event(
            conn,
            job_id,
            str(tenant_uuid),
            "completed",
            {"e2e_latency_ms": e2e_latency_ms, "doc_type": proposal.get("doc_type")},
            "system",
            request_id,
        )

        job_store.update(job_id, status="completed", result=proposal)
        logger.info(f"[{request_id}] Job {job_id} completed in {e2e_latency_ms}ms: {proposal.get('doc_type')}")

    except Exception as e:
        logger.error(f"[{request_id}] Job {job_id} failed: {e}", exc_info=True)
        job_store.update(job_id, status="failed", error=str(e))

        # Try to record failure in audit
        if conn:
            try:
                # Use tenant_uuid if available, fallback to tenant_id string
                t_id = str(tenant_uuid) if tenant_uuid else tenant_id
                await update_job_state(conn, job_id, JobState.FAILED, error=str(e), request_id=request_id)
                await append_audit_event(
                    conn,
                    job_id,
                    t_id,
                    "failed",
                    {"error": str(e)[:1000]},
                    "system",
                    request_id,
                )
                await update_audit_decision(conn, job_id, "failed", str(e)[:500], request_id)
            except Exception as audit_err:
                logger.error(f"[{request_id}] Failed to record audit: {audit_err}")

    finally:
        if conn:
            await conn.close()


async def persist_proposal_only(
    conn,
    job_id: str,
    file_info: dict[str, Any],
    proposal: dict[str, Any],
    tenant_id_str: str,
    request_id: str | None = None,
) -> dict[str, str]:
    """
    PR17: Persist just the extracted_invoice and journal_proposal (not ledger).
    This is called for BOTH auto-approved AND needs-approval paths,
    so the finalize activity can access proposal data later.
    
    Returns dict with proposal_id and invoice_id.
    """
    request_id = request_id or get_request_id()
    tenant_uuid = uuid.UUID(tenant_id_str)
    doc_uuid = uuid.UUID(job_id)
    
    # Check if already persisted (idempotent)
    existing = await conn.fetchrow(
        """SELECT jp.id as proposal_id, ei.id as invoice_id
           FROM journal_proposals jp 
           JOIN extracted_invoices ei ON jp.invoice_id = ei.id
           JOIN documents d ON ei.document_id = d.id
           WHERE d.job_id = $1""",
        job_id,
    )
    if existing:
        logger.info(f"[{request_id}] Proposal already persisted for job {job_id}")
        return {"proposal_id": str(existing["proposal_id"]), "invoice_id": str(existing["invoice_id"])}
    
    # 0. Ensure documents table entry exists
    await conn.execute(
        """
        INSERT INTO documents 
        (id, tenant_id, job_id, filename, content_type, file_size, file_path, checksum, status)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        ON CONFLICT (id) DO UPDATE SET status = 'processed'
        """,
        doc_uuid,
        tenant_uuid,
        job_id,
        file_info.get("filename", "unknown.png"),
        file_info.get("content_type", "application/octet-stream"),
        file_info.get("size", 0),
        file_info.get("path", ""),
        file_info.get("checksum", ""),
        "processed",
    )
    
    # 1. Insert into extracted_invoices
    invoice_id = uuid.uuid4()
    invoice_date_str = proposal.get("invoice_date", datetime.now().strftime("%Y-%m-%d"))
    try:
        invoice_date = datetime.strptime(invoice_date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        invoice_date = datetime.now().date()
    
    await conn.execute(
        """
        INSERT INTO extracted_invoices 
        (id, document_id, tenant_id, vendor_name, vendor_tax_id, invoice_number, 
         invoice_date, total_amount, currency, ai_confidence, tax_amount, subtotal)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
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
        float(proposal.get("vat_amount", 0)),
        float(proposal.get("total_amount", 0)) - float(proposal.get("vat_amount", 0)),
    )
    
    # 2. Insert into journal_proposals (status='pending' until approved)
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
        "pending",  # Not approved yet
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
    
    logger.info(f"[{request_id}] Persisted proposal {proposal_id} for job {job_id}")
    return {"proposal_id": str(proposal_id), "invoice_id": str(invoice_id)}


async def persist_to_db_with_conn(
    conn,
    job_id: str,
    file_info: dict[str, Any],
    proposal: dict[str, Any],
    tenant_id_str: str,
    request_id: str | None = None,
) -> dict[str, str]:
    """
    Persist processing result to PostgreSQL golden tables using existing connection.
    Returns dict with created IDs.
    """
    # Get or create tenant
    tenant_row = await conn.fetchrow("SELECT id FROM tenants WHERE code = $1", tenant_id_str)
    if not tenant_row:
        tenant_uuid = str(uuid.uuid4())
        await conn.execute(
            "INSERT INTO tenants (id, name, code) VALUES ($1, $2, $3) ON CONFLICT DO NOTHING",
            uuid.UUID(tenant_uuid),
            f"Tenant {tenant_id_str}",
            tenant_id_str,
        )
        tenant_row = await conn.fetchrow("SELECT id FROM tenants WHERE code = $1", tenant_id_str)

    tenant_uuid = tenant_row["id"]
    doc_uuid = uuid.UUID(job_id)

    # 0. Insert into documents table (FK requirement)
    await conn.execute(
        """
        INSERT INTO documents 
        (id, tenant_id, job_id, filename, content_type, file_size, file_path, checksum, status)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        ON CONFLICT (id) DO UPDATE SET status = 'processed', updated_at = NOW()
        """,
        doc_uuid,
        tenant_uuid,
        job_id,
        file_info.get("filename", "unknown.png"),
        file_info.get("content_type", "application/octet-stream"),
        file_info.get("size", 0),
        file_info.get("path", ""),
        file_info.get("checksum", ""),
        "processed",
    )

    # 1. Insert into extracted_invoices
    invoice_id = uuid.uuid4()
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
        "",
        proposal.get("invoice_no", f"INV-{job_id[:8]}"),
        invoice_date,
        float(proposal.get("total_amount", 0)),
        "VND",
        float(proposal.get("confidence", 0.85)),
    )

    # 2. Insert into journal_proposals
    proposal_id = uuid.uuid4()
    entries = proposal.get("entries", [])
    confidence = float(proposal.get("confidence", 0.85))
    risk_level = "low" if confidence > 0.8 else "medium"

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
        confidence,
        "do-agent-qwen3-32b",
        proposal.get("explanation", "AI-generated journal proposal"),
        risk_level,
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

    # 4. Insert approval with job_id
    approval_id = uuid.uuid4()
    await conn.execute(
        """
        INSERT INTO approvals
        (id, proposal_id, tenant_id, job_id, approver_name, action, status, comments)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        ON CONFLICT DO NOTHING
        """,
        approval_id,
        proposal_id,
        tenant_uuid,
        doc_uuid,
        "Auto-Approver",
        "approved",
        "approved",
        "Auto-approved by E2E pipeline",
    )

    # 5. Update proposal status to approved
    await conn.execute("UPDATE journal_proposals SET status = 'approved' WHERE id = $1", proposal_id)

    # 6. Insert ledger_entries (PR19: idempotent with DB constraint)
    # First check if ledger already exists for this proposal (idempotency check)
    existing_ledger = await conn.fetchrow(
        "SELECT id, entry_number FROM ledger_entries WHERE proposal_id = $1",
        proposal_id,
    )
    
    if existing_ledger:
        # PR19: Ledger already posted, return existing entry (idempotent)
        logger.info(f"[{request_id}] [PR19] Job {job_id}: Ledger already exists for proposal (idempotent)")
        return {
            "invoice_id": str(invoice_id),
            "proposal_id": str(proposal_id),
            "approval_id": str(approval_id),
            "ledger_id": str(existing_ledger["id"]),
            "entry_number": existing_ledger["entry_number"],
            "idempotent": True,
        }
    
    ledger_id = uuid.uuid4()
    entry_number = f"JE-{datetime.now().strftime('%Y%m%d')}-{job_id[:4].upper()}"
    
    try:
        await conn.execute(
            """
            INSERT INTO ledger_entries
            (id, proposal_id, approval_id, tenant_id, entry_date, entry_number,
             description, posted_by_name)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
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
    except Exception as e:
        # PR19: Handle unique constraint violation (race condition)
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            logger.info(f"[{request_id}] [PR19] Job {job_id}: Ledger constraint violation (idempotent)")
            existing = await conn.fetchrow(
                "SELECT id, entry_number FROM ledger_entries WHERE proposal_id = $1",
                proposal_id,
            )
            if existing:
                return {
                    "invoice_id": str(invoice_id),
                    "proposal_id": str(proposal_id),
                    "approval_id": str(approval_id),
                    "ledger_id": str(existing["id"]),
                    "entry_number": existing["entry_number"],
                    "idempotent": True,
                }
        raise

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

    logger.info(
        f"[{request_id}] Job {job_id}: Persisted (invoice={invoice_id}, proposal={proposal_id}, ledger={ledger_id})"
    )

    return {
        "invoice_id": str(invoice_id),
        "proposal_id": str(proposal_id),
        "approval_id": str(approval_id),
        "ledger_id": str(ledger_id),
        "entry_number": entry_number,
    }


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


def setup_otel_instrumentation(app: FastAPI):
    """
    Setup OpenTelemetry instrumentation for FastAPI (PR15).
    Fail-open: log warning if OTEL unavailable, don't crash.
    """
    from src.core import config as core_config
    
    if not core_config.ENABLE_OTEL:
        logger.info("OTEL disabled (ENABLE_OTEL=0)")
        return
    
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        
        # Configure resource with service name
        resource = Resource.create({
            "service.name": core_config.OTEL_SERVICE_NAME,
            "service.version": "1.0.0",
        })
        
        # Create tracer provider
        tracer_provider = TracerProvider(resource=resource)
        
        # Configure OTLP exporter
        otlp_exporter = OTLPSpanExporter(
            endpoint=core_config.OTEL_ENDPOINT,
            insecure=True,  # Use insecure for internal docker network
        )
        
        # Add batch processor for efficiency
        tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
        
        # Set global tracer provider
        trace.set_tracer_provider(tracer_provider)
        
        # Instrument FastAPI
        FastAPIInstrumentor.instrument_app(app)
        
        # Instrument httpx for outbound calls (LLM, etc.)
        HTTPXClientInstrumentor().instrument()
        
        logger.info(f"OTEL enabled: service={core_config.OTEL_SERVICE_NAME}, endpoint={core_config.OTEL_ENDPOINT}")
        
    except ImportError as e:
        logger.warning(f"OTEL packages not available (non-fatal): {e}")
    except Exception as e:
        logger.warning(f"OTEL initialization failed (non-fatal): {e}")


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

    # PR15: Setup OTEL instrumentation (before middlewares)
    setup_otel_instrumentation(app)

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

    # PR16: Start Temporal workflow if ENABLE_TEMPORAL=1, else fallback to background task
    from src.core import config as core_config
    
    use_temporal = getattr(core_config, 'ENABLE_TEMPORAL', False)
    workflow_started = False
    
    if use_temporal:
        try:
            # PR16: Upload to MinIO and create document record BEFORE starting workflow
            from src.storage import upload_document
            import asyncpg
            
            # 1. Upload to MinIO
            minio_bucket, minio_key, file_checksum, file_size = upload_document(
                content, file.filename, content_type, x_tenant_id, job_id
            )
            logger.info(f"MinIO upload: s3://{minio_bucket}/{minio_key}")
            
            # 2. Insert document record with MinIO info
            db_url = os.getenv("DATABASE_URL", "postgresql://erpx:erpx_secret@postgres:5432/erpx")
            conn = await asyncpg.connect(db_url)
            
            # Ensure tenant exists
            tenant_row = await conn.fetchrow("SELECT id FROM tenants WHERE code = $1", x_tenant_id)
            if not tenant_row:
                tenant_uuid = uuid.uuid4()
                await conn.execute(
                    "INSERT INTO tenants (id, name, code) VALUES ($1, $2, $3) ON CONFLICT (code) DO NOTHING",
                    tenant_uuid, f"Tenant {x_tenant_id}", x_tenant_id,
                )
                tenant_row = await conn.fetchrow("SELECT id FROM tenants WHERE code = $1", x_tenant_id)
            
            tenant_uuid = tenant_row["id"]
            doc_uuid = uuid.UUID(job_id)
            
            await conn.execute(
                """
                INSERT INTO documents 
                (id, tenant_id, job_id, filename, content_type, file_size, file_path, checksum, 
                 minio_bucket, minio_key, status)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                ON CONFLICT (id) DO NOTHING
                """,
                doc_uuid, tenant_uuid, job_id, file.filename, content_type, len(content),
                str(file_path), checksum, minio_bucket, minio_key, "pending",
            )
            await conn.close()
            logger.info(f"Document record created: {job_id}")
            
            # 3. Start Temporal workflow (async)
            workflow_id = await start_document_workflow(job_id)
            workflow_started = True
            logger.info(f"Temporal workflow started: workflow_id={workflow_id} job_id={job_id}")
        except Exception as e:
            logger.warning(f"Temporal workflow start failed, falling back to async: {e}")
            workflow_started = False
    
    if not workflow_started:
        # Fallback: Start background processing (original behavior)
        background_tasks.add_task(process_document_async, job_id, str(file_path), file_info)

    return UploadResponse(
        job_id=job_id,
        status="queued" if workflow_started else "pending",
        message="Document uploaded successfully. Processing started.",
        file_info=file_info,
    )


# ===========================================================================
# PR18: DB-backed Job Status Helper
# ===========================================================================

async def get_job_status_from_db(job_id: str) -> dict | None:
    """
    Get job status from database (Source of Truth).
    
    PR18: This makes /v1/jobs/{job_id} work even after API restart.
    
    Returns dict compatible with JobStatus model, or None if not found.
    """
    try:
        conn = await get_db_connection()
        try:
            # 1. Get job processing state (primary source)
            state_row = await conn.fetchrow(
                """
                SELECT current_state, created_at, updated_at, state_changed_at
                FROM job_processing_state 
                WHERE job_id = $1
                """,
                job_id,
            )
            
            # 2. Get document info
            doc_row = await conn.fetchrow(
                """
                SELECT filename, content_type, file_size, file_path, checksum,
                       minio_bucket, minio_key, created_at, updated_at
                FROM documents 
                WHERE job_id = $1
                """,
                job_id,
            )
            
            # If neither exists, job not found
            if not state_row and not doc_row:
                return None
            
            # Map DB state to API status
            status = "unknown"
            if state_row:
                state_map = {
                    "uploaded": "queued",
                    "extracting": "processing",
                    "extracted": "processing",
                    "proposing": "processing",
                    "proposed": "processing",
                    "approving": "processing",
                    "waiting_for_approval": "waiting_for_approval",
                    "posting": "processing",
                    "completed": "completed",
                    "failed": "failed",
                }
                status = state_map.get(state_row["current_state"], state_row["current_state"])
            
            # Build file_info from documents table
            file_info = None
            if doc_row:
                file_info = {
                    "filename": doc_row["filename"],
                    "content_type": doc_row["content_type"],
                    "size": doc_row["file_size"],
                    "path": doc_row["file_path"],
                    "checksum": doc_row["checksum"],
                }
                if doc_row["minio_bucket"] and doc_row["minio_key"]:
                    file_info["minio_path"] = f"s3://{doc_row['minio_bucket']}/{doc_row['minio_key']}"
            
            # Determine timestamps
            created_at = (state_row["created_at"] if state_row else doc_row["created_at"]) if (state_row or doc_row) else datetime.now()
            updated_at = (state_row["updated_at"] if state_row else doc_row["updated_at"]) if (state_row or doc_row) else datetime.now()
            
            # 3. Get result info for completed jobs
            result = None
            error = None
            if status == "completed":
                # Try to get ledger entry info
                ledger_row = await conn.fetchrow(
                    """
                    SELECT le.id, le.entry_number, le.description, le.posted_at
                    FROM ledger_entries le
                    JOIN journal_proposals jp ON le.proposal_id = jp.id
                    JOIN extracted_invoices ei ON jp.invoice_id = ei.id
                    JOIN documents d ON ei.document_id = d.id
                    WHERE d.job_id = $1
                    ORDER BY le.created_at DESC LIMIT 1
                    """,
                    job_id,
                )
                if ledger_row:
                    result = {
                        "ledger_entry_id": str(ledger_row["id"]),
                        "entry_number": ledger_row["entry_number"],
                        "description": ledger_row["description"],
                        "posted_at": ledger_row["posted_at"].isoformat() if ledger_row["posted_at"] else None,
                    }
            elif status == "failed":
                # Get error from job_processing_state
                if state_row:
                    error_row = await conn.fetchrow(
                        "SELECT last_error FROM job_processing_state WHERE job_id = $1",
                        job_id,
                    )
                    if error_row and error_row["last_error"]:
                        error = error_row["last_error"]
            
            return {
                "job_id": job_id,
                "status": status,
                "created_at": created_at.isoformat() if hasattr(created_at, 'isoformat') else str(created_at),
                "updated_at": updated_at.isoformat() if hasattr(updated_at, 'isoformat') else str(updated_at),
                "file_info": file_info,
                "result": result,
                "error": error,
            }
        finally:
            await conn.close()
    except Exception as e:
        logger.warning(f"Failed to get job status from DB for {job_id}: {e}")
        return None


@app.get("/v1/jobs/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str):
    """
    Get job status and result.
    
    PR18: DB-backed - survives API restart.
    Priority: DB (source of truth) > job_store (cache)
    """
    # PR18: Always try DB first (source of truth)
    db_status = await get_job_status_from_db(job_id)
    
    if db_status:
        # DB found - return it (DB wins over stale cache)
        logger.debug(f"[PR18] Job {job_id} status from DB: {db_status['status']}")
        return JobStatus(**db_status)
    
    # Fallback to job_store cache (for jobs not yet in DB)
    job = job_store.get(job_id)
    if job:
        logger.debug(f"[PR18] Job {job_id} status from cache: {job.get('status')}")
        return JobStatus(**job)
    
    # Not found anywhere
    raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")


@app.get("/v1/jobs")
async def list_jobs(limit: int = 100):
    """List recent jobs"""
    jobs = job_store.list_all(limit)
    return {"jobs": jobs, "count": len(jobs)}


# ===========================================================================
# PR-7: Audit & Evidence Endpoints
# ===========================================================================


async def get_db_connection():
    """Get async database connection."""
    import asyncpg

    db_url = os.getenv("DATABASE_URL", "postgresql://erpx:erpx_secret@localhost:5432/erpx")
    db_url = db_url.replace("postgresql://", "")
    parts = db_url.split("@")
    user_pass = parts[0].split(":")
    host_db = parts[1].split("/")
    host_port = host_db[0].split(":")

    return await asyncpg.connect(
        host=host_port[0],
        port=int(host_port[1]) if len(host_port) > 1 else 5432,
        user=user_pass[0],
        password=user_pass[1],
        database=host_db[1],
    )


@app.get("/v1/jobs/{job_id}/evidence")
async def get_job_evidence(job_id: str):
    """
    Get audit evidence for a job.

    Returns complete audit trail including:
    - Raw file reference
    - Extracted text preview
    - LLM inputs/outputs
    - Validation results
    - Decision chain
    """
    try:
        conn = await get_db_connection()
        try:
            evidence = await get_audit_evidence(conn, job_id)
            if not evidence:
                raise HTTPException(status_code=404, detail=f"No evidence found for job: {job_id}")
            return evidence
        finally:
            await conn.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get evidence for job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/jobs/{job_id}/timeline")
async def get_job_timeline(job_id: str):
    """
    Get audit timeline for a job.

    Returns chronological list of events:
    - upload
    - ocr_complete
    - llm_complete
    - validate
    - approve/reject
    - post
    """
    try:
        conn = await get_db_connection()
        try:
            timeline = await get_audit_timeline(conn, job_id)
            return {"job_id": job_id, "events": timeline, "count": len(timeline)}
        finally:
            await conn.close()
    except Exception as e:
        logger.error(f"Failed to get timeline for job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===========================================================================
# PR-8: Approval Inbox Endpoints
# ===========================================================================


@app.get("/v1/approvals")
async def list_approvals(
    status: str = "pending",
    tenant_id: str | None = None,
    limit: int = 50,
):
    """
    List approvals filtered by status.

    Query params:
    - status: pending|approved|rejected (default: pending)
    - tenant_id: filter by tenant (optional)
    - limit: max results (default: 50)

    Returns list of approvals with proposal context.
    """
    try:
        conn = await get_db_connection()
        try:
            approvals = await list_pending_approvals(
                conn,
                tenant_id=tenant_id,
                status=status,
                limit=limit,
            )
            return {
                "approvals": approvals,
                "count": len(approvals),
                "status_filter": status,
            }
        finally:
            await conn.close()
    except Exception as e:
        logger.error(f"Failed to list approvals: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/approvals/{approval_id}")
async def get_approval(approval_id: str):
    """Get single approval by ID with full context."""
    try:
        conn = await get_db_connection()
        try:
            approval = await get_approval_by_id(conn, approval_id)
            if not approval:
                raise HTTPException(status_code=404, detail=f"Approval not found: {approval_id}")
            return approval
        finally:
            await conn.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get approval {approval_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/approvals/{approval_id}/approve")
async def approve_approval(
    approval_id: str,
    request: ApprovalActionRequest,
    x_request_id: str | None = Header(default=None),
):
    """
    Approve a pending proposal.

    This will:
    1. Update approval status to 'approved'
    2. Update proposal status to 'approved'
    3. Trigger ledger posting (create ledger entry + lines)

    Body:
    - approver: approver name/ID (required)
    - comment: approval comment (optional)
    """
    request_id = x_request_id or get_request_id()
    try:
        conn = await get_db_connection()
        try:
            result = await approve_proposal(
                conn,
                approval_id=approval_id,
                approver=request.approver,
                comment=request.comment,
                request_id=request_id,
            )
            return result
        finally:
            await conn.close()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[{request_id}] Failed to approve {approval_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/approvals/{approval_id}/reject")
async def reject_approval(
    approval_id: str,
    request: ApprovalActionRequest,
    x_request_id: str | None = Header(default=None),
):
    """
    Reject a pending proposal.

    This will:
    1. Update approval status to 'rejected'
    2. Update proposal status to 'rejected'
    3. No ledger posting

    Body:
    - approver: rejector name/ID (required)
    - comment: rejection reason (optional)
    """
    request_id = x_request_id or get_request_id()
    try:
        conn = await get_db_connection()
        try:
            result = await reject_proposal(
                conn,
                approval_id=approval_id,
                approver=request.approver,
                comment=request.comment,
                request_id=request_id,
            )
            return result
        finally:
            await conn.close()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[{request_id}] Failed to reject {approval_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===========================================================================
# PR-17: Human-in-the-Loop Approval Endpoints (by job_id)
# ===========================================================================


class ApprovalByJobResponse(BaseModel):
    job_id: str
    approval_status: str
    temporal_signaled: bool
    message: str


@app.get("/v1/approvals/pending")
async def list_pending_approvals_pr17(
    tenant_id: str | None = None,
    limit: int = 50,
):
    """
    List pending approvals (PR17).
    
    Query params:
    - tenant_id: filter by tenant (optional)
    - limit: max results (default: 50)
    
    Returns list of pending approvals with job_id.
    """
    try:
        conn = await get_db_connection()
        try:
            query = """
                SELECT 
                    a.id as approval_id,
                    a.job_id,
                    a.tenant_id,
                    a.status,
                    a.created_at,
                    a.updated_at,
                    ei.vendor_name,
                    ei.invoice_number,
                    ei.total_amount,
                    ei.currency
                FROM approvals a
                LEFT JOIN journal_proposals jp ON a.proposal_id = jp.id
                LEFT JOIN extracted_invoices ei ON jp.invoice_id = ei.id
                WHERE a.status = 'pending'
            """
            params = []
            
            if tenant_id:
                query += " AND a.tenant_id = $1"
                params.append(uuid.UUID(tenant_id) if len(tenant_id) > 10 else tenant_id)
            
            query += f" ORDER BY a.created_at DESC LIMIT ${len(params) + 1}"
            params.append(limit)
            
            rows = await conn.fetch(query, *params)
            
            return {
                "approvals": [
                    {
                        "approval_id": str(row["approval_id"]),
                        "job_id": str(row["job_id"]) if row["job_id"] else None,
                        "tenant_id": str(row["tenant_id"]) if row["tenant_id"] else None,
                        "status": row["status"],
                        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                        "vendor_name": row["vendor_name"],
                        "invoice_number": row["invoice_number"],
                        "total_amount": float(row["total_amount"]) if row["total_amount"] else None,
                        "currency": row["currency"],
                    }
                    for row in rows
                ],
                "count": len(rows),
            }
        finally:
            await conn.close()
    except Exception as e:
        logger.error(f"Failed to list pending approvals: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/approvals/by-job/{job_id}/approve", response_model=ApprovalByJobResponse)
async def approve_by_job_id(
    job_id: str,
    x_request_id: str | None = Header(default=None),
):
    """
    Approve a pending job and signal Temporal workflow (PR17).
    
    This will:
    1. Update approval status to 'approved' in DB
    2. Signal Temporal workflow to continue posting
    
    Idempotent: repeated calls won't double-post ledger.
    """
    request_id = x_request_id or get_request_id()
    
    try:
        conn = await get_db_connection()
        try:
            # Find approval by job_id
            approval_row = await conn.fetchrow(
                """
                SELECT id, status FROM approvals 
                WHERE job_id = $1::uuid
                ORDER BY created_at DESC LIMIT 1
                """,
                uuid.UUID(job_id),
            )
            
            if not approval_row:
                raise HTTPException(status_code=404, detail=f"No approval found for job_id: {job_id}")
            
            approval_id = approval_row["id"]
            current_status = approval_row["status"]
            
            # Check if already approved (idempotent)
            if current_status == "approved":
                logger.info(f"[{request_id}] Job {job_id} already approved, returning OK")
                return ApprovalByJobResponse(
                    job_id=job_id,
                    approval_status="approved",
                    temporal_signaled=False,
                    message="Already approved (idempotent)",
                )
            
            if current_status not in ["pending", None]:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot approve: current status is {current_status}",
                )
            
            # Update approval status
            await conn.execute(
                """
                UPDATE approvals
                SET status = 'approved', 
                    action = 'approved',
                    approver_name = 'api_user', 
                    approved_at = NOW(),
                    updated_at = NOW()
                WHERE id = $1
                """,
                approval_id,
            )
            
            logger.info(f"[{request_id}] Approval {approval_id} for job {job_id} approved")
            
        finally:
            await conn.close()
        
        # Signal Temporal workflow
        from src.workflows.temporal_client import signal_workflow_approval
        
        signal_result = await signal_workflow_approval(job_id, "approve")
        
        return ApprovalByJobResponse(
            job_id=job_id,
            approval_status="approved",
            temporal_signaled=signal_result.get("signaled", False),
            message=signal_result.get("message", "Approval processed"),
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[{request_id}] Failed to approve job {job_id}: {e}")
        # Return 202 with temporal_signaled=false on failure (fail-open)
        return ApprovalByJobResponse(
            job_id=job_id,
            approval_status="approved",
            temporal_signaled=False,
            message=f"Approval saved but signal failed: {str(e)}",
        )


@app.post("/v1/approvals/by-job/{job_id}/reject", response_model=ApprovalByJobResponse)
async def reject_by_job_id(
    job_id: str,
    x_request_id: str | None = Header(default=None),
):
    """
    Reject a pending job and signal Temporal workflow (PR17).
    
    This will:
    1. Update approval status to 'rejected' in DB
    2. Signal Temporal workflow to finalize rejection
    
    Idempotent: repeated calls won't fail.
    """
    request_id = x_request_id or get_request_id()
    
    try:
        conn = await get_db_connection()
        try:
            # Find approval by job_id
            approval_row = await conn.fetchrow(
                """
                SELECT id, status FROM approvals 
                WHERE job_id = $1::uuid
                ORDER BY created_at DESC LIMIT 1
                """,
                uuid.UUID(job_id),
            )
            
            if not approval_row:
                raise HTTPException(status_code=404, detail=f"No approval found for job_id: {job_id}")
            
            approval_id = approval_row["id"]
            current_status = approval_row["status"]
            
            # Check if already rejected (idempotent)
            if current_status == "rejected":
                logger.info(f"[{request_id}] Job {job_id} already rejected, returning OK")
                return ApprovalByJobResponse(
                    job_id=job_id,
                    approval_status="rejected",
                    temporal_signaled=False,
                    message="Already rejected (idempotent)",
                )
            
            if current_status not in ["pending", None]:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot reject: current status is {current_status}",
                )
            
            # Update approval status
            await conn.execute(
                """
                UPDATE approvals
                SET status = 'rejected', 
                    action = 'rejected',
                    approver_name = 'api_user', 
                    approved_at = NOW(),
                    updated_at = NOW()
                WHERE id = $1
                """,
                approval_id,
            )
            
            logger.info(f"[{request_id}] Approval {approval_id} for job {job_id} rejected")
            
        finally:
            await conn.close()
        
        # Signal Temporal workflow
        from src.workflows.temporal_client import signal_workflow_approval
        
        signal_result = await signal_workflow_approval(job_id, "reject")
        
        return ApprovalByJobResponse(
            job_id=job_id,
            approval_status="rejected",
            temporal_signaled=signal_result.get("signaled", False),
            message=signal_result.get("message", "Rejection processed"),
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[{request_id}] Failed to reject job {job_id}: {e}")
        # Return 202 with temporal_signaled=false on failure (fail-open)
        return ApprovalByJobResponse(
            job_id=job_id,
            approval_status="rejected",
            temporal_signaled=False,
            message=f"Rejection saved but signal failed: {str(e)}",
        )


# ===========================================================================
# PR-9: Policy Engine Endpoints
# ===========================================================================


@app.get("/v1/policy/rules")
async def list_policy_rules(tenant_id: str | None = None):
    """
    List active policy rules.

    Query params:
    - tenant_id: filter by tenant (optional, includes system rules)
    """
    try:
        conn = await get_db_connection()
        try:
            rules = await get_active_rules(conn, tenant_id)
            return {"rules": rules, "count": len(rules)}
        finally:
            await conn.close()
    except Exception as e:
        logger.error(f"Failed to list policy rules: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/policy/evaluate")
async def evaluate_policy(
    proposal: dict,
    job_id: str,
    tenant_id: str | None = None,
    x_request_id: str | None = Header(default=None),
):
    """
    Evaluate a proposal against policy rules.

    Body:
    - proposal: The proposal dict with entries, total_amount, vendor, etc.
    - job_id: Job ID for tracing
    - tenant_id: Tenant ID (optional)

    Returns:
    - overall_result: approved, rejected, or requires_review
    - auto_approved: True if can be auto-approved
    - details: Per-rule evaluation results
    """
    request_id = x_request_id or get_request_id()
    try:
        conn = await get_db_connection()
        try:
            evaluation = await policy_evaluate_proposal(
                conn,
                proposal=proposal,
                job_id=job_id,
                tenant_id=tenant_id,
                request_id=request_id,
            )
            return evaluation.to_dict()
        finally:
            await conn.close()
    except Exception as e:
        logger.error(f"[{request_id}] Policy evaluation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/jobs/{job_id}/policy")
async def get_job_policy(job_id: str):
    """
    Get policy evaluation for a job.

    Returns the latest policy evaluation result including
    per-rule pass/fail details.
    """
    try:
        conn = await get_db_connection()
        try:
            evaluation = await get_policy_evaluation(conn, job_id)
            if not evaluation:
                raise HTTPException(status_code=404, detail=f"No policy evaluation for job: {job_id}")
            return evaluation
        finally:
            await conn.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get policy for job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===========================================================================
# PR-10: Data Zones + Idempotency Endpoints
# ===========================================================================


@app.get("/v1/jobs/{job_id}/zones")
async def get_zones(job_id: str):
    """
    Get data zone history for a job.

    Returns chronological list of zones the data passed through:
    raw -> extracted -> proposed -> posted
    """
    try:
        conn = await get_db_connection()
        try:
            zones = await get_job_zones(conn, job_id)
            return {"job_id": job_id, "zones": zones, "count": len(zones)}
        finally:
            await conn.close()
    except Exception as e:
        logger.error(f"Failed to get zones for job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/jobs/{job_id}/state")
async def get_state(job_id: str):
    """
    Get job processing state.

    Returns current state, previous state, checkpoint data for resumption.
    """
    try:
        conn = await get_db_connection()
        try:
            state = await get_job_state(conn, job_id)
            if not state:
                raise HTTPException(status_code=404, detail=f"No state for job: {job_id}")
            return state
        finally:
            await conn.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get state for job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/documents/check-duplicate")
async def check_duplicate(
    checksum: str,
    file_size: int,
    tenant_id: str | None = None,
):
    """
    Check if document is a duplicate.

    Query params:
    - checksum: SHA256 of file content
    - file_size: File size in bytes
    - tenant_id: Tenant ID (optional)

    Returns existing job info if duplicate, 404 if not found.
    """
    try:
        conn = await get_db_connection()
        try:
            duplicate = await check_document_duplicate(conn, checksum, file_size, tenant_id)
            if not duplicate:
                raise HTTPException(status_code=404, detail="Document not found (not a duplicate)")
            return {
                "is_duplicate": True,
                "original_job_id": duplicate["first_job_id"],
                "document_id": duplicate["document_id"],
                "duplicate_count": duplicate["duplicate_count"],
            }
        finally:
            await conn.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to check duplicate: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===========================================================================
# PR-11: Event Bus / Outbox Endpoints
# ===========================================================================


@app.get("/v1/outbox/stats")
async def outbox_stats():
    """
    Get outbox event statistics.

    Returns counts by status:
    - pending: Events waiting to be delivered
    - processing: Events currently being delivered
    - delivered: Successfully delivered events
    - failed: Failed events (will retry)
    - dead_letter: Events that exceeded retry limit
    """
    try:
        conn = await get_db_connection()
        try:
            stats = await get_outbox_stats(conn)
            return stats
        finally:
            await conn.close()
    except Exception as e:
        logger.error(f"Failed to get outbox stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/outbox/pending")
async def list_pending_outbox_events(limit: int = 50):
    """
    List pending outbox events.

    Query params:
    - limit: Max results (default: 50)

    Useful for debugging event delivery issues.
    """
    try:
        conn = await get_db_connection()
        try:
            events = await get_pending_events(conn, limit=limit)
            return {"events": events, "count": len(events)}
        finally:
            await conn.close()
    except Exception as e:
        logger.error(f"Failed to list pending events: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===========================================================================
# PR-12: Observability Endpoints
# ===========================================================================


@app.get("/v1/metrics")
async def list_metrics():
    """List all available metric names."""
    try:
        conn = await get_db_connection()
        try:
            names = await list_metric_names(conn)
            return {"metrics": names, "count": len(names)}
        finally:
            await conn.close()
    except Exception as e:
        logger.error(f"Failed to list metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/metrics/{metric_name}")
async def get_metric(metric_name: str, hours: int = 24):
    """
    Get statistics for a specific metric.

    Query params:
    - hours: Time window in hours (default: 24)

    Returns aggregate stats: avg, min, max, p50, p95, p99.
    """
    try:
        conn = await get_db_connection()
        try:
            stats = await get_metric_stats(conn, metric_name, hours)
            return stats
        finally:
            await conn.close()
    except Exception as e:
        logger.error(f"Failed to get metric {metric_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/evaluations")
async def list_evals(limit: int = 20):
    """
    List recent evaluation runs.

    Query params:
    - limit: Max results (default: 20)
    """
    try:
        conn = await get_db_connection()
        try:
            runs = await list_evaluation_runs(conn, limit)
            return {"evaluations": runs, "count": len(runs)}
        finally:
            await conn.close()
    except Exception as e:
        logger.error(f"Failed to list evaluations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/evaluations/{run_id}")
async def get_eval(run_id: str):
    """Get details of a specific evaluation run."""
    try:
        conn = await get_db_connection()
        try:
            run = await get_evaluation_run(conn, run_id)
            if not run:
                raise HTTPException(status_code=404, detail=f"Evaluation run not found: {run_id}")
            return run
        finally:
            await conn.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get evaluation {run_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/alerts")
async def list_alerts():
    """List currently firing alerts."""
    try:
        conn = await get_db_connection()
        try:
            alerts = await list_active_alerts(conn)
            return {"alerts": alerts, "count": len(alerts)}
        finally:
            await conn.close()
    except Exception as e:
        logger.error(f"Failed to list alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/alerts/check")
async def trigger_alert_check():
    """
    Manually trigger alert rule evaluation.

    Returns list of alerts that fired.
    """
    try:
        conn = await get_db_connection()
        try:
            fired = await check_alerts(conn)
            return {
                "checked": True,
                "fired_alerts": fired,
                "count": len(fired),
            }
        finally:
            await conn.close()
    except Exception as e:
        logger.error(f"Failed to check alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
