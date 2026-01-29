"""
ERPX AI Accounting - Document Routes (UI-Facing)
================================================
Provides document-centric API endpoints for the UI.
"""

import logging
import os
import sys
import uuid
from datetime import datetime
from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks

sys.path.insert(0, "/root/erp-ai")

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["Documents"])


async def get_db_pool():
    """Get database connection pool"""
    try:
        from src.db import get_pool

        return await get_pool()
    except Exception as e:
        logger.error(f"Failed to get DB pool: {e}")
        return None


def format_document(row: dict) -> dict:
    """Format a document row for API response"""
    extracted_data = row.get("extracted_data") or {}
    if isinstance(extracted_data, str):
        try:
            extracted_data = json.loads(extracted_data)
        except:
            extracted_data = {}
    return {
        "id": str(row.get("id")),
        "filename": row.get("filename"),
        "content_type": row.get("content_type"),
        "file_size": row.get("file_size"),
        "status": row.get("status", "pending"),
        "document_type": row.get("doc_type"),
        "created_at": row.get("created_at").isoformat() if row.get("created_at") else None,
        "updated_at": row.get("updated_at").isoformat() if row.get("updated_at") else None,
        # Extracted fields
        "extracted_fields": extracted_data,
        "invoice_no": extracted_data.get("invoice_no") or extracted_data.get("invoice_number"),
        "invoice_date": extracted_data.get("invoice_date"),
        "vendor_name": extracted_data.get("vendor_name") or extracted_data.get("seller_name"),
        "vendor_tax_id": extracted_data.get("vendor_tax_id") or extracted_data.get("seller_tax_code"),
        "total_amount": extracted_data.get("total_amount"),
        "vat_amount": extracted_data.get("vat_amount"),
        "currency": extracted_data.get("currency", "VND"),
        "extracted_text": row.get("raw_text"),
        # OCR Boxes
        "ocr_boxes": extracted_data.get("ocr_boxes", []),
        # File URL
        "file_url": f"/v1/files/{row.get('minio_bucket')}/{row.get('minio_key')}" if row.get("minio_key") else None,
    }


def format_proposal(row: dict) -> dict:
    """Format a proposal row for API response"""
    entries_raw = row.get("entries") or []
    entries = []
    total_debit = 0.0
    total_credit = 0.0

    for entry in entries_raw:
        debit = float(entry.get("debit", 0) or 0)
        credit = float(entry.get("credit", 0) or 0)
        total_debit += debit
        total_credit += credit
        entries.append(
            {
                "account_code": entry.get("account_code", entry.get("debit_account", entry.get("credit_account"))),
                "account_name": entry.get("account_name", ""),
                "debit": debit,
                "credit": credit,
                "description": entry.get("description", ""),
            }
        )

    return {
        "id": str(row.get("id")),
        "document_id": str(row.get("document_id")),
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
        "ai_confidence": float(row.get("ai_confidence") or 0),
        "reasoning": row.get("ai_reasoning"),
        "created_at": row.get("created_at").isoformat() if row.get("created_at") else None,
    }


@router.get("")
async def list_documents(
    status: Optional[str] = Query(None, description="Filter by status"),
    doc_type: Optional[str] = Query(None, alias="type", description="Filter by document type"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> dict:
    """List all documents with optional status and type filter."""
    pool = await get_db_pool()
    if not pool:
        raise HTTPException(status_code=503, detail="Database unavailable")

    async with pool.acquire() as conn:
        conditions = []
        params = []
        param_idx = 1

        if status:
            conditions.append(f"status = ${param_idx}")
            params.append(status)
            param_idx += 1
        
        if doc_type:
            conditions.append(f"doc_type = ${param_idx}")
            params.append(doc_type)
            param_idx += 1

        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
        
        query = f"""
            SELECT id, filename, content_type, file_size, status, doc_type,
                   extracted_data, minio_bucket, minio_key, raw_text,
                   created_at, updated_at
            FROM documents
            {where_clause}
            ORDER BY created_at DESC
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """
        
        # Add limit and offset to params
        params.append(limit)
        params.append(offset)

        rows = await conn.fetch(query, *params)
        
        # Get count
        count_query = f"SELECT COUNT(*) as total FROM documents {where_clause}"
        # For count we only need the filter params, not limit/offset
        count_params = params[:-2] 
        count_row = await conn.fetchrow(count_query, *count_params)

        documents = [format_document(dict(row)) for row in rows]
        total = count_row["total"] if count_row else 0

        return {
            "documents": documents,
            "total": total,
            "limit": limit,
            "offset": offset,
        }


@router.get("/{document_id}")
async def get_document(document_id: str) -> dict:
    """Get a single document by ID."""
    pool = await get_db_pool()
    if not pool:
        raise HTTPException(status_code=503, detail="Database unavailable")

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, filename, content_type, file_size, status, doc_type,
                   extracted_data, proposal, validation_result, raw_text,
                   minio_bucket, minio_key, created_at, updated_at
            FROM documents
            WHERE id::text = $1 OR job_id = $1
            """,
            document_id,
        )

        if not row:
            raise HTTPException(status_code=404, detail="Document not found")

        doc = format_document(dict(row))

        # Get extracted invoice data
        extracted = await conn.fetchrow(
            "SELECT * FROM extracted_invoices WHERE document_id = $1 ORDER BY created_at DESC LIMIT 1", row["id"]
        )
        if extracted:
            doc["invoice_no"] = extracted.get("invoice_number") or doc.get("invoice_no")
            doc["invoice_date"] = (
                extracted.get("invoice_date").isoformat() if extracted.get("invoice_date") else doc.get("invoice_date")
            )
            doc["vendor_name"] = extracted.get("vendor_name") or doc.get("vendor_name")
            doc["vendor_tax_id"] = extracted.get("vendor_tax_id") or doc.get("vendor_tax_id")
            doc["total_amount"] = float(extracted.get("total_amount") or 0) or doc.get("total_amount")
            doc["vat_amount"] = float(extracted.get("vat_amount") or 0) or doc.get("vat_amount")
            if extracted.get("line_items"):
                doc["extracted_fields"]["line_items"] = extracted["line_items"]

        return doc


from fastapi import BackgroundTasks
from src.processing import process_document
from src.storage import get_minio_client
from src.llm import get_llm_client
import json

async def process_extraction_task(document_id: str):
    """Background task for document extraction"""
    try:
        pool = await get_db_pool()
        if not pool:
            return

        async with pool.acquire() as conn:
            # Get document info
            doc = await conn.fetchrow(
                "SELECT id, minio_bucket, minio_key, filename, content_type FROM documents WHERE id::text = $1 OR job_id = $1", document_id
            )
            if not doc or not doc["minio_bucket"] or not doc["minio_key"]:
                await conn.execute("UPDATE documents SET status = 'failed', updated_at = NOW() WHERE id::text = $1 OR job_id = $1", document_id)
                return

            # Download from MinIO
            minio_client = get_minio_client()
            try:
                data = minio_client.get_object(doc["minio_bucket"], doc["minio_key"]).read()
            except Exception as e:
                logger.error(f"Failed to download from MinIO: {e}")
                await conn.execute("UPDATE documents SET status = 'failed', updated_at = NOW() WHERE id = $1", document_id)
                return

            # Run Processing
            result = process_document(data, doc["content_type"], doc["filename"])
            
            if result.success:
                # Store extracted data including boxes
                extracted_payload = result.key_fields
                if result.boxes:
                    extracted_payload["ocr_boxes"] = result.boxes

                # Rule-based classification (Phase 3 - Fix B2)
                doc_type = "other"
                text = (result.document_text or "").lower()
                if "hóa đơn" in text or "invoice" in text or "giá trị gia tăng" in text:
                    doc_type = "invoice"
                elif "phiếu thu" in text or "receipt" in text:
                    doc_type = "receipt"
                elif "phiếu chi" in text or "payment" in text or "vouchers" in text:
                    doc_type = "payment"
                elif "sổ phụ" in text or "sao kê" in text or "bank statement" in text:
                    doc_type = "bank_statement"
                
                # If extraction was very specific about invoice, override
                if "invoice_number" in result.key_fields and result.key_fields["invoice_number"]:
                    doc_type = "invoice"

                await conn.execute(
                    """
                    UPDATE documents 
                    SET status = 'extracted', 
                        doc_type = $2,
                        extracted_data = $3, 
                        raw_text = $4,
                        validation_result = $5,
                        updated_at = NOW() 
                    WHERE id = $1
                    """,
                    document_id,
                    doc_type,
                    json.dumps(extracted_payload),
                    result.document_text,
                    json.dumps({"confidence": result.confidence})
                )
                
                # Backfill extracted_invoices table for B2/B4
                if doc_type == "invoice":
                    invoice_id = str(uuid.uuid4())
                    await conn.execute(
                        """
                        INSERT INTO extracted_invoices 
                        (id, document_id, tenant_id, vendor_name, vendor_tax_id, invoice_number, 
                         invoice_date, total_amount, currency, ai_confidence, created_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, NOW())
                        ON CONFLICT DO NOTHING
                        """,
                        invoice_id,
                        document_id,
                        doc.get("tenant_id", "default"),
                        result.key_fields.get("vendor_name") or result.key_fields.get("seller_name", "Unknown"),
                        result.key_fields.get("vendor_tax_id", ""),
                        result.key_fields.get("invoice_number", f"INV-{document_id[:8]}"),
                        datetime.now().date(), # Fallback date
                        float(result.key_fields.get("total_amount") or 0),
                        result.key_fields.get("currency", "VND"),
                        float(result.confidence or 0.8)
                    )
                    
            else:
                 await conn.execute("UPDATE documents SET status = 'failed', updated_at = NOW() WHERE id = $1", document_id)

    except Exception as e:
        logger.error(f"Extraction task failed: {e}")


async def process_proposal_task(document_id: str):
    """Background task for journal proposal generation"""
    try:
        pool = await get_db_pool()
        if not pool:
            return

        async with pool.acquire() as conn:
            # Get document info
            doc = await conn.fetchrow("SELECT raw_text, extracted_data, tenant_id FROM documents WHERE id = $1", document_id)
            
            if not doc or not doc["raw_text"]:
                await conn.execute("UPDATE documents SET status = 'failed', updated_at = NOW() WHERE id = $1", document_id)
                return

            # Call LLM
            llm = get_llm_client()
            prompt = f"""
            Analyze this accounting document text and extracted data.
            Generate a journal entry proposal (debit/credit).
            Return valid JSON only.
            
            Extracted Data: {doc['extracted_data']}
            
            Document Text:
            {doc['raw_text'][:4000]}
            """
            
            schema = {
                "type": "object",
                "properties": {
                    "entries": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "account_code": {"type": "string"},
                                "account_name": {"type": "string"},
                                "debit": {"type": "number"},
                                "credit": {"type": "number"},
                                "description": {"type": "string"}
                            },
                             "required": ["account_code", "debit", "credit", "description"]
                        }
                    },
                    "reasoning": {"type": "string"},
                    "confidence": {"type": "number"}
                },
                "required": ["entries", "reasoning"]
            }
            
            try:
                response = await llm.generate_json(prompt, schema=schema)
                
                # Insert Proposal
                proposal_id = str(uuid.uuid4())
                entries = response.get("entries", [])
                total_debit = sum(e.get("debit", 0) for e in entries)
                total_credit = sum(e.get("credit", 0) for e in entries)
                
                # Fetch tenant_id (assuming simple setup for now, or fallback)
                tenant_id = doc.get("tenant_id")
                
                await conn.execute(
                    """
                    INSERT INTO journal_proposals (id, document_id, status, ai_confidence, ai_reasoning, created_at)
                    VALUES ($1, $2, 'pending', $3, $4, NOW())
                    """,
                    proposal_id,
                    document_id,
                    float(response.get("confidence", 0.0)),
                    response.get("reasoning", "")
                )

                # Insert Entries
                for idx, entry in enumerate(entries):
                    await conn.execute(
                        """
                        INSERT INTO journal_proposal_entries
                        (id, proposal_id, account_code, account_name, debit_amount, credit_amount, line_order)
                        VALUES ($1, $2, $3, $4, $5, $6, $7)
                        """,
                        str(uuid.uuid4()),
                        proposal_id,
                        entry.get("account_code", ""),
                        entry.get("account_name", ""),
                        float(entry.get("debit", 0) or 0),
                        float(entry.get("credit", 0) or 0),
                        idx + 1
                    )
                
                # Create Pending Approval so UI can approve it
                approval_id = str(uuid.uuid4())
                await conn.execute(
                    """
                    INSERT INTO approvals (id, proposal_id, tenant_id, job_id, action, status, created_at)
                    VALUES ($1, $2, $3, $4, 'pending', 'pending', NOW())
                    """,
                    approval_id,
                    proposal_id,
                    tenant_id,
                    document_id
                )
                
                # Update Document
                await conn.execute("UPDATE documents SET status = 'proposed', updated_at = NOW() WHERE id = $1", document_id)

            except Exception as llm_error:
                logger.error(f"LLM generation failed: {llm_error}")
                await conn.execute("UPDATE documents SET status = 'failed', updated_at = NOW() WHERE id = $1", document_id)

    except Exception as e:
        logger.error(f"Proposal task failed: {e}")


@router.post("/{document_id}/extract")
async def run_extraction(document_id: str, background_tasks: BackgroundTasks) -> dict:
    """Trigger document extraction."""
    pool = await get_db_pool()
    if not pool:
        raise HTTPException(status_code=503, detail="Database unavailable")

    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE documents SET status = 'extracting', updated_at = NOW() WHERE id::text = $1 OR job_id = $1", document_id
        )
    
    background_tasks.add_task(process_extraction_task, document_id)

    return {"message": "Extraction started", "document_id": document_id, "status": "extracting"}


@router.post("/{document_id}/propose")
async def run_proposal(document_id: str, background_tasks: BackgroundTasks) -> dict:
    """Trigger journal proposal generation."""
    pool = await get_db_pool()
    if not pool:
        raise HTTPException(status_code=503, detail="Database unavailable")

    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE documents SET status = 'proposing', updated_at = NOW() WHERE id::text = $1 OR job_id = $1", document_id
        )
    
    background_tasks.add_task(process_proposal_task, document_id)

    return {"message": "Proposal generation started", "document_id": document_id, "status": "proposing"}


@router.get("/{document_id}/proposal")
async def get_document_proposal(document_id: str) -> dict:
    """Get the journal proposal for a document."""
    pool = await get_db_pool()
    if not pool:
        raise HTTPException(status_code=503, detail="Database unavailable")

    async with pool.acquire() as conn:
        # First get the document ID if we have a job_id
        doc = await conn.fetchrow("SELECT id FROM documents WHERE id::text = $1 OR job_id = $1", document_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        row = await conn.fetchrow(
            """
            SELECT jp.*, d.filename
            FROM journal_proposals jp
            JOIN documents d ON jp.document_id = d.id
            WHERE jp.document_id = $1
            ORDER BY jp.created_at DESC
            LIMIT 1
            """,
            doc["id"],
        )

        if not row:
            raise HTTPException(status_code=404, detail="No proposal found")

        return format_proposal(dict(row))


@router.get("/{document_id}/evidence")
async def get_document_evidence(document_id: str) -> List[dict]:
    """Get the processing evidence/timeline for a document."""
    pool = await get_db_pool()
    if not pool:
        raise HTTPException(status_code=503, detail="Database unavailable")

    async with pool.acquire() as conn:
        # Try audit_evidence table first
        rows = await conn.fetch(
            """
            SELECT id, llm_stage, decision, llm_input_preview, llm_output_raw, 
                   created_at, updated_at
            FROM audit_evidence
            WHERE document_id = $1 OR job_id = $1
            ORDER BY created_at ASC
            """,
            document_id,
        )

        events = []
        for row in rows:
            events.append(
                {
                    "id": str(row["id"]),
                    "step": row.get("llm_stage", "processing"),
                    "action": row.get("llm_stage", "unknown"),
                    "timestamp": row["created_at"].isoformat() if row.get("created_at") else None,
                    "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
                    "output_summary": row.get("llm_output_raw"),
                    "severity": "success" if row.get("decision") == "approved" else "info",
                    "trace_id": None,
                }
            )

        return events


@router.post("/{document_id}/submit")
async def submit_for_approval(document_id: str, body: dict = None) -> dict:
    """Submit a document for approval."""
    pool = await get_db_pool()
    if not pool:
        raise HTTPException(status_code=503, detail="Database unavailable")

    approval_id = str(uuid.uuid4())

    async with pool.acquire() as conn:
        # Get document
        doc = await conn.fetchrow("SELECT id FROM documents WHERE id::text = $1 OR job_id = $1", document_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        # Get proposal
        proposal = await conn.fetchrow(
            "SELECT id FROM journal_proposals WHERE document_id = $1 ORDER BY created_at DESC LIMIT 1", doc["id"]
        )

        # Check for existing pending approval
        existing_approval = await conn.fetchrow(
            "SELECT id FROM approvals WHERE proposal_id = $1 AND status = 'pending'", proposal["id"]
        )
        
        if existing_approval:
            approval_id = str(existing_approval["id"])
        else:
            # Create approval record
            await conn.execute(
                """
                INSERT INTO approvals (id, document_id, proposal_id, status, created_at)
                VALUES ($1, $2, $3, 'pending', NOW())
                ON CONFLICT DO NOTHING
                """,
                approval_id,
                doc["id"],
                proposal["id"] if proposal else None,
            )

        # Update document status
        await conn.execute(
            "UPDATE documents SET status = 'pending_approval', updated_at = NOW() WHERE id = $1", doc["id"]
        )

    return {"message": "Submitted for approval", "document_id": document_id, "approval_id": approval_id}


@router.get("/{document_id}/ledger")
async def get_document_ledger(document_id: str) -> dict:
    """Get the ledger entry for an approved document."""
    pool = await get_db_pool()
    if not pool:
        raise HTTPException(status_code=503, detail="Database unavailable")

    async with pool.acquire() as conn:
        # Get document
        doc = await conn.fetchrow("SELECT id FROM documents WHERE id::text = $1 OR job_id = $1", document_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        # Get ledger entry
        entry = await conn.fetchrow(
            """
            SELECT le.*
            FROM ledger_entries le
            JOIN journal_proposals jp ON le.proposal_id = jp.id
            WHERE jp.document_id = $1
            LIMIT 1
            """,
            doc["id"],
        )

        if not entry:
            return {"posted": False, "message": "No ledger entry for this document"}

        # Get ledger lines
        lines = await conn.fetch("SELECT * FROM ledger_lines WHERE ledger_entry_id = $1 ORDER BY line_order", entry["id"])

        return {
            "posted": True,
            "id": str(entry["id"]),
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


@router.delete("/{document_id}")
async def delete_document(document_id: str) -> dict:
    """Delete a document and its related data."""
    pool = await get_db_pool()
    if not pool:
        raise HTTPException(status_code=503, detail="Database unavailable")

    async with pool.acquire() as conn:
        try:
            doc_uuid = uuid.UUID(document_id)
            # Check if exists
            doc = await conn.fetchrow("SELECT id FROM documents WHERE id = $1", doc_uuid)
            if not doc:
                 raise HTTPException(status_code=404, detail="Document not found")
            
            # Delete dependent records in full cascade (Phase 4 - Fix B3)
            # 0. Data zones (multiple FKs to document, proposal, ledger)
            await conn.execute("DELETE FROM data_zones WHERE document_id = $1 OR job_id::text = $2", doc_uuid, document_id)
            
            # 1. Ledger related
            await conn.execute("""
                DELETE FROM ledger_lines 
                WHERE ledger_entry_id IN (
                    SELECT id FROM ledger_entries 
                    WHERE proposal_id IN (SELECT id FROM journal_proposals WHERE document_id = $1)
                )
            """, doc_uuid)
            await conn.execute("DELETE FROM ledger_entries WHERE proposal_id IN (SELECT id FROM journal_proposals WHERE document_id = $1)", doc_uuid)
            
            # 2. Proposal related
            await conn.execute("DELETE FROM journal_proposal_entries WHERE proposal_id IN (SELECT id FROM journal_proposals WHERE document_id = $1)", doc_uuid)
            await conn.execute("DELETE FROM approvals WHERE proposal_id IN (SELECT id FROM journal_proposals WHERE document_id = $1)", doc_uuid)
            await conn.execute("DELETE FROM journal_proposals WHERE document_id = $1", doc_uuid)
            
            # 3. Extraction related
            await conn.execute("DELETE FROM extracted_invoices WHERE document_id = $1", doc_uuid)
            await conn.execute("DELETE FROM audit_evidence WHERE document_id = $1", doc_uuid)
            
            # 4. Finally delete the document
            await conn.execute("DELETE FROM documents WHERE id = $1 OR job_id = $2", doc_uuid, document_id)
        except ValueError:
             raise HTTPException(status_code=400, detail="Invalid document ID format")
        except Exception as e:
            logger.error(f"Error deleting document {document_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Internal deletion error: {str(e)}")

    return {"message": "Document deleted", "id": document_id}

# =============================================================================
# Journal Proposals List
# =============================================================================


@router.get("/journal-proposals", tags=["Journal Proposals"])
async def list_journal_proposals(
    status: Optional[str] = Query(None, description="Filter by status (pending, approved, rejected)"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> dict:
    """
    List all journal proposals with document details.
    """
    pool = await get_db_pool()
    if not pool:
        raise HTTPException(status_code=503, detail="Database unavailable")

    async with pool.acquire() as conn:
        # Build query with optional status filter
        base_query = """
            SELECT 
                jp.id,
                jp.document_id,
                jp.status,
                jp.ai_confidence,
                jp.ai_reasoning,
                jp.entries,
                jp.total_debit,
                jp.total_credit,
                jp.created_at,
                d.filename,
                d.doc_type,
                ei.vendor_name,
                ei.vendor_tax_id,
                ei.invoice_number,
                ei.invoice_date,
                ei.total_amount,
                ei.tax_amount as vat_amount,
                ei.currency
            FROM journal_proposals jp
            LEFT JOIN documents d ON jp.document_id = d.id
            LEFT JOIN extracted_invoices ei ON d.id = ei.document_id
        """

        if status:
            rows = await conn.fetch(
                base_query
                + """
                WHERE jp.status = $1
                ORDER BY jp.created_at DESC
                LIMIT $2 OFFSET $3
                """,
                status,
                limit,
                offset,
            )
            count_row = await conn.fetchrow("SELECT COUNT(*) as total FROM journal_proposals WHERE status = $1", status)
        else:
            rows = await conn.fetch(
                base_query
                + """
                ORDER BY jp.created_at DESC
                LIMIT $1 OFFSET $2
                """,
                limit,
                offset,
            )
            count_row = await conn.fetchrow("SELECT COUNT(*) as total FROM journal_proposals")

        proposals = []
        for row in rows:
            entries_raw = row.get("entries") or []
            entries = []
            total_debit = float(row.get("total_debit") or 0)
            total_credit = float(row.get("total_credit") or 0)

            # If totals not stored, calculate from entries
            if total_debit == 0 and total_credit == 0:
                for entry in entries_raw:
                    debit = float(entry.get("debit", 0) or 0)
                    credit = float(entry.get("credit", 0) or 0)
                    total_debit += debit
                    total_credit += credit
                    entries.append(
                        {
                            "account_code": entry.get(
                                "account_code", entry.get("debit_account", entry.get("credit_account"))
                            ),
                            "account_name": entry.get("account_name", ""),
                            "debit": debit,
                            "credit": credit,
                            "description": entry.get("description", ""),
                        }
                    )
            else:
                entries = entries_raw

            proposals.append(
                {
                    "id": str(row["id"]),
                    "document_id": str(row["document_id"]) if row.get("document_id") else None,
                    "filename": row.get("filename"),
                    "document_type": row.get("doc_type"),
                    "vendor_name": row.get("vendor_name"),
                    "vendor_tax_id": row.get("vendor_tax_id"),
                    "invoice_number": row.get("invoice_number"),
                    "invoice_date": row["invoice_date"].isoformat() if row.get("invoice_date") else None,
                    "total_amount": float(row.get("total_amount") or 0),
                    "vat_amount": float(row.get("vat_amount") or 0),
                    "currency": row.get("currency", "VND"),
                    "status": row.get("status", "pending"),
                    "ai_confidence": float(row.get("ai_confidence") or 0),
                    "ai_reasoning": row.get("ai_reasoning"),
                    "entries": entries,
                    "total_debit": total_debit,
                    "total_credit": total_credit,
                    "is_balanced": abs(total_debit - total_credit) < 0.01,
                    "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
                }
            )

        total = count_row["total"] if count_row else 0

        return {
            "proposals": proposals,
            "total": total,
            "limit": limit,
            "offset": offset,
        }
