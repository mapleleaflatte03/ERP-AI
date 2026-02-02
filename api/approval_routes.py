"""
ERPX AI Accounting - Approval Routes
=====================================
Endpoints:
- GET  /approvals - List pending approvals
- GET  /approvals/{approval_id} - Get approval detail
- POST /approvals/{approval_id}/approve - Approve document
- POST /approvals/{approval_id}/reject - Reject document
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from src.db import get_pool as get_db_pool

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/approvals", tags=["Approvals"])


# =============================================================================
# Request/Response Models
# =============================================================================

class ApproveRequest(BaseModel):
    user_id: str
    note: Optional[str] = None


class RejectRequest(BaseModel):
    user_id: str
    reason: str


# =============================================================================
# List Approvals
# =============================================================================

@router.get("")
async def list_approvals(
    request: Request,
    status: Optional[str] = Query(None, description="Filter by status: pending, approved, rejected"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> dict:
    """
    List approvals with optional status filter.
    Returns approvals from approval_inbox view with full context.
    """
    pool = await get_db_pool()
    if not pool:
        raise HTTPException(status_code=503, detail="Database unavailable")

    async with pool.acquire() as conn:
        # Build query based on status filter
        if status:
            query = """
                SELECT 
                    a.id,
                    a.job_id,
                    a.proposal_id,
                    a.tenant_id,
                    COALESCE(a.status, a.action) as status,
                    a.approver_name,
                    a.comment,
                    a.created_at,
                    a.updated_at,
                    j.filename,
                    j.file_path,
                    j.status as job_status,
                    jp.ai_confidence,
                    jp.risk_level,
                    ei.vendor_name,
                    ei.invoice_number,
                    ei.invoice_date,
                    ei.total_amount,
                    ei.currency
                FROM approvals a
                LEFT JOIN jobs j ON a.job_id = j.id
                LEFT JOIN journal_proposals jp ON a.proposal_id = jp.id
                LEFT JOIN extracted_invoices ei ON jp.invoice_id = ei.id
                WHERE COALESCE(a.status, a.action) = $1
                ORDER BY a.created_at DESC
                LIMIT $2 OFFSET $3
            """
            rows = await conn.fetch(query, status, limit, offset)
            
            count_query = """
                SELECT COUNT(*) FROM approvals WHERE COALESCE(status, action) = $1
            """
            total = await conn.fetchval(count_query, status)
        else:
            query = """
                SELECT 
                    a.id,
                    a.job_id,
                    a.proposal_id,
                    a.tenant_id,
                    COALESCE(a.status, a.action) as status,
                    a.approver_name,
                    a.comment,
                    a.created_at,
                    a.updated_at,
                    j.filename,
                    j.file_path,
                    j.status as job_status,
                    jp.ai_confidence,
                    jp.risk_level,
                    ei.vendor_name,
                    ei.invoice_number,
                    ei.invoice_date,
                    ei.total_amount,
                    ei.currency
                FROM approvals a
                LEFT JOIN jobs j ON a.job_id = j.id
                LEFT JOIN journal_proposals jp ON a.proposal_id = jp.id
                LEFT JOIN extracted_invoices ei ON jp.invoice_id = ei.id
                ORDER BY a.created_at DESC
                LIMIT $1 OFFSET $2
            """
            rows = await conn.fetch(query, limit, offset)
            total = await conn.fetchval("SELECT COUNT(*) FROM approvals")

        # Get pending count
        pending_count = await conn.fetchval(
            "SELECT COUNT(*) FROM approvals WHERE COALESCE(status, action) = 'pending'"
        )

        approvals = []
        for row in rows:
            approval = {
                "id": str(row["id"]),
                "job_id": str(row["job_id"]) if row["job_id"] else None,
                "proposal_id": str(row["proposal_id"]) if row["proposal_id"] else None,
                "tenant_id": row.get("tenant_id"),
                "status": row["status"],
                "approver_name": row.get("approver_name"),
                "comment": row.get("comment"),
                "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
                "updated_at": row["updated_at"].isoformat() if row.get("updated_at") else None,
                # Document info
                "filename": row.get("filename"),
                "file_path": row.get("file_path"),
                "job_status": row.get("job_status"),
                # Proposal info
                "ai_confidence": float(row["ai_confidence"]) if row.get("ai_confidence") else None,
                "risk_level": row.get("risk_level"),
                # Invoice info
                "vendor_name": row.get("vendor_name"),
                "invoice_number": row.get("invoice_number"),
                "invoice_date": row["invoice_date"].isoformat() if row.get("invoice_date") else None,
                "total_amount": float(row["total_amount"]) if row.get("total_amount") else None,
                "currency": row.get("currency"),
            }
            approvals.append(approval)

        return {
            "success": True,
            "data": {
                "approvals": approvals,
                "total": total or 0,
                "pending": pending_count or 0,
                "limit": limit,
                "offset": offset,
            }
        }

# ==============================================================================
# Pending Approvals (must be before /{approval_id} to avoid route conflict)
# ==============================================================================

@router.get("/pending")
async def list_pending_approvals(
    limit: int = Query(50, ge=1, le=100),
) -> dict:
    """
    List pending approvals only.
    This route must be BEFORE /{approval_id} to avoid route conflict.
    """
    pool = await get_db_pool()
    if not pool:
        raise HTTPException(status_code=503, detail="Database unavailable")
    
    async with pool.acquire() as conn:
        query = """
            SELECT 
                a.id,
                a.job_id,
                a.proposal_id,
                a.tenant_id,
                COALESCE(a.status, a.action) as status,
                a.approver_name,
                a.created_at,
                j.filename,
                jp.ai_confidence,
                ei.vendor_name,
                ei.invoice_number,
                ei.total_amount,
                ei.currency
            FROM approvals a
            LEFT JOIN jobs j ON a.job_id = j.id
            LEFT JOIN journal_proposals jp ON a.proposal_id = jp.id
            LEFT JOIN extracted_invoices ei ON jp.invoice_id = ei.id
            WHERE COALESCE(a.status, a.action) = 'pending'
            ORDER BY a.created_at DESC
            LIMIT $1
        """
        rows = await conn.fetch(query, limit)
        
        approvals = []
        for row in rows:
            approvals.append({
                "id": str(row["id"]),
                "job_id": str(row["job_id"]) if row["job_id"] else None,
                "proposal_id": str(row["proposal_id"]) if row["proposal_id"] else None,
                "tenant_id": row.get("tenant_id"),
                "status": row["status"],
                "filename": row.get("filename"),
                "vendor_name": row.get("vendor_name"),
                "invoice_number": row.get("invoice_number"),
                "total_amount": float(row["total_amount"]) if row.get("total_amount") else None,
                "currency": row.get("currency"),
                "ai_confidence": float(row["ai_confidence"]) if row.get("ai_confidence") else None,
                "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
            })
        
        return {
            "success": True,
            "data": approvals,
            "count": len(approvals)
        }



# =============================================================================
# Get Single Approval
# =============================================================================

@router.get("/{approval_id}")
async def get_approval(approval_id: str) -> dict:
    """
    Get detailed information about a specific approval.
    """
    pool = await get_db_pool()
    if not pool:
        raise HTTPException(status_code=503, detail="Database unavailable")

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT 
                a.*,
                j.filename,
                j.file_path,
                j.status as job_status,
                jp.ai_confidence,
                jp.ai_model,
                jp.ai_reasoning,
                jp.risk_level,
                ei.vendor_name,
                ei.invoice_number,
                ei.invoice_date,
                ei.total_amount,
                ei.currency,
                ei.line_items
            FROM approvals a
            LEFT JOIN jobs j ON a.job_id = j.id
            LEFT JOIN journal_proposals jp ON a.proposal_id = jp.id
            LEFT JOIN extracted_invoices ei ON jp.invoice_id = ei.id
            WHERE a.id = $1
            """,
            approval_id
        )

        if not row:
            raise HTTPException(status_code=404, detail="Approval not found")

        return {
            "success": True,
            "data": {
                "id": str(row["id"]),
                "job_id": str(row["job_id"]) if row["job_id"] else None,
                "proposal_id": str(row["proposal_id"]) if row["proposal_id"] else None,
                "status": row.get("status") or row.get("action"),
                "approver_name": row.get("approver_name"),
                "comment": row.get("comment"),
                "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
                "updated_at": row["updated_at"].isoformat() if row.get("updated_at") else None,
                "document": {
                    "filename": row.get("filename"),
                    "file_path": row.get("file_path"),
                    "status": row.get("job_status"),
                },
                "proposal": {
                    "ai_confidence": float(row["ai_confidence"]) if row.get("ai_confidence") else None,
                    "ai_model": row.get("ai_model"),
                    "ai_reasoning": row.get("ai_reasoning"),
                    "risk_level": row.get("risk_level"),
                },
                "invoice": {
                    "vendor_name": row.get("vendor_name"),
                    "invoice_number": row.get("invoice_number"),
                    "invoice_date": row["invoice_date"].isoformat() if row.get("invoice_date") else None,
                    "total_amount": float(row["total_amount"]) if row.get("total_amount") else None,
                    "currency": row.get("currency"),
                    "line_items": row.get("line_items"),
                },
            }
        }


# =============================================================================
# Approve Document
# =============================================================================

@router.post("/{approval_id}/approve")
async def approve_document(approval_id: str, body: ApproveRequest) -> dict:
    """
    Approve a pending document. Updates approval status and job status.
    """
    pool = await get_db_pool()
    if not pool:
        raise HTTPException(status_code=503, detail="Database unavailable")

    async with pool.acquire() as conn:
        # Check approval exists and is pending
        approval = await conn.fetchrow(
            "SELECT * FROM approvals WHERE id = $1",
            approval_id
        )
        
        if not approval:
            raise HTTPException(status_code=404, detail="Approval not found")
        
        current_status = approval.get("status") or approval.get("action")
        if current_status != "pending":
            raise HTTPException(
                status_code=400, 
                detail=f"Approval is not pending (current status: {current_status})"
            )

        # Update approval
        await conn.execute(
            """
            UPDATE approvals 
            SET status = 'approved', 
                action = 'approved',
                approver_name = $2,
                comment = $3,
                updated_at = NOW()
            WHERE id = $1
            """,
            approval_id,
            body.user_id,
            body.note
        )

        # Update job status
        if approval["job_id"]:
            await conn.execute(
                """
                UPDATE jobs 
                SET status = 'approved', 
                    updated_at = NOW()
                WHERE id = $1
                """,
                approval["job_id"]
            )

        logger.info(f"Approval {approval_id} approved by {body.user_id}")

        return {
            "success": True,
            "message": "Document approved successfully",
            "data": {
                "approval_id": approval_id,
                "status": "approved",
                "approved_by": body.user_id,
                "approved_at": datetime.utcnow().isoformat(),
            }
        }


# =============================================================================
# Reject Document
# =============================================================================

@router.post("/{approval_id}/reject")
async def reject_document(approval_id: str, body: RejectRequest) -> dict:
    """
    Reject a pending document. Updates approval status and job status.
    """
    pool = await get_db_pool()
    if not pool:
        raise HTTPException(status_code=503, detail="Database unavailable")

    async with pool.acquire() as conn:
        # Check approval exists and is pending
        approval = await conn.fetchrow(
            "SELECT * FROM approvals WHERE id = $1",
            approval_id
        )
        
        if not approval:
            raise HTTPException(status_code=404, detail="Approval not found")
        
        current_status = approval.get("status") or approval.get("action")
        if current_status != "pending":
            raise HTTPException(
                status_code=400, 
                detail=f"Approval is not pending (current status: {current_status})"
            )

        # Update approval
        await conn.execute(
            """
            UPDATE approvals 
            SET status = 'rejected', 
                action = 'rejected',
                approver_name = $2,
                comment = $3,
                updated_at = NOW()
            WHERE id = $1
            """,
            approval_id,
            body.user_id,
            body.reason
        )

        # Update job status
        if approval["job_id"]:
            await conn.execute(
                """
                UPDATE jobs 
                SET status = 'rejected', 
                    updated_at = NOW()
                WHERE id = $1
                """,
                approval["job_id"]
            )

        logger.info(f"Approval {approval_id} rejected by {body.user_id}: {body.reason}")

        return {
            "success": True,
            "message": "Document rejected",
            "data": {
                "approval_id": approval_id,
                "status": "rejected",
                "rejected_by": body.user_id,
                "reason": body.reason,
                "rejected_at": datetime.utcnow().isoformat(),
            }
        }
