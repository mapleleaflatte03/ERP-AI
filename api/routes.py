"""
ERPX AI Accounting - API Routes
===============================
"""

import asyncio
import os
import sys
import time
import uuid
from datetime import datetime
from functools import lru_cache

from fastapi import APIRouter, File, Header, HTTPException, Request, UploadFile

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.schemas import (
    APIResponse,
    ApprovalDecision,
    CodingRequest,
    ReconcileRequest,
)

# Import copilot (will be created/updated)
try:
    from agents.accounting_coding.erpx_copilot import ERPXAccountingCopilot
except ImportError:
    ERPXAccountingCopilot = None


@lru_cache(maxsize=128)
def get_copilot_instance(mode: str, tenant_id: str | None):
    """
    Get a cached instance of the ERPXAccountingCopilot.
    """
    if ERPXAccountingCopilot is None:
        raise HTTPException(status_code=500, detail="Copilot not available")
    return ERPXAccountingCopilot(mode=mode, tenant_id=tenant_id)


# Import orchestrator
try:
    from orchestrator.workflow import AccountingWorkflow
except ImportError:
    AccountingWorkflow = None

router = APIRouter(tags=["Accounting"])


def get_request_id(request: Request) -> str:
    """Get or generate request ID"""
    return getattr(request.state, "request_id", str(uuid.uuid4()))


def get_tenant_id(request: Request) -> str | None:
    """Get tenant ID from request state"""
    return getattr(request.state, "tenant_id", None)


# =============================================================================
# POST /v1/accounting/coding
# =============================================================================


@router.post("/accounting/coding", response_model=APIResponse)
async def process_document(request: Request, coding_request: CodingRequest):
    """
    Process a document for accounting coding.

    Accepts:
    - OCR text (raw string)
    - Structured fields (pre-extracted JSON)
    - File path (local file)
    - Base64 encoded file content

    Returns:
    - ASOFT-T compatible payload
    - Missing fields list
    - Warnings
    - Evidence for audit
    - needs_human_review flag
    """
    start_time = time.time()
    request_id = get_request_id(request)
    tenant_id = get_tenant_id(request) or coding_request.tenant_id

    try:
        # Get copilot instance
        copilot = get_copilot_instance(mode=coding_request.mode, tenant_id=tenant_id)

        # Process document
        result = copilot.process(
            ocr_text=coding_request.ocr_text,
            structured_fields=coding_request.structured_fields,
            file_metadata={"source_file": coding_request.file_path} if coding_request.file_path else None,
            doc_id=coding_request.doc_id,
        )

        processing_time = (time.time() - start_time) * 1000

        return APIResponse(
            success=True, data=result, request_id=request_id, processing_time_ms=round(processing_time, 2)
        )

    except Exception as e:
        processing_time = (time.time() - start_time) * 1000
        return APIResponse(
            success=False, error=str(e), request_id=request_id, processing_time_ms=round(processing_time, 2)
        )


# =============================================================================
# POST /v1/accounting/coding/file
# =============================================================================


@router.post("/accounting/coding/file", response_model=APIResponse)
async def process_file(
    request: Request,
    file: UploadFile = File(...),
    mode: str = "STRICT",
    doc_id: str | None = None,
    x_tenant_id: str | None = Header(None),
):
    """
    Process an uploaded file for accounting coding.

    Accepts image files (PNG, JPG, PDF) or JSON files with OCR results.
    """
    start_time = time.time()
    request_id = get_request_id(request)
    tenant_id = get_tenant_id(request) or x_tenant_id

    try:
        # Read file content
        content = await file.read()
        filename = file.filename or "uploaded_file"

        # Determine file type
        if filename.endswith(".json"):
            # JSON file - parse as structured
            import json

            structured_fields = json.loads(content.decode("utf-8"))
            ocr_text = structured_fields.get("ocr_text", "")
        else:
            # Image/PDF - would need OCR (mock for now)
            ocr_text = f"[File uploaded: {filename}, size: {len(content)} bytes]"
            structured_fields = None

        # Get copilot instance
        copilot = get_copilot_instance(mode=mode.upper(), tenant_id=tenant_id)

        # Process
        result = copilot.process(
            ocr_text=ocr_text,
            structured_fields=structured_fields,
            file_metadata={"source_file": filename},
            doc_id=doc_id or str(uuid.uuid4()),
        )

        processing_time = (time.time() - start_time) * 1000

        return APIResponse(
            success=True, data=result, request_id=request_id, processing_time_ms=round(processing_time, 2)
        )

    except Exception as e:
        processing_time = (time.time() - start_time) * 1000
        return APIResponse(
            success=False, error=str(e), request_id=request_id, processing_time_ms=round(processing_time, 2)
        )


# =============================================================================
# POST /v1/accounting/reconcile
# =============================================================================


@router.post("/accounting/reconcile", response_model=APIResponse)
async def reconcile_transactions(request: Request, reconcile_request: ReconcileRequest):
    """
    Reconcile invoices with bank transactions.

    Matching rules:
    - Amount tolerance: ±0.5% OR ±50,000 VND
    - Date window: ±7 days
    - Keyword boost: vendor/invoice_no in memo

    Returns:
    - matched: List of matched invoice-transaction pairs
    - unmatched_invoices: Invoices without bank match
    - unmatched_bank_txns: Bank transactions without invoice match
    """
    start_time = time.time()
    request_id = get_request_id(request)

    try:
        # Initialize copilot for reconciliation
        # Use STRICT mode by default for reconciliation if not specified
        copilot = get_copilot_instance(mode="STRICT", tenant_id=reconcile_request.tenant_id)

        # Convert bank_txns to dict format
        bank_txns = [
            {
                "txn_id": txn.txn_id,
                "txn_date": txn.txn_date,
                "amount": txn.amount,
                "memo": txn.memo,
                "account_no": txn.account_no,
            }
            for txn in reconcile_request.bank_txns
        ]

        # Process each invoice and reconcile
        tasks = []
        for invoice in reconcile_request.invoices:
            tasks.append(
                asyncio.to_thread(
                    copilot.process, structured_fields=invoice, bank_txns=bank_txns
                )
            )

        results = await asyncio.gather(*tasks)

        # Aggregate reconciliation results
        all_matched = []
        unmatched_invoices = []
        matched_txn_ids = set()

        for i, result in enumerate(results):
            recon = result.get("reconciliation_result", {})
            matched = recon.get("matched", [])

            if matched:
                all_matched.extend(matched)
                for m in matched:
                    matched_txn_ids.add(m.get("txn_id"))
            else:
                invoice_id = reconcile_request.invoices[i].get("doc_id", f"INV-{i}")
                unmatched_invoices.append(invoice_id)

        # Find unmatched bank transactions
        all_txn_ids = {txn.txn_id for txn in reconcile_request.bank_txns}
        unmatched_bank_txns = list(all_txn_ids - matched_txn_ids)

        processing_time = (time.time() - start_time) * 1000

        return APIResponse(
            success=True,
            data={
                "reconciliation_result": {
                    "matched": all_matched,
                    "unmatched_invoices": unmatched_invoices,
                    "unmatched_bank_txns": unmatched_bank_txns,
                },
                "total_invoices": len(reconcile_request.invoices),
                "total_bank_txns": len(reconcile_request.bank_txns),
                "matched_count": len(all_matched),
            },
            request_id=request_id,
            processing_time_ms=round(processing_time, 2),
        )

    except Exception as e:
        processing_time = (time.time() - start_time) * 1000
        return APIResponse(
            success=False, error=str(e), request_id=request_id, processing_time_ms=round(processing_time, 2)
        )


# =============================================================================
# POST /v1/accounting/batch
# =============================================================================


@router.post("/accounting/batch", response_model=APIResponse)
async def process_batch(
    request: Request, documents: list, mode: str = "STRICT", x_tenant_id: str | None = Header(None)
):
    """
    Process multiple documents in batch.

    Each document should have:
    - ocr_text OR structured_fields
    - Optional doc_id
    """
    start_time = time.time()
    request_id = get_request_id(request)
    tenant_id = get_tenant_id(request) or x_tenant_id

    try:
        copilot = get_copilot_instance(mode=mode.upper(), tenant_id=tenant_id)

        results = []
        errors = []

        for i, doc in enumerate(documents):
            try:
                result = copilot.process(
                    ocr_text=doc.get("ocr_text"),
                    structured_fields=doc.get("structured_fields"),
                    file_metadata=doc.get("file_metadata"),
                    doc_id=doc.get("doc_id", f"BATCH-{i}"),
                )
                results.append({"index": i, "success": True, "data": result})
            except Exception as e:
                errors.append({"index": i, "error": str(e)})
                results.append({"index": i, "success": False, "error": str(e)})

        processing_time = (time.time() - start_time) * 1000

        return APIResponse(
            success=len(errors) == 0,
            data={
                "results": results,
                "total": len(documents),
                "successful": len(documents) - len(errors),
                "failed": len(errors),
            },
            request_id=request_id,
            processing_time_ms=round(processing_time, 2),
        )

    except Exception as e:
        processing_time = (time.time() - start_time) * 1000
        return APIResponse(
            success=False, error=str(e), request_id=request_id, processing_time_ms=round(processing_time, 2)
        )


# =============================================================================
# Approval Endpoints
# =============================================================================


@router.get("/accounting/approvals", response_model=APIResponse)
async def list_approvals(
    request: Request, status: str | None = None, limit: int = 50, x_tenant_id: str | None = Header(None)
):
    """List pending approvals"""
    # Mock implementation - would query approval queue
    return APIResponse(success=True, data={"approvals": [], "total": 0, "pending": 0})


@router.post("/accounting/approvals/{approval_id}/decide", response_model=APIResponse)
async def decide_approval(request: Request, approval_id: str, decision: ApprovalDecision):
    """Approve or reject a pending approval"""
    # Mock implementation
    return APIResponse(
        success=True,
        data={"approval_id": approval_id, "decision": decision.decision, "processed_at": datetime.utcnow().isoformat()},
    )
