"""
ERPX AI Accounting - Agent Action Routes
========================================
Implements Plan → Confirm → Execute pattern for Copilot actions.

Endpoints:
- POST /agent/actions/plan     - Create a new action proposal
- GET  /agent/actions/pending  - List pending proposals for session
- GET  /agent/actions/history  - List action history  
- GET  /agent/actions/{id}     - Get proposal details
- POST /agent/actions/{id}/confirm - Confirm and execute proposal
- POST /agent/actions/{id}/cancel  - Cancel proposal
"""

import logging
import os
import sys
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["Agent"])


# =============================================================================
# Pydantic Models
# =============================================================================

class ActionPlanRequest(BaseModel):
    """Request to create an action proposal"""
    session_id: str
    action_type: str  # 'approve_proposal', 'reject_proposal', etc.
    target_entity: Optional[str] = None  # 'approval', 'document', etc.
    target_id: Optional[str] = None
    action_params: dict = {}
    description: str
    reasoning: Optional[str] = None


class ActionConfirmRequest(BaseModel):
    """Request to confirm an action"""
    user_id: Optional[str] = None  # Will be set from auth in production


class ActionResponse(BaseModel):
    """Response for action operations"""
    id: str
    action_type: str
    target_entity: Optional[str]
    target_id: Optional[str]
    description: str
    reasoning: Optional[str]
    status: str
    action_params: dict
    result: Optional[dict] = None
    error_message: Optional[str] = None
    created_at: str
    confirmed_at: Optional[str] = None
    executed_at: Optional[str] = None


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


def format_action(row: dict) -> ActionResponse:
    """Format a database row as ActionResponse"""
    return ActionResponse(
        id=str(row["id"]),
        action_type=row["action_type"],
        target_entity=row.get("target_entity"),
        target_id=str(row["target_id"]) if row.get("target_id") else None,
        description=row.get("description", ""),
        reasoning=row.get("reasoning"),
        status=row["status"],
        action_params=row.get("action_params") or {},
        result=row.get("result"),
        error_message=row.get("error_message"),
        created_at=row["created_at"].isoformat() if row.get("created_at") else None,
        confirmed_at=row["confirmed_at"].isoformat() if row.get("confirmed_at") else None,
        executed_at=row["executed_at"].isoformat() if row.get("executed_at") else None,
    )


# =============================================================================
# Action Executors - Map action_type to actual function
# =============================================================================

async def execute_approve_proposal(action_params: dict, conn) -> dict:
    """Execute approval action"""
    from src.approval.service import ApprovalService
    
    approval_id = action_params.get("approval_id")
    if not approval_id:
        raise ValueError("approval_id required")
    
    service = ApprovalService(conn)
    result = await service.approve(approval_id, approved_by="copilot-confirmed")
    
    return {
        "success": True,
        "approval_id": approval_id,
        "message": f"Approval {approval_id} approved successfully"
    }


async def execute_reject_proposal(action_params: dict, conn) -> dict:
    """Execute rejection action"""
    from src.approval.service import ApprovalService
    
    approval_id = action_params.get("approval_id")
    reason = action_params.get("reason", "Rejected via Copilot")
    
    if not approval_id:
        raise ValueError("approval_id required")
    
    service = ApprovalService(conn)
    result = await service.reject(approval_id, rejected_by="copilot-confirmed", reason=reason)
    
    return {
        "success": True,
        "approval_id": approval_id,
        "message": f"Approval {approval_id} rejected: {reason}"
    }


# Registry of action executors
ACTION_EXECUTORS = {
    "approve_proposal": execute_approve_proposal,
    "reject_proposal": execute_reject_proposal,
}


# =============================================================================
# Endpoints - SPECIFIC ROUTES FIRST (before parameterized routes)
# =============================================================================

@router.post("/actions/plan")
async def create_action_plan(request: ActionPlanRequest) -> dict:
    """
    Create a new action proposal (Plan phase).
    
    This stores the proposed action for user confirmation.
    Returns the proposal ID and details for UI display.
    """
    pool = await get_db_pool()
    if not pool:
        raise HTTPException(status_code=503, detail="Database unavailable")
    
    async with pool.acquire() as conn:
        # Create proposal record
        row = await conn.fetchrow(
            """
            INSERT INTO agent_action_proposals 
            (session_id, action_type, target_entity, target_id, action_params, description, reasoning, status)
            VALUES ($1, $2, $3, $4::uuid, $5, $6, $7, 'proposed')
            RETURNING *
            """,
            request.session_id,
            request.action_type,
            request.target_entity,
            request.target_id if request.target_id else None,
            request.action_params,
            request.description,
            request.reasoning
        )
        
        # Log to audit_events
        await conn.execute(
            """
            INSERT INTO audit_events (entity_type, entity_id, action, actor, details, created_at)
            VALUES ('agent_action', $1, 'proposed', 'copilot', $2, NOW())
            """,
            str(row["id"]),
            {"action_type": request.action_type, "description": request.description}
        )
        
        return {
            "success": True,
            "proposal": format_action(dict(row)).dict(),
            "message": "Action proposed. Awaiting confirmation."
        }


@router.get("/actions/pending")
async def list_pending_actions(
    session_id: str = Query(..., description="Chat session ID"),
    limit: int = Query(20, ge=1, le=100)
) -> dict:
    """
    List pending action proposals for a session.
    
    Returns proposals that are in 'proposed' status and awaiting confirmation.
    """
    pool = await get_db_pool()
    if not pool:
        raise HTTPException(status_code=503, detail="Database unavailable")
    
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM agent_action_proposals 
            WHERE session_id = $1 AND status = 'proposed'
            ORDER BY created_at DESC
            LIMIT $2
            """,
            session_id,
            limit
        )
        
        proposals = [format_action(dict(row)).dict() for row in rows]
        
        return {
            "success": True,
            "proposals": proposals,
            "count": len(proposals)
        }


@router.get("/actions/history")
async def list_action_history(
    session_id: Optional[str] = Query(None, description="Filter by session ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0)
) -> dict:
    """List action history with optional filters"""
    pool = await get_db_pool()
    if not pool:
        raise HTTPException(status_code=503, detail="Database unavailable")
    
    async with pool.acquire() as conn:
        # Build query
        conditions = []
        params = []
        param_idx = 1
        
        if session_id:
            conditions.append(f"session_id = ${param_idx}")
            params.append(session_id)
            param_idx += 1
        
        if status:
            conditions.append(f"status = ${param_idx}")
            params.append(status)
            param_idx += 1
        
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        
        query = f"""
            SELECT * FROM agent_action_proposals 
            {where_clause}
            ORDER BY created_at DESC
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """
        params.extend([limit, offset])
        
        rows = await conn.fetch(query, *params)
        
        # Get total count
        count_query = f"SELECT COUNT(*) as total FROM agent_action_proposals {where_clause}"
        count_row = await conn.fetchrow(count_query, *params[:-2]) if params[:-2] else await conn.fetchrow(count_query)
        total = count_row["total"] if count_row else 0
        
        proposals = [format_action(dict(row)).dict() for row in rows]
        
        return {
            "success": True,
            "proposals": proposals,
            "total": total,
            "limit": limit,
            "offset": offset
        }


# =============================================================================
# Parameterized routes (MUST come after specific routes)
# =============================================================================

@router.get("/actions/{action_id}")
async def get_action(action_id: str) -> dict:
    """Get details of a specific action proposal"""
    pool = await get_db_pool()
    if not pool:
        raise HTTPException(status_code=503, detail="Database unavailable")
    
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM agent_action_proposals WHERE id = $1",
            action_id
        )
        
        if not row:
            raise HTTPException(status_code=404, detail="Action not found")
        
        return {
            "success": True,
            "proposal": format_action(dict(row)).dict()
        }


@router.post("/actions/{action_id}/confirm")
async def confirm_action(action_id: str, request: ActionConfirmRequest = None) -> dict:
    """
    Confirm and execute an action proposal (Confirm + Execute phases).
    
    This moves the proposal from 'proposed' → 'confirmed' → 'executed' or 'failed'.
    """
    pool = await get_db_pool()
    if not pool:
        raise HTTPException(status_code=503, detail="Database unavailable")
    
    async with pool.acquire() as conn:
        # Get proposal
        row = await conn.fetchrow(
            "SELECT * FROM agent_action_proposals WHERE id = $1",
            action_id
        )
        
        if not row:
            raise HTTPException(status_code=404, detail="Action not found")
        
        if row["status"] != "proposed":
            raise HTTPException(
                status_code=400, 
                detail=f"Cannot confirm action in '{row['status']}' status"
            )
        
        # Update to confirmed
        await conn.execute(
            """
            UPDATE agent_action_proposals 
            SET status = 'confirmed', confirmed_at = NOW(), confirmed_by = $2
            WHERE id = $1
            """,
            action_id,
            request.user_id if request and request.user_id else None
        )
        
        # Execute the action
        action_type = row["action_type"]
        action_params = row["action_params"] or {}
        
        executor = ACTION_EXECUTORS.get(action_type)
        if not executor:
            # Update to failed
            await conn.execute(
                """
                UPDATE agent_action_proposals 
                SET status = 'failed', error_message = $2, executed_at = NOW()
                WHERE id = $1
                """,
                action_id,
                f"Unknown action type: {action_type}"
            )
            raise HTTPException(status_code=400, detail=f"Unknown action type: {action_type}")
        
        try:
            # Execute the action
            result = await executor(action_params, conn)
            
            # Update to executed
            await conn.execute(
                """
                UPDATE agent_action_proposals 
                SET status = 'executed', result = $2, executed_at = NOW()
                WHERE id = $1
                """,
                action_id,
                result
            )
            
            # Log to audit_events
            await conn.execute(
                """
                INSERT INTO audit_events (entity_type, entity_id, action, actor, details, created_at)
                VALUES ('agent_action', $1, 'executed', 'user', $2, NOW())
                """,
                action_id,
                {"action_type": action_type, "result": result}
            )
            
            # Get updated record
            updated_row = await conn.fetchrow(
                "SELECT * FROM agent_action_proposals WHERE id = $1",
                action_id
            )
            
            return {
                "success": True,
                "proposal": format_action(dict(updated_row)).dict(),
                "result": result,
                "message": "Action executed successfully"
            }
            
        except Exception as e:
            # Update to failed
            error_msg = str(e)
            await conn.execute(
                """
                UPDATE agent_action_proposals 
                SET status = 'failed', error_message = $2, executed_at = NOW()
                WHERE id = $1
                """,
                action_id,
                error_msg
            )
            
            logger.error(f"Action execution failed: {error_msg}")
            raise HTTPException(status_code=500, detail=f"Action failed: {error_msg}")


@router.post("/actions/{action_id}/cancel")
async def cancel_action(action_id: str) -> dict:
    """Cancel a proposed action"""
    pool = await get_db_pool()
    if not pool:
        raise HTTPException(status_code=503, detail="Database unavailable")
    
    async with pool.acquire() as conn:
        # Get proposal
        row = await conn.fetchrow(
            "SELECT * FROM agent_action_proposals WHERE id = $1",
            action_id
        )
        
        if not row:
            raise HTTPException(status_code=404, detail="Action not found")
        
        if row["status"] != "proposed":
            raise HTTPException(
                status_code=400, 
                detail=f"Cannot cancel action in '{row['status']}' status"
            )
        
        # Update to cancelled
        await conn.execute(
            """
            UPDATE agent_action_proposals 
            SET status = 'cancelled', updated_at = NOW()
            WHERE id = $1
            """,
            action_id
        )
        
        # Log to audit_events
        await conn.execute(
            """
            INSERT INTO audit_events (entity_type, entity_id, action, actor, details, created_at)
            VALUES ('agent_action', $1, 'cancelled', 'user', $2, NOW())
            """,
            action_id,
            {"action_type": row["action_type"]}
        )
        
        return {
            "success": True,
            "message": "Action cancelled"
        }
