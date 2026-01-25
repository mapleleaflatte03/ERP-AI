"""
ERPX AI Accounting - Document Routes (UI-Facing)
================================================
These endpoints provide a document-centric view for the UI,
mapping to the underlying jobs-based architecture.
"""

import logging
import os
import sys
from datetime import datetime
from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException, Query

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["Documents"])


# =============================================================================
# Helper Functions
# =============================================================================

async def get_db_pool():
    """Get database connection pool"""
    try:
        from src.db import get_pool
        return await get_pool()
    except Exception as e:
        logger.error(f"Failed to get DB pool: {e}")
        return None


def format_document(row: dict) -> dict:
    """Format a job record as a document response"""
    return {
        "id": row.get("id"),
        "filename": row.get("filename"),
        "content_type": row.get("content_type"),
        "file_size": row.get("file_size"),
        "status": row.get("status", "pending"),
        "document_type": row.get("document_type"),
        "created_at": row.get("created_at").isoformat() if row.get("created_at") else None,
        "updated_at": row.get("updated_at").isoformat() if row.get("updated_at") else None,
        # Extracted fields
        "extracted_fields": row.get("extracted_data") or {},
        "invoice_no": (row.get("extracted_data") or {}).get("invoice_no"),
        "invoice_date": (row.get("extracted_data") or {}).get("invoice_date"),
        "vendor_name": (row.get("extracted_data") or {}).get("vendor_name"),
        "vendor_tax_id": (row.get("extracted_data") or {}).get("vendor_tax_id"),
        "total_amount": (row.get("extracted_data") or {}).get("total_amount"),
        "vat_amount": (row.get("extracted_data") or {}).get("vat_amount"),
        "currency": (row.get("extracted_data") or {}).get("currency", "VND"),
        "extracted_text": (row.get("extracted_data") or {}).get("raw_text"),
        # File URL (for preview)
        "file_url": f"/api/v1/files/{row.get('minio_bucket')}/{row.get('minio_key')}" if row.get("minio_key") else None,
        # Approval state
        "approval_state": row.get("approval_state"),
    }


def format_proposal(row: dict) -> dict:
    """Format a proposal record"""
    entries_raw = row.get("entries") or []
    entries = []
    total_debit = 0.0
    total_credit = 0.0
    
    for entry in entries_raw:
        debit = float(entry.get("debit", 0) or 0)
        credit = float(entry.get("credit", 0) or 0)
        total_debit += debit
        total_credit += credit
        entries.append({
            "account_code": entry.get("account_code", entry.get("debit_account", entry.get("credit_account"))),
            "account_name": entry.get("account_name", ""),
            "debit": debit,
            "credit": credit,
            "description": entry.get("description", ""),
        })
    
    return {
        "id": row.get("id"),
        "job_id": row.get("job_id"),
        "status": row.get("status", "pending"),
        "posting_date": row.get("invoice_date").isoformat() if row.get("invoice_date") else None,
        "description": row.get("description"),
        "vendor_name": row.get("vendor_name"),
        "invoice_number": row.get("invoice_number"),
        "total_amount": float(row.get("total_amount") or 0),
        "vat_amount": float(row.get("vat_amount") or 0),
        "entries": entries,
        "total_debit": total_debit,
        "total_credit": total_credit,
        "ai_confidence": float(row.get("confidence") or 0),
        "reasoning": row.get("reasoning"),
        "created_at": row.get("created_at").isoformat() if row.get("created_at") else None,
    }


# =============================================================================
# Document List & Detail
# =============================================================================

@router.get("")
async def list_documents(
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> dict:
    """
    List all documents with optional status filter.
    Returns documents from the jobs table.
    """
    pool = await get_db_pool()
    if not pool:
        raise HTTPException(status_code=503, detail="Database unavailable")
    
    async with pool.acquire() as conn:
        if status:
            rows = await conn.fetch(
                """
                SELECT id, filename, content_type, file_size, status, document_type,
                       extracted_data, minio_bucket, minio_key, approval_state,
                       created_at, updated_at
                FROM jobs
                WHERE status = $1
                ORDER BY created_at DESC
                LIMIT $2 OFFSET $3
                """,
                status, limit, offset
            )
        else:
            rows = await conn.fetch(
                """
                SELECT id, filename, content_type, file_size, status, document_type,
                       extracted_data, minio_bucket, minio_key, approval_state,
                       created_at, updated_at
                FROM jobs
                ORDER BY created_at DESC
                LIMIT $1 OFFSET $2
                """,
                limit, offset
            )
        
        documents = [format_document(dict(row)) for row in rows]
        
        # Get total count
        count_row = await conn.fetchrow("SELECT COUNT(*) as total FROM jobs")
        total = count_row["total"] if count_row else 0
        
        return {
            "documents": documents,
            "total": total,
            "limit": limit,
            "offset": offset,
        }


@router.get("/{document_id}")
async def get_document(document_id: str) -> dict:
    """
    Get a single document by ID.
    Returns the job record formatted as a document.
    """
    pool = await get_db_pool()
    if not pool:
        raise HTTPException(status_code=503, detail="Database unavailable")
    
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, filename, content_type, file_size, status, document_type,
                   extracted_data, journal_proposal, validation_result,
                   minio_bucket, minio_key, approval_state,
                   created_at, updated_at
            FROM jobs
            WHERE id = $1
            """,
            document_id
        )
        
        if not row:
            raise HTTPException(status_code=404, detail="Document not found")
        
        doc = format_document(dict(row))
        
        # Add additional fields from related tables
        extracted = await conn.fetchrow(
            "SELECT * FROM extracted_invoices WHERE job_id = $1 ORDER BY created_at DESC LIMIT 1",
            document_id
        )
        if extracted:
            doc["invoice_no"] = extracted.get("invoice_number") or doc.get("invoice_no")
            doc["invoice_date"] = extracted.get("invoice_date").isoformat() if extracted.get("invoice_date") else doc.get("invoice_date")
            doc["vendor_name"] = extracted.get("vendor_name") or doc.get("vendor_name")
            doc["vendor_tax_id"] = extracted.get("vendor_tax_id") or doc.get("vendor_tax_id")
            doc["total_amount"] = float(extracted.get("total_amount") or 0) or doc.get("total_amount")
            doc["vat_amount"] = float(extracted.get("vat_amount") or 0) or doc.get("vat_amount")
            doc["extracted_text"] = extracted.get("raw_text") or doc.get("extracted_text")
            if extracted.get("line_items"):
                doc["extracted_fields"]["line_items"] = extracted["line_items"]
        
        return doc


# =============================================================================
# Document Actions
# =============================================================================

@router.post("/{document_id}/extract")
async def run_extraction(document_id: str) -> dict:
    """
    Trigger document extraction for a document.
    This is typically handled by the workflow, but provides a manual trigger.
    """
    pool = await get_db_pool()
    if not pool:
        raise HTTPException(status_code=503, detail="Database unavailable")
    
    async with pool.acquire() as conn:
        # Update status to extracting
        await conn.execute(
            "UPDATE jobs SET status = 'extracting', updated_at = NOW() WHERE id = $1",
            document_id
        )
    
    # In a real implementation, this would trigger the Temporal workflow
    return {
        "message": "Extraction started",
        "document_id": document_id,
        "status": "extracting",
    }


@router.post("/{document_id}/propose")
async def run_proposal(document_id: str) -> dict:
    """
    Trigger journal proposal generation for a document.
    """
    pool = await get_db_pool()
    if not pool:
        raise HTTPException(status_code=503, detail="Database unavailable")
    
    async with pool.acquire() as conn:
        # Update status to proposing
        await conn.execute(
            "UPDATE jobs SET status = 'proposing', updated_at = NOW() WHERE id = $1",
            document_id
        )
    
    return {
        "message": "Proposal generation started",
        "document_id": document_id,
        "status": "proposing",
    }


@router.get("/{document_id}/proposal")
async def get_document_proposal(document_id: str) -> dict:
    """
    Get the journal proposal for a document.
    """
    pool = await get_db_pool()
    if not pool:
        raise HTTPException(status_code=503, detail="Database unavailable")
    
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT jp.*, j.filename, j.status as job_status
            FROM journal_proposals jp
            JOIN jobs j ON jp.job_id = j.id
            WHERE jp.job_id = $1
            ORDER BY jp.created_at DESC
            LIMIT 1
            """,
            document_id
        )
        
        if not row:
            raise HTTPException(status_code=404, detail="No proposal found for this document")
        
        return format_proposal(dict(row))


@router.get("/{document_id}/evidence")
async def get_document_evidence(document_id: str) -> List[dict]:
    """
    Get the processing evidence/timeline for a document.
    """
    pool = await get_db_pool()
    if not pool:
        raise HTTPException(status_code=503, detail="Database unavailable")
    
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, action, entity_type, old_value, new_value, created_at
            FROM audit_logs
            WHERE job_id = $1
            ORDER BY created_at ASC
            """,
            document_id
        )
        
        events = []
        for row in rows:
            events.append({
                "id": str(row["id"]),
                "step": row.get("entity_type", "processing"),
                "action": row.get("action", "unknown"),
                "timestamp": row["created_at"].isoformat() if row.get("created_at") else None,
                "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
                "output_summary": row.get("new_value", {}).get("summary") if isinstance(row.get("new_value"), dict) else None,
                "severity": "info",
            })
        
        return events


@router.post("/{document_id}/submit")
async def submit_for_approval(document_id: str, body: dict = None) -> dict:
    """
    Submit a document for approval.
    """
    pool = await get_db_pool()
    if not pool:
        raise HTTPException(status_code=503, detail="Database unavailable")
    
    import uuid
    approval_id = str(uuid.uuid4())
    
    async with pool.acquire() as conn:
        # Get proposal ID
        proposal = await conn.fetchrow(
            "SELECT id FROM journal_proposals WHERE job_id = $1 ORDER BY created_at DESC LIMIT 1",
            document_id
        )
        proposal_id = proposal["id"] if proposal else None
        
        # Create approval record
        await conn.execute(
            """
            INSERT INTO approvals (id, job_id, proposal_id, action, created_at)
            VALUES ($1, $2, $3, 'pending', NOW())
            """,
            approval_id, document_id, proposal_id
        )
        
        # Update job status
        await conn.execute(
            "UPDATE jobs SET status = 'pending_approval', approval_state = 'pending', updated_at = NOW() WHERE id = $1",
            document_id
        )
    
    return {
        "message": "Document submitted for approval",
        "document_id": document_id,
        "approval_id": approval_id,
        "status": "pending_approval",
    }


# =============================================================================
# Ledger Results
# =============================================================================

@router.get("/{document_id}/ledger")
async def get_document_ledger(document_id: str) -> dict:
    """
    Get the ledger entry for an approved document.
    """
    pool = await get_db_pool()
    if not pool:
        raise HTTPException(status_code=503, detail="Database unavailable")
    
    async with pool.acquire() as conn:
        entry = await conn.fetchrow(
            """
            SELECT le.*, j.filename
            FROM ledger_entries le
            JOIN jobs j ON le.job_id = j.id
            WHERE le.job_id = $1
            LIMIT 1
            """,
            document_id
        )
        
        if not entry:
            return {"posted": False, "message": "No ledger entry for this document"}
        
        lines = await conn.fetch(
            """
            SELECT * FROM ledger_lines WHERE entry_id = $1 ORDER BY line_order
            """,
            entry["id"]
        )
        
        return {
            "posted": True,
            "id": entry["id"],
            "entry_date": entry["entry_date"].isoformat() if entry.get("entry_date") else None,
            "description": entry.get("description"),
            "reference": entry.get("reference"),
            "total_debit": float(entry.get("total_debit") or 0),
            "total_credit": float(entry.get("total_credit") or 0),
            "posted_by": entry.get("posted_by"),
            "posted_at": entry["posted_at"].isoformat() if entry.get("posted_at") else None,
            "lines": [
                {
                    "account_code": line.get("account_code"),
                    "account_name": line.get("account_name"),
                    "debit": float(line.get("debit") or 0),
                    "credit": float(line.get("credit") or 0),
                    "description": line.get("description"),
                }
                for line in lines
            ],
        }
