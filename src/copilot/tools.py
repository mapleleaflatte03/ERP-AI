
import logging
import uuid
from typing import Any, List, Dict

from src.approval import service as approval_service
from src.db import get_connection

logger = logging.getLogger(__name__)

async def list_pending_approvals(limit: int = 5) -> List[Dict[str, Any]]:
    """List pending approvals."""
    try:
        async with get_connection() as conn:
             return await approval_service.list_pending_approvals(conn, limit=limit)
    except Exception as e:
        logger.error(f"Error listing approvals: {e}")
        return []

async def get_approval(approval_id: str) -> Dict[str, Any] | None:
    """Get single approval."""
    try:
        async with get_connection() as conn:
             return await approval_service.get_approval_by_id(conn, approval_id)
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
