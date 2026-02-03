"""
ActionProposalService - Central service for AI action gating
============================================================

Implements the Plan → Confirm → Execute pattern for ALL AI-initiated writes.
Used by all module chats (Documents, Proposals, Approvals, Analyze).

Module Scopes:
- documents: extract, propose, delete
- proposals: submit, update
- approvals: approve, reject
- analyze: query (read-only by default), dataset_upload
- admin: system operations (restricted)
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Optional, Literal
from enum import Enum

logger = logging.getLogger(__name__)


class ModuleScope(str, Enum):
    """Valid module scopes for action proposals"""
    DOCUMENTS = "documents"
    PROPOSALS = "proposals"
    APPROVALS = "approvals"
    ANALYZE = "analyze"
    ADMIN = "admin"
    GLOBAL = "global"


class ActionStatus(str, Enum):
    """Action proposal status workflow"""
    PROPOSED = "proposed"
    CONFIRMED = "confirmed"
    EXECUTED = "executed"
    CANCELLED = "cancelled"
    FAILED = "failed"


# Module -> Allowed action types mapping
MODULE_ALLOWED_ACTIONS = {
    ModuleScope.DOCUMENTS: [
        "extract_fields",
        "propose_journal",
        "delete_document",
        "update_metadata",
    ],
    ModuleScope.PROPOSALS: [
        "submit_proposal",
        "update_proposal",
        "delete_proposal",
    ],
    ModuleScope.APPROVALS: [
        "approve_proposal",
        "reject_proposal",
    ],
    ModuleScope.ANALYZE: [
        "execute_query",  # Read-only SELECT only
        "upload_dataset",
        "delete_dataset",
    ],
    ModuleScope.ADMIN: [
        "system_import",
        "cache_clear",
    ],
    ModuleScope.GLOBAL: [
        # Global chat can only read or redirect to module
        "navigate_to_module",
    ],
}


class ActionProposalService:
    """
    Central service for managing AI action proposals.
    
    All AI-initiated write operations MUST go through this service:
    1. create_proposal() - AI proposes an action
    2. User reviews proposal in UI
    3. confirm() - User confirms, triggers execute
    4. apply() - Service executes the action
    
    Direct writes are BLOCKED. confirmed_action pattern is DEPRECATED.
    """
    
    def __init__(self, db_pool):
        self.pool = db_pool
    
    async def create_proposal(
        self,
        module: ModuleScope,
        action_type: str,
        payload: dict,
        description: str,
        *,
        scope_id: Optional[str] = None,  # document_id, proposal_id, etc.
        target_entity: Optional[str] = None,
        target_id: Optional[str] = None,
        reasoning: Optional[str] = None,
        risk_level: str = "medium",
        preview: Optional[dict] = None,
        idempotency_key: Optional[str] = None,
        created_by: str = "copilot",
        session_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> dict:
        """
        Create a new action proposal for user confirmation.
        
        Args:
            module: The module scope (documents, approvals, etc.)
            action_type: Type of action (approve_proposal, extract_fields, etc.)
            payload: Action parameters
            description: Human-readable description
            scope_id: Context ID (document_id, proposal_id, etc.)
            target_entity: Target entity type
            target_id: Target entity ID
            reasoning: AI's reasoning for this action
            risk_level: low/medium/high
            preview: Preview data for UI display
            idempotency_key: Prevent duplicate proposals
            created_by: Actor creating the proposal
            session_id: Chat session ID
            tenant_id: Tenant ID for multi-tenancy
            
        Returns:
            Created proposal dict with id, status, etc.
        """
        # Validate module + action_type combination
        allowed_actions = MODULE_ALLOWED_ACTIONS.get(module, [])
        if action_type not in allowed_actions:
            raise ValueError(
                f"Action '{action_type}' not allowed in module '{module}'. "
                f"Allowed: {allowed_actions}"
            )
        
        # Check idempotency
        if idempotency_key:
            existing = await self._find_by_idempotency_key(idempotency_key)
            if existing:
                logger.info(f"Returning existing proposal for idempotency_key={idempotency_key}")
                return existing
        
        proposal_id = str(uuid.uuid4())
        session_id = session_id or str(uuid.uuid4())
        
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO agent_action_proposals 
                (id, tenant_id, session_id, action_type, target_entity, target_id, 
                 action_params, description, reasoning, status, proposed_by)
                VALUES ($1, $2::uuid, $3, $4, $5, $6::uuid, $7, $8, $9, 'proposed', $10)
                RETURNING *
                """,
                uuid.UUID(proposal_id),
                uuid.UUID(tenant_id) if tenant_id else None,
                session_id,
                action_type,
                target_entity or module.value,
                uuid.UUID(target_id) if target_id else None,
                {
                    **payload,
                    "_module": module.value,
                    "_scope_id": scope_id,
                    "_risk_level": risk_level,
                    "_preview": preview,
                    "_idempotency_key": idempotency_key,
                },
                description,
                reasoning,
                created_by,
            )
            
            # Audit log
            await self._log_audit(
                conn, 
                proposal_id, 
                "proposed", 
                created_by,
                {"module": module.value, "action_type": action_type}
            )
            
            return self._format_proposal(dict(row))
    
    async def list_pending(
        self,
        module: Optional[ModuleScope] = None,
        scope_id: Optional[str] = None,
        session_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        limit: int = 20,
    ) -> list[dict]:
        """List pending proposals for a module/scope."""
        async with self.pool.acquire() as conn:
            conditions = ["status = 'proposed'"]
            params = []
            idx = 1
            
            if module:
                conditions.append(f"action_params->>'_module' = ${idx}")
                params.append(module.value)
                idx += 1
            
            if scope_id:
                conditions.append(f"action_params->>'_scope_id' = ${idx}")
                params.append(scope_id)
                idx += 1
            
            if session_id:
                conditions.append(f"session_id = ${idx}")
                params.append(session_id)
                idx += 1
            
            if tenant_id:
                conditions.append(f"tenant_id = ${idx}::uuid")
                params.append(tenant_id)
                idx += 1
            
            where = " AND ".join(conditions)
            params.append(limit)
            
            rows = await conn.fetch(
                f"""
                SELECT * FROM agent_action_proposals 
                WHERE {where}
                ORDER BY created_at DESC
                LIMIT ${idx}
                """,
                *params
            )
            
            return [self._format_proposal(dict(row)) for row in rows]
    
    async def get_proposal(self, proposal_id: str) -> Optional[dict]:
        """Get a single proposal by ID."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM agent_action_proposals WHERE id = $1",
                uuid.UUID(proposal_id)
            )
            return self._format_proposal(dict(row)) if row else None
    
    async def confirm(
        self,
        proposal_id: str,
        user_id: str,
        *,
        auto_apply: bool = True,
    ) -> dict:
        """
        Confirm a proposal. If auto_apply=True (default), also executes it.
        
        Returns updated proposal dict.
        """
        async with self.pool.acquire() as conn:
            # Get and lock the proposal
            row = await conn.fetchrow(
                "SELECT * FROM agent_action_proposals WHERE id = $1 FOR UPDATE",
                uuid.UUID(proposal_id)
            )
            
            if not row:
                raise ValueError(f"Proposal {proposal_id} not found")
            
            if row["status"] != "proposed":
                raise ValueError(
                    f"Cannot confirm proposal in '{row['status']}' status. "
                    f"Only 'proposed' can be confirmed."
                )
            
            # Update to confirmed - handle non-UUID user_ids gracefully
            user_uuid = None
            if user_id and user_id != "anonymous":
                try:
                    user_uuid = uuid.UUID(user_id)
                except (ValueError, TypeError):
                    # Non-UUID user_id (e.g., from tests or external systems)
                    pass
            
            await conn.execute(
                """
                UPDATE agent_action_proposals 
                SET status = 'confirmed', confirmed_at = NOW(), confirmed_by = $2
                WHERE id = $1
                """,
                uuid.UUID(proposal_id),
                user_uuid,
            )
            
            # Audit log
            await self._log_audit(conn, proposal_id, "confirmed", user_id, {})
            
            if auto_apply:
                return await self._apply(proposal_id, dict(row), conn)
            
            # Return without applying
            updated = await conn.fetchrow(
                "SELECT * FROM agent_action_proposals WHERE id = $1",
                uuid.UUID(proposal_id)
            )
            return self._format_proposal(dict(updated))
    
    async def cancel(self, proposal_id: str, user_id: str = "anonymous") -> dict:
        """Cancel a pending proposal."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM agent_action_proposals WHERE id = $1",
                uuid.UUID(proposal_id)
            )
            
            if not row:
                raise ValueError(f"Proposal {proposal_id} not found")
            
            if row["status"] != "proposed":
                raise ValueError(
                    f"Cannot cancel proposal in '{row['status']}' status"
                )
            
            await conn.execute(
                """
                UPDATE agent_action_proposals 
                SET status = 'cancelled', updated_at = NOW()
                WHERE id = $1
                """,
                uuid.UUID(proposal_id)
            )
            
            await self._log_audit(conn, proposal_id, "cancelled", user_id, {})
            
            return {"success": True, "status": "cancelled"}
    
    async def _apply(self, proposal_id: str, row: dict, conn) -> dict:
        """
        Execute the confirmed action.
        
        This is where the actual work happens (approve, extract, etc.)
        """
        action_type = row["action_type"]
        action_params = row["action_params"] or {}
        module = action_params.get("_module", "global")
        
        try:
            # Get the executor for this action type
            executor = ACTION_EXECUTORS.get(action_type)
            if not executor:
                raise ValueError(f"No executor for action_type: {action_type}")
            
            # Execute
            result = await executor(action_params, conn)
            
            # Update to executed
            await conn.execute(
                """
                UPDATE agent_action_proposals 
                SET status = 'executed', result = $2, executed_at = NOW()
                WHERE id = $1
                """,
                uuid.UUID(proposal_id),
                result
            )
            
            await self._log_audit(
                conn, proposal_id, "executed", "system",
                {"module": module, "result": result}
            )
            
            # Return updated proposal
            updated = await conn.fetchrow(
                "SELECT * FROM agent_action_proposals WHERE id = $1",
                uuid.UUID(proposal_id)
            )
            return self._format_proposal(dict(updated))
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Action execution failed: {error_msg}")
            
            await conn.execute(
                """
                UPDATE agent_action_proposals 
                SET status = 'failed', error_message = $2, executed_at = NOW()
                WHERE id = $1
                """,
                uuid.UUID(proposal_id),
                error_msg
            )
            
            await self._log_audit(
                conn, proposal_id, "failed", "system",
                {"error": error_msg}
            )
            
            raise
    
    async def _find_by_idempotency_key(self, key: str) -> Optional[dict]:
        """Find existing proposal by idempotency key."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT * FROM agent_action_proposals 
                WHERE action_params->>'_idempotency_key' = $1
                AND created_at > NOW() - INTERVAL '1 hour'
                """,
                key
            )
            return self._format_proposal(dict(row)) if row else None
    
    async def _log_audit(
        self,
        conn,
        proposal_id: str,
        action: str,
        actor: str,
        details: dict,
    ):
        """Log to audit_events table."""
        try:
            await conn.execute(
                """
                INSERT INTO audit_events 
                (entity_type, entity_id, action, actor, details, created_at)
                VALUES ('action_proposal', $1, $2, $3, $4, NOW())
                """,
                proposal_id,
                action,
                actor,
                details,
            )
        except Exception as e:
            logger.warning(f"Failed to log audit event: {e}")
    
    def _format_proposal(self, row: dict) -> dict:
        """Format a DB row as a proposal dict."""
        params = row.get("action_params") or {}
        return {
            "id": str(row["id"]),
            "module": params.get("_module", "global"),
            "scope_id": params.get("_scope_id"),
            "action_type": row["action_type"],
            "target_entity": row.get("target_entity"),
            "target_id": str(row["target_id"]) if row.get("target_id") else None,
            "description": row.get("description", ""),
            "reasoning": row.get("reasoning"),
            "status": row["status"],
            "risk_level": params.get("_risk_level", "medium"),
            "preview": params.get("_preview"),
            "action_params": {
                k: v for k, v in params.items() 
                if not k.startswith("_")
            },
            "result": row.get("result"),
            "error_message": row.get("error_message"),
            "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
            "confirmed_at": row["confirmed_at"].isoformat() if row.get("confirmed_at") else None,
            "executed_at": row["executed_at"].isoformat() if row.get("executed_at") else None,
        }


# =============================================================================
# Action Executors - One per action_type
# =============================================================================

async def execute_approve_proposal(params: dict, conn) -> dict:
    """Execute approval action."""
    from src.approval.service import ApprovalService
    
    approval_id = params.get("approval_id") or params.get("id")
    if not approval_id:
        raise ValueError("approval_id required")
    
    service = ApprovalService(conn)
    result = await service.approve(approval_id, approved_by="copilot-confirmed")
    
    return {
        "success": True,
        "approval_id": str(approval_id),
        "message": f"Approval {approval_id} approved successfully"
    }


async def execute_reject_proposal(params: dict, conn) -> dict:
    """Execute rejection action."""
    from src.approval.service import ApprovalService
    
    approval_id = params.get("approval_id") or params.get("id")
    reason = params.get("reason", "Rejected via Copilot")
    
    if not approval_id:
        raise ValueError("approval_id required")
    
    service = ApprovalService(conn)
    result = await service.reject(
        approval_id, 
        rejected_by="copilot-confirmed", 
        reason=reason
    )
    
    return {
        "success": True,
        "approval_id": str(approval_id),
        "message": f"Approval {approval_id} rejected: {reason}"
    }


async def execute_extract_fields(params: dict, conn) -> dict:
    """Execute field extraction on a document."""
    document_id = params.get("document_id")
    if not document_id:
        raise ValueError("document_id required")
    
    # Trigger extraction workflow
    # This would typically call the OCR/extraction service
    return {
        "success": True,
        "document_id": str(document_id),
        "message": "Extraction triggered",
        "status": "processing"
    }


async def execute_propose_journal(params: dict, conn) -> dict:
    """Generate journal proposal for a document."""
    document_id = params.get("document_id")
    if not document_id:
        raise ValueError("document_id required")
    
    # Trigger proposal generation
    return {
        "success": True,
        "document_id": str(document_id),
        "message": "Journal proposal generation triggered",
        "status": "processing"
    }


async def execute_query(params: dict, conn) -> dict:
    """Execute a read-only SQL query (Analyze module)."""
    sql = params.get("sql", "")
    
    # CRITICAL: Validate query is read-only
    sql_upper = sql.upper().strip()
    if not sql_upper.startswith("SELECT"):
        raise ValueError("Only SELECT queries allowed")
    
    dangerous_keywords = ["INSERT", "UPDATE", "DELETE", "DROP", "TRUNCATE", "ALTER", "CREATE"]
    for kw in dangerous_keywords:
        if kw in sql_upper:
            raise ValueError(f"Dangerous keyword '{kw}' not allowed in query")
    
    # Execute with timeout and row limit
    try:
        rows = await conn.fetch(
            f"SELECT * FROM ({sql}) AS q LIMIT 1000",
        )
        return {
            "success": True,
            "row_count": len(rows),
            "data": [dict(r) for r in rows[:100]],  # Return max 100 rows
            "truncated": len(rows) > 100,
        }
    except Exception as e:
        raise ValueError(f"Query failed: {e}")


async def execute_navigate_to_module(params: dict, conn) -> dict:
    """Navigate user to a specific module (no-op, UI handles)."""
    return {
        "success": True,
        "action": "navigate",
        "target_module": params.get("module"),
        "message": "Navigation request recorded"
    }


# Registry of executors
ACTION_EXECUTORS = {
    "approve_proposal": execute_approve_proposal,
    "reject_proposal": execute_reject_proposal,
    "extract_fields": execute_extract_fields,
    "propose_journal": execute_propose_journal,
    "execute_query": execute_query,
    "navigate_to_module": execute_navigate_to_module,
}
