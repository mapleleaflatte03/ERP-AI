
import logging
from typing import Any, List, Dict

from src.approval import service as approval_service
from src.db import get_connection, update_job_status
from src.api.main import get_db_connection # Reuse dependency if possible or use src.db

logger = logging.getLogger(__name__)

async def list_pending_approvals(limit: int = 5) -> List[Dict[str, Any]]:
    """List pending approvals calls approval service"""
    conn = await get_connection() # Use src.db directly
    try:
        async with conn:
             return await approval_service.list_pending_approvals(conn, limit=limit)
    except Exception as e:
        logger.error(f"Error listing approvals: {e}")
        return []

async def approve_proposal(proposal_id: str, reason: str = "Approved via Copilot") -> Dict[str, Any]:
    """Approve a journal proposal (Write Operation)"""
    conn = await get_connection()
    try:
        async with conn:
            # Reusing approval service logic requires more than just calling it? 
            # service.py has update_approval_status
            # Let's check approval/service.py again
            # actually we used 'POST /v1/approvals/{id}/{action}' logic in main.py
            # logic: update approvals table, if all approved -> post ledger?
            pass 
            # Placeholder, will implement after checking service.py
    except Exception as e:
        logger.error(f"Error approving: {e}")
        return {"error": str(e)}

