"""
ERPX AI Copilot Tools
=====================
Tools available to the Copilot agent for assisting users.

Architecture:
- READ tools: Direct database access (safe, no confirmation needed)
- WRITE tools: Go through Agent Action Proposals (Plan → Confirm → Execute)

This ensures sensitive actions like approvals require user confirmation.
"""

import logging
import uuid
from typing import Any, List, Dict, Optional

from src.approval import service as approval_service
from src.db import get_connection, get_pool

logger = logging.getLogger(__name__)


# =============================================================================
# READ TOOLS (Direct access - no confirmation needed)
# =============================================================================

async def list_pending_approvals(limit: int = 10) -> List[Dict[str, Any]]:
    """List pending journal proposals requiring approval."""
    try:
        async with get_connection() as conn:
             rows = await approval_service.list_pending_approvals(conn, limit=limit)
             
             results = []
             for row in rows:
                 doc = row.get("document") or {}
                 results.append({
                     "id": row.get("id"),
                     "doc_name": doc.get("filename") or row.get("filename") or "Document",
                     "doc_type": doc.get("doc_type") or row.get("doc_type") or "Unknown",
                     "counterparty": row.get("vendor_name") or "Unknown",
                     "amount": row.get("total_amount") or 0.0,
                     "currency": row.get("currency") or "VND",
                     "file_name": doc.get("filename") or row.get("filename"),
                     "status": row.get("status") or "pending"
                 })
             return results
    except Exception as e:
        logger.error(f"Error listing approvals: {e}")
        return []


async def get_approval_statistics() -> Dict[str, Any]:
    """Get counts of documents by status (approved/pending/rejected)."""
    try:
        async with get_connection() as conn:
            # Count status from approvals table
            stats = await conn.fetch("""
                SELECT status, COUNT(*) as count 
                FROM approvals 
                GROUP BY status
            """)
            
            # Map results
            counts = {"pending": 0, "approved": 0, "rejected": 0}
            for row in stats:
                status = row["status"] or "pending"
                counts[status] = row["count"]
                
            return counts
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return {"error": str(e)}


async def get_approval(approval_id: str) -> Dict[str, Any] | None:
    """Get single approval by ID with details."""
    try:
        async with get_connection() as conn:
             row = await approval_service.get_approval_by_id(conn, approval_id)
             if row:
                 return {
                     "id": row.get("id"),
                     "counterparty": row.get("vendor_name"),
                     "amount": row.get("total_amount"),
                     "currency": row.get("currency"),
                     "status": row.get("status"),
                     "invoice_no": row.get("invoice_number")
                 }
             return None
    except Exception as e:
        logger.error(f"Error getting approval: {e}")
        return None


async def get_document_content(document_id: str) -> Dict[str, Any]:
    """
    Get the extracted content of a document.
    
    Returns:
        - raw_text: The OCR-extracted text
        - extracted_fields: Structured fields (vendor, amount, date, etc.)
        - line_items: Line items if available
        - ocr_confidence: Confidence score
    
    This tool allows the Copilot to read document content for analysis
    without accessing the file system directly.
    """
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            # First check extracted_invoices table
            invoice = await conn.fetchrow(
                """
                SELECT 
                    id, vendor_name, vendor_tax_id, invoice_number, invoice_date,
                    total_amount, tax_amount, currency, line_items, raw_text,
                    ocr_confidence, ai_confidence
                FROM extracted_invoices 
                WHERE document_id = $1 OR job_id = $1
                ORDER BY created_at DESC 
                LIMIT 1
                """,
                document_id
            )
            
            if invoice:
                return {
                    "document_id": document_id,
                    "found": True,
                    "source": "extracted_invoices",
                    "raw_text": invoice.get("raw_text") or "",
                    "extracted_fields": {
                        "vendor_name": invoice.get("vendor_name"),
                        "vendor_tax_id": invoice.get("vendor_tax_id"),
                        "invoice_number": invoice.get("invoice_number"),
                        "invoice_date": str(invoice.get("invoice_date")) if invoice.get("invoice_date") else None,
                        "total_amount": float(invoice.get("total_amount") or 0),
                        "tax_amount": float(invoice.get("tax_amount") or 0),
                        "currency": invoice.get("currency") or "VND"
                    },
                    "line_items": invoice.get("line_items") or [],
                    "ocr_confidence": float(invoice.get("ocr_confidence") or 0),
                    "ai_confidence": float(invoice.get("ai_confidence") or 0)
                }
            
            # Fallback to documents table
            doc = await conn.fetchrow(
                """
                SELECT id, raw_text, extracted_data, doc_type, doc_type_confidence
                FROM documents
                WHERE id = $1 OR job_id = $1
                LIMIT 1
                """,
                document_id
            )
            
            if doc:
                extracted = doc.get("extracted_data") or {}
                return {
                    "document_id": document_id,
                    "found": True,
                    "source": "documents",
                    "raw_text": doc.get("raw_text") or "",
                    "extracted_fields": extracted,
                    "doc_type": doc.get("doc_type"),
                    "doc_type_confidence": float(doc.get("doc_type_confidence") or 0)
                }
            
            return {
                "document_id": document_id,
                "found": False,
                "error": "Document not found"
            }
            
    except Exception as e:
        logger.error(f"Error getting document content: {e}")
        return {
            "document_id": document_id,
            "found": False,
            "error": str(e)
        }


async def search_documents(
    query: str,
    doc_type: Optional[str] = None,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    Search documents by vendor name, invoice number, or other fields.
    
    Args:
        query: Search term (matches vendor_name, invoice_number)
        doc_type: Optional filter by document type
        limit: Max results to return
    
    Returns:
        List of matching documents with basic info
    """
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            # Build search query
            search_pattern = f"%{query}%"
            
            if doc_type:
                rows = await conn.fetch(
                    """
                    SELECT 
                        ei.id, ei.document_id, ei.vendor_name, ei.invoice_number,
                        ei.invoice_date, ei.total_amount, ei.currency,
                        d.doc_type, d.filename
                    FROM extracted_invoices ei
                    LEFT JOIN documents d ON ei.document_id = d.id
                    WHERE (ei.vendor_name ILIKE $1 OR ei.invoice_number ILIKE $1)
                    AND d.doc_type = $2
                    ORDER BY ei.created_at DESC
                    LIMIT $3
                    """,
                    search_pattern, doc_type, limit
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT 
                        ei.id, ei.document_id, ei.vendor_name, ei.invoice_number,
                        ei.invoice_date, ei.total_amount, ei.currency,
                        d.doc_type, d.filename
                    FROM extracted_invoices ei
                    LEFT JOIN documents d ON ei.document_id = d.id
                    WHERE ei.vendor_name ILIKE $1 OR ei.invoice_number ILIKE $1
                    ORDER BY ei.created_at DESC
                    LIMIT $2
                    """,
                    search_pattern, limit
                )
            
            results = []
            for row in rows:
                results.append({
                    "id": str(row.get("id")),
                    "document_id": str(row.get("document_id")) if row.get("document_id") else None,
                    "vendor_name": row.get("vendor_name"),
                    "invoice_number": row.get("invoice_number"),
                    "invoice_date": str(row.get("invoice_date")) if row.get("invoice_date") else None,
                    "total_amount": float(row.get("total_amount") or 0),
                    "currency": row.get("currency") or "VND",
                    "doc_type": row.get("doc_type"),
                    "filename": row.get("filename")
                })
            
            return results
            
    except Exception as e:
        logger.error(f"Error searching documents: {e}")
        return []


async def get_document_ocr_boxes(document_id: str) -> Dict[str, Any]:
    """
    Get OCR bounding boxes for a document (for visual overlay).
    
    Returns:
        - boxes: List of bounding boxes with text and confidence
        - page_info: Page dimensions
    """
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            # Check if we have OCR boxes stored
            row = await conn.fetchrow(
                """
                SELECT extracted_data, raw_text
                FROM documents
                WHERE id = $1 OR job_id = $1
                LIMIT 1
                """,
                document_id
            )
            
            if not row:
                return {"document_id": document_id, "found": False}
            
            extracted = row.get("extracted_data") or {}
            boxes = extracted.get("ocr_boxes") or []
            
            return {
                "document_id": document_id,
                "found": True,
                "boxes": boxes,
                "page_info": extracted.get("page_info") or {}
            }
            
    except Exception as e:
        logger.error(f"Error getting OCR boxes: {e}")
        return {"document_id": document_id, "found": False, "error": str(e)}


# =============================================================================
# WRITE TOOLS (Go through Action Proposals - require confirmation)
# =============================================================================

async def propose_approve(
    session_id: str,
    approval_id: str,
    reason: str = "Approved via Copilot"
) -> Dict[str, Any]:
    """
    Propose to approve a document (creates action proposal).
    
    This does NOT directly approve - it creates a proposal that the user
    must confirm through the UI.
    
    Args:
        session_id: Current chat session ID
        approval_id: ID of the approval to approve
        reason: Reason for approval
    
    Returns:
        Action proposal details for UI display
    """
    try:
        # Get approval details for description
        approval = await get_approval(approval_id)
        if not approval:
            return {"error": "Approval not found", "success": False}
        
        description = f"Approve {approval.get('counterparty', 'Unknown')} - {approval.get('amount', 0):,.0f} {approval.get('currency', 'VND')}"
        
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO agent_action_proposals 
                (session_id, action_type, target_entity, target_id, action_params, description, reasoning, status)
                VALUES ($1, 'approve_proposal', 'approval', $2::uuid, $3, $4, $5, 'proposed')
                RETURNING id, action_type, description, status, created_at
                """,
                session_id,
                approval_id,
                {"approval_id": approval_id, "reason": reason},
                description,
                reason
            )
            
            # Log to audit
            await conn.execute(
                """
                INSERT INTO audit_events (entity_type, entity_id, action, actor, details, created_at)
                VALUES ('agent_action', $1, 'proposed', 'copilot', $2, NOW())
                """,
                str(row["id"]),
                {"action": "approve", "approval_id": approval_id}
            )
            
            return {
                "success": True,
                "action_id": str(row["id"]),
                "action_type": "approve_proposal",
                "description": description,
                "status": "proposed",
                "message": "Action proposed. Please confirm in the UI to execute.",
                "requires_confirmation": True
            }
            
    except Exception as e:
        logger.error(f"Error proposing approval: {e}")
        return {"error": str(e), "success": False}


async def propose_reject(
    session_id: str,
    approval_id: str,
    reason: str = "Rejected via Copilot"
) -> Dict[str, Any]:
    """
    Propose to reject a document (creates action proposal).
    
    This does NOT directly reject - it creates a proposal that the user
    must confirm through the UI.
    
    Args:
        session_id: Current chat session ID
        approval_id: ID of the approval to reject
        reason: Reason for rejection
    
    Returns:
        Action proposal details for UI display
    """
    try:
        # Get approval details for description
        approval = await get_approval(approval_id)
        if not approval:
            return {"error": "Approval not found", "success": False}
        
        description = f"Reject {approval.get('counterparty', 'Unknown')} - {approval.get('amount', 0):,.0f} {approval.get('currency', 'VND')}: {reason}"
        
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO agent_action_proposals 
                (session_id, action_type, target_entity, target_id, action_params, description, reasoning, status)
                VALUES ($1, 'reject_proposal', 'approval', $2::uuid, $3, $4, $5, 'proposed')
                RETURNING id, action_type, description, status, created_at
                """,
                session_id,
                approval_id,
                {"approval_id": approval_id, "reason": reason},
                description,
                reason
            )
            
            # Log to audit
            await conn.execute(
                """
                INSERT INTO audit_events (entity_type, entity_id, action, actor, details, created_at)
                VALUES ('agent_action', $1, 'proposed', 'copilot', $2, NOW())
                """,
                str(row["id"]),
                {"action": "reject", "approval_id": approval_id, "reason": reason}
            )
            
            return {
                "success": True,
                "action_id": str(row["id"]),
                "action_type": "reject_proposal",
                "description": description,
                "status": "proposed",
                "message": "Action proposed. Please confirm in the UI to execute.",
                "requires_confirmation": True
            }
            
    except Exception as e:
        logger.error(f"Error proposing rejection: {e}")
        return {"error": str(e), "success": False}


# Legacy functions for backward compatibility (will log warning)
async def approve_proposal(approval_id: str, approver: str = "Copilot", reason: str = "Approved via Copilot") -> Dict[str, Any]:
    """
    DEPRECATED: Use propose_approve() instead.
    Direct approval is disabled for safety - actions must go through proposals.
    """
    logger.warning(f"Direct approve_proposal called for {approval_id} - redirecting to proposal system")
    return {
        "error": "Direct approval disabled. Use Copilot to propose approval, then confirm in UI.",
        "success": False,
        "hint": "Ask the Copilot to propose this approval, then click Confirm in the chat interface."
    }


async def reject_proposal(approval_id: str, approver: str = "Copilot", reason: str = "Rejected via Copilot") -> Dict[str, Any]:
    """
    DEPRECATED: Use propose_reject() instead.
    Direct rejection is disabled for safety - actions must go through proposals.
    """
    logger.warning(f"Direct reject_proposal called for {approval_id} - redirecting to proposal system")
    return {
        "error": "Direct rejection disabled. Use Copilot to propose rejection, then confirm in UI.",
        "success": False,
        "hint": "Ask the Copilot to propose this rejection, then click Confirm in the chat interface."
    }


# =============================================================================
# TOOL REGISTRY (for Copilot agent to discover available tools)
# =============================================================================

COPILOT_TOOLS = {
    # READ tools (safe)
    "list_pending_approvals": {
        "function": list_pending_approvals,
        "description": "List pending journal proposals requiring approval",
        "parameters": {"limit": "int (default 10)"},
        "requires_confirmation": False
    },
    "get_approval_statistics": {
        "function": get_approval_statistics,
        "description": "Get counts of documents by status",
        "parameters": {},
        "requires_confirmation": False
    },
    "get_approval": {
        "function": get_approval,
        "description": "Get single approval by ID with details",
        "parameters": {"approval_id": "str"},
        "requires_confirmation": False
    },
    "get_document_content": {
        "function": get_document_content,
        "description": "Get extracted content of a document (text, fields, line items)",
        "parameters": {"document_id": "str"},
        "requires_confirmation": False
    },
    "get_document_ocr_boxes": {
        "function": get_document_ocr_boxes,
        "description": "Get OCR bounding boxes for visual overlay on document preview",
        "parameters": {"document_id": "str"},
        "requires_confirmation": False
    },
    "search_documents": {
        "function": search_documents,
        "description": "Search documents by vendor name or invoice number",
        "parameters": {"query": "str", "doc_type": "str (optional)", "limit": "int (default 10)"},
        "requires_confirmation": False
    },
    
    # WRITE tools (require confirmation)
    "propose_approve": {
        "function": propose_approve,
        "description": "Propose to approve a document (requires user confirmation)",
        "parameters": {"session_id": "str", "approval_id": "str", "reason": "str"},
        "requires_confirmation": True
    },
    "propose_reject": {
        "function": propose_reject,
        "description": "Propose to reject a document (requires user confirmation)",
        "parameters": {"session_id": "str", "approval_id": "str", "reason": "str"},
        "requires_confirmation": True
    },
}
