
import logging
import uuid
from typing import Any, List, Dict

from src.approval import service as approval_service
from src.db import get_connection

logger = logging.getLogger(__name__)

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

async def approve_proposal(approval_id: str, approver: str = "Copilot", reason: str = "Approved via Copilot") -> Dict[str, Any]:
    """Approve a proposal (Action)."""
    try:
        async with get_connection() as conn:
            return await approval_service.approve_proposal(
                conn, 
                approval_id=approval_id, 
                approver=approver, 
                comment=reason
            )
    except Exception as e:
        logger.error(f"Error approving: {e}")
        return {"error": str(e)}

async def reject_proposal(approval_id: str, approver: str = "Copilot", reason: str = "Rejected via Copilot") -> Dict[str, Any]:
    """Reject a proposal (Action)."""
    try:
        async with get_connection() as conn:
            return await approval_service.reject_proposal(
                conn, 
                approval_id=approval_id, 
                approver=approver, 
                comment=reason
            )
    except Exception as e:
        logger.error(f"Error rejecting: {e}")
        return {"error": str(e)}

