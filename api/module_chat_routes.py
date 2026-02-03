"""
Module Chat Routes - Per-Module Chat with Scope Enforcement
==========================================================

Provides chat endpoints for each module with proper scope isolation:
- /v1/chat/documents - Documents module chat
- /v1/chat/proposals - Proposals module chat  
- /v1/chat/approvals - Approvals module chat
- /v1/chat/analyze - Analyze module chat

Each chat is scoped to its module and can only access/propose actions
within that module's boundaries.
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Optional, List
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel

from src.services.action_proposals import (
    ActionProposalService, 
    ModuleScope, 
    MODULE_ALLOWED_ACTIONS
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["Module Chat"])


# =============================================================================
# Request/Response Models
# =============================================================================

class ModuleChatRequest(BaseModel):
    """Request for module-scoped chat"""
    message: str
    scope_id: Optional[str] = None  # document_id, proposal_id, etc.
    session_id: Optional[str] = None
    context: Optional[dict] = None


class ProposedAction(BaseModel):
    """An action proposed by the AI"""
    proposal_id: str
    action_type: str
    description: str
    risk_level: str = "medium"
    preview: Optional[dict] = None
    confirm_url: str


class ModuleChatResponse(BaseModel):
    """Response from module chat"""
    ok: bool = True
    response: str
    proposed_actions: List[ProposedAction] = []
    data: Optional[dict] = None
    trace_id: Optional[str] = None


# =============================================================================
# Helper: Get DB Pool
# =============================================================================

async def get_db_pool():
    """Get database connection pool"""
    try:
        from src.db import get_pool
        return await get_pool()
    except Exception as e:
        logger.error(f"Failed to get DB pool: {e}")
        return None


# =============================================================================
# Module-Specific Tool Definitions
# =============================================================================

DOCUMENTS_TOOLS = """
Available tools for Documents module:
1. list_documents(limit): List recent documents
2. get_document(id): Get document details
3. extract_fields(document_id): Extract fields from document (WRITE - requires confirmation)
4. propose_journal(document_id): Generate journal proposal (WRITE - requires confirmation)
"""

PROPOSALS_TOOLS = """
Available tools for Proposals module:
1. list_proposals(limit, status): List proposals
2. get_proposal(id): Get proposal details
3. submit_proposal(proposal_id): Submit for approval (WRITE - requires confirmation)
"""

APPROVALS_TOOLS = """
Available tools for Approvals module:
1. list_pending_approvals(limit): List pending approvals
2. get_approval(id): Get approval details
3. get_approval_statistics(): Get statistics
4. approve_proposal(approval_id): Approve (WRITE - requires confirmation)
5. reject_proposal(approval_id, reason): Reject (WRITE - requires confirmation)
"""

ANALYZE_TOOLS = """
Available tools for Analyze module:
1. list_datasets(): List available datasets
2. get_dataset_schema(dataset_id): Get dataset columns/types
3. execute_query(sql): Execute READ-ONLY SQL query (SELECT only, WRITE requires confirmation)
4. get_kpis(): Get KPI summary
"""


# =============================================================================
# Documents Module Chat
# =============================================================================

@router.post("/documents", response_model=ModuleChatResponse)
async def chat_documents(request: ModuleChatRequest):
    """
    Chat for Documents module.
    
    Scope: Can read documents, extract fields, generate proposals.
    Write actions (extract, propose) require confirmation.
    """
    trace_id = str(uuid.uuid4())[:8]
    
    try:
        from src.llm.client import LLMClient
        
        pool = await get_db_pool()
        if not pool:
            raise HTTPException(status_code=503, detail="Database unavailable")
        
        service = ActionProposalService(pool)
        client = LLMClient()
        
        # Build context-aware prompt
        system_prompt = f"""You are the ERPX Documents Assistant.
        
{DOCUMENTS_TOOLS}

RULES:
- Only respond about documents and document processing
- For write actions (extract, propose), return a tool call - do NOT execute directly
- Always respond in Vietnamese
- If user asks about approvals/proposals, redirect them to those modules

Scope ID: {request.scope_id or 'global'}

OUTPUT FORMAT (JSON):
{{
    "thought": "Your reasoning",
    "tool": "tool_name or null",
    "params": {{}},
    "response": "Text response to user"
}}
"""
        
        decision = await client.generate_json(
            prompt=request.message,
            system=system_prompt,
            temperature=0.1
        )
        
        tool = decision.get("tool")
        params = decision.get("params", {})
        response_text = decision.get("response", "")
        proposed_actions = []
        
        # Handle write tools - create proposals
        if tool in ["extract_fields", "propose_journal"]:
            doc_id = params.get("document_id") or request.scope_id
            if not doc_id:
                return ModuleChatResponse(
                    response="Tôi cần Document ID để thực hiện. Bạn đang xem tài liệu nào?",
                    trace_id=trace_id
                )
            
            proposal = await service.create_proposal(
                module=ModuleScope.DOCUMENTS,
                action_type=tool,
                payload={"document_id": doc_id},
                description=f"{'Trích xuất thông tin' if tool == 'extract_fields' else 'Tạo đề xuất hạch toán'} cho tài liệu",
                scope_id=doc_id,
                target_entity="document",
                target_id=doc_id,
                session_id=request.session_id,
            )
            
            proposed_actions.append(ProposedAction(
                proposal_id=proposal["id"],
                action_type=tool,
                description=proposal["description"],
                risk_level=proposal["risk_level"],
                confirm_url=f"/v1/agent/actions/{proposal['id']}/confirm"
            ))
            
            response_text = f"Tôi đã tạo đề xuất: {proposal['description']}. Vui lòng xác nhận để thực hiện."
        
        # Handle read tools
        elif tool == "list_documents":
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT id, file_name, status, created_at FROM documents ORDER BY created_at DESC LIMIT $1",
                    params.get("limit", 10)
                )
                response_text = "**Danh sách tài liệu gần đây:**\n"
                for r in rows:
                    response_text += f"- 📄 {r['file_name']} ({r['status']}) - ID: `{str(r['id'])[:8]}`\n"
        
        elif tool == "get_document":
            doc_id = params.get("id") or request.scope_id
            if doc_id:
                async with pool.acquire() as conn:
                    row = await conn.fetchrow(
                        "SELECT * FROM documents WHERE id = $1",
                        uuid.UUID(doc_id)
                    )
                    if row:
                        response_text = f"**Tài liệu:** {row['file_name']}\n- Trạng thái: {row['status']}\n- Tạo: {row['created_at']}"
                    else:
                        response_text = "Không tìm thấy tài liệu."
        
        return ModuleChatResponse(
            response=response_text or decision.get("thought", "Tôi có thể giúp gì về tài liệu?"),
            proposed_actions=proposed_actions,
            trace_id=trace_id
        )
        
    except Exception as e:
        logger.error(f"Documents chat error: {e}")
        return ModuleChatResponse(
            ok=False,
            response=f"Lỗi hệ thống: {str(e)}",
            trace_id=trace_id
        )


# =============================================================================
# Approvals Module Chat
# =============================================================================

@router.post("/approvals", response_model=ModuleChatResponse)
async def chat_approvals(request: ModuleChatRequest):
    """
    Chat for Approvals module.
    
    Scope: Can read approvals, approve/reject (with confirmation).
    """
    trace_id = str(uuid.uuid4())[:8]
    
    try:
        from src.llm.client import LLMClient
        from src.copilot import tools
        
        pool = await get_db_pool()
        if not pool:
            raise HTTPException(status_code=503, detail="Database unavailable")
        
        service = ActionProposalService(pool)
        client = LLMClient()
        
        system_prompt = f"""You are the ERPX Approvals Assistant.

{APPROVALS_TOOLS}

RULES:
- Only respond about approvals and the approval workflow
- For approve/reject actions, return a tool call - NEVER execute directly
- Always respond in Vietnamese
- If scope_id is provided, focus on that specific approval

Scope ID: {request.scope_id or 'global'}

OUTPUT FORMAT (JSON):
{{
    "thought": "Your reasoning",
    "tool": "tool_name or null", 
    "params": {{}},
    "response": "Text response to user"
}}
"""
        
        decision = await client.generate_json(
            prompt=request.message,
            system=system_prompt,
            temperature=0.1
        )
        
        tool = decision.get("tool")
        params = decision.get("params", {})
        response_text = decision.get("response", "")
        proposed_actions = []
        
        # Write tools - create proposals
        if tool in ["approve_proposal", "reject_proposal"]:
            approval_id = params.get("approval_id") or params.get("id") or request.scope_id
            if not approval_id:
                return ModuleChatResponse(
                    response="Tôi cần Approval ID để thực hiện. Bạn đang xem phiếu duyệt nào?",
                    trace_id=trace_id
                )
            
            label = "Duyệt" if tool == "approve_proposal" else "Từ chối"
            reason = params.get("reason", "Via AI Assistant")
            
            proposal = await service.create_proposal(
                module=ModuleScope.APPROVALS,
                action_type=tool,
                payload={
                    "approval_id": approval_id,
                    "reason": reason if tool == "reject_proposal" else None
                },
                description=f"{label} phiếu duyệt {approval_id[:8]}...",
                scope_id=approval_id,
                target_entity="approval",
                target_id=approval_id,
                risk_level="medium" if tool == "approve_proposal" else "low",
                session_id=request.session_id,
            )
            
            proposed_actions.append(ProposedAction(
                proposal_id=proposal["id"],
                action_type=tool,
                description=proposal["description"],
                risk_level=proposal["risk_level"],
                confirm_url=f"/v1/agent/actions/{proposal['id']}/confirm"
            ))
            
            response_text = f"Tôi đã tạo đề xuất: {proposal['description']}. Vui lòng xác nhận."
        
        # Read tools
        elif tool == "list_pending_approvals":
            rows = await tools.list_pending_approvals(limit=params.get("limit", 10))
            if not rows:
                response_text = "Hiện không có chứng từ nào chờ duyệt."
            else:
                response_text = "**Danh sách chờ duyệt:**\n"
                for r in rows:
                    response_text += f"- 📄 {r.get('doc_name', 'Tài liệu')} - {r.get('amount', 0):,.0f} VND (ID: `{r['id'][:8]}`)\n"
        
        elif tool == "get_approval_statistics":
            stats = await tools.get_approval_statistics()
            response_text = f"**Thống kê:**\n- Chờ duyệt: {stats.get('pending', 0)}\n- Đã duyệt: {stats.get('approved', 0)}\n- Từ chối: {stats.get('rejected', 0)}"
        
        return ModuleChatResponse(
            response=response_text or decision.get("thought", "Tôi có thể giúp gì về duyệt chứng từ?"),
            proposed_actions=proposed_actions,
            trace_id=trace_id
        )
        
    except Exception as e:
        logger.error(f"Approvals chat error: {e}")
        return ModuleChatResponse(
            ok=False,
            response=f"Lỗi hệ thống: {str(e)}",
            trace_id=trace_id
        )


# =============================================================================
# Proposals Module Chat
# =============================================================================

@router.post("/proposals", response_model=ModuleChatResponse)
async def chat_proposals(request: ModuleChatRequest):
    """Chat for Proposals module."""
    trace_id = str(uuid.uuid4())[:8]
    
    try:
        from src.llm.client import LLMClient
        
        pool = await get_db_pool()
        if not pool:
            raise HTTPException(status_code=503, detail="Database unavailable")
        
        client = LLMClient()
        
        system_prompt = f"""You are the ERPX Proposals Assistant.

{PROPOSALS_TOOLS}

RULES:
- Only respond about journal proposals
- Always respond in Vietnamese

Scope ID: {request.scope_id or 'global'}

OUTPUT FORMAT (JSON):
{{
    "thought": "Your reasoning",
    "tool": "tool_name or null",
    "params": {{}},
    "response": "Text response to user"
}}
"""
        
        decision = await client.generate_json(
            prompt=request.message,
            system=system_prompt,
            temperature=0.1
        )
        
        tool = decision.get("tool")
        params = decision.get("params", {})
        response_text = decision.get("response", "")
        
        if tool == "list_proposals":
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT jp.id, jp.status, jp.total_debit, jp.created_at, d.file_name
                    FROM journal_proposals jp
                    LEFT JOIN documents d ON d.id = jp.document_id
                    ORDER BY jp.created_at DESC
                    LIMIT $1
                    """,
                    params.get("limit", 10)
                )
                response_text = "**Đề xuất hạch toán gần đây:**\n"
                for r in rows:
                    response_text += f"- 📋 {r['file_name'] or 'Proposal'} - {r['total_debit']:,.0f} VND ({r['status']})\n"
        
        return ModuleChatResponse(
            response=response_text or decision.get("thought", "Tôi có thể giúp gì về đề xuất hạch toán?"),
            trace_id=trace_id
        )
        
    except Exception as e:
        logger.error(f"Proposals chat error: {e}")
        return ModuleChatResponse(
            ok=False,
            response=f"Lỗi hệ thống: {str(e)}",
            trace_id=trace_id
        )


# =============================================================================
# Analyze Module Chat
# =============================================================================

@router.post("/analyze", response_model=ModuleChatResponse)
async def chat_analyze(request: ModuleChatRequest):
    """
    Chat for Analyze module.
    
    Scope: Read-only queries by default. SQL is validated for SELECT only.
    """
    trace_id = str(uuid.uuid4())[:8]
    
    try:
        from src.llm.client import LLMClient
        
        pool = await get_db_pool()
        if not pool:
            raise HTTPException(status_code=503, detail="Database unavailable")
        
        service = ActionProposalService(pool)
        client = LLMClient()
        
        system_prompt = f"""You are the ERPX Analytics Assistant.

{ANALYZE_TOOLS}

RULES:
- Only respond about data analysis and reporting
- SQL queries MUST be SELECT only - no INSERT/UPDATE/DELETE/DROP
- Always respond in Vietnamese
- Limit query results to avoid performance issues

Dataset ID: {request.scope_id or 'default'}

OUTPUT FORMAT (JSON):
{{
    "thought": "Your reasoning",
    "tool": "tool_name or null",
    "params": {{"sql": "SELECT ..."}},
    "response": "Text response to user"
}}
"""
        
        decision = await client.generate_json(
            prompt=request.message,
            system=system_prompt,
            temperature=0.1
        )
        
        tool = decision.get("tool")
        params = decision.get("params", {})
        response_text = decision.get("response", "")
        proposed_actions = []
        
        if tool == "execute_query":
            sql = params.get("sql", "")
            
            # CRITICAL: Validate SELECT only
            sql_upper = sql.upper().strip()
            if not sql_upper.startswith("SELECT"):
                return ModuleChatResponse(
                    ok=False,
                    response="⚠️ Chỉ cho phép truy vấn SELECT. Không thể thực hiện INSERT/UPDATE/DELETE.",
                    trace_id=trace_id
                )
            
            dangerous = ["INSERT", "UPDATE", "DELETE", "DROP", "TRUNCATE", "ALTER", "CREATE"]
            for kw in dangerous:
                if kw in sql_upper:
                    return ModuleChatResponse(
                        ok=False,
                        response=f"⚠️ Từ khóa '{kw}' không được phép trong truy vấn phân tích.",
                        trace_id=trace_id
                    )
            
            # Execute with limits
            try:
                async with pool.acquire() as conn:
                    rows = await conn.fetch(f"SELECT * FROM ({sql}) AS q LIMIT 100")
                    
                    if not rows:
                        response_text = "Truy vấn không trả về kết quả."
                    else:
                        response_text = f"**Kết quả ({len(rows)} dòng):**\n```\n"
                        # Format as simple table
                        if rows:
                            cols = list(rows[0].keys())
                            response_text += " | ".join(cols) + "\n"
                            response_text += "-" * 50 + "\n"
                            for r in rows[:10]:
                                response_text += " | ".join(str(r[c])[:20] for c in cols) + "\n"
                            if len(rows) > 10:
                                response_text += f"... và {len(rows) - 10} dòng nữa\n"
                        response_text += "```"
            except Exception as e:
                response_text = f"⚠️ Lỗi truy vấn: {str(e)}"
        
        elif tool == "list_datasets":
            async with pool.acquire() as conn:
                rows = await conn.fetch("SELECT id, name, row_count, created_at FROM datasets ORDER BY created_at DESC LIMIT 20")
                response_text = "**Datasets có sẵn:**\n"
                for r in rows:
                    response_text += f"- 📊 {r['name']} ({r['row_count']} rows)\n"
        
        elif tool == "get_kpis":
            async with pool.acquire() as conn:
                # Get basic KPIs
                stats = await conn.fetchrow("""
                    SELECT 
                        COUNT(*) FILTER (WHERE status = 'pending') as pending_approvals,
                        COUNT(*) FILTER (WHERE status = 'approved') as approved,
                        SUM(CASE WHEN status = 'approved' THEN total_debit ELSE 0 END) as total_approved_amount
                    FROM approvals a
                    JOIN journal_proposals jp ON jp.id = a.proposal_id
                """)
                response_text = f"""**KPIs:**
- Chờ duyệt: {stats['pending_approvals'] or 0}
- Đã duyệt: {stats['approved'] or 0}
- Tổng giá trị đã duyệt: {stats['total_approved_amount'] or 0:,.0f} VND"""
        
        return ModuleChatResponse(
            response=response_text or decision.get("thought", "Tôi có thể giúp phân tích dữ liệu gì?"),
            proposed_actions=proposed_actions,
            trace_id=trace_id
        )
        
    except Exception as e:
        logger.error(f"Analyze chat error: {e}")
        return ModuleChatResponse(
            ok=False,
            response=f"Lỗi hệ thống: {str(e)}",
            trace_id=trace_id
        )


# =============================================================================
# Generic Pending Actions Endpoint
# =============================================================================

@router.get("/pending-actions")
async def get_pending_actions(
    module: Optional[str] = Query(None, description="Filter by module"),
    scope_id: Optional[str] = Query(None, description="Filter by scope ID"),
    session_id: Optional[str] = Query(None, description="Filter by session"),
    limit: int = Query(20, ge=1, le=100)
):
    """Get pending action proposals for UI display."""
    pool = await get_db_pool()
    if not pool:
        raise HTTPException(status_code=503, detail="Database unavailable")
    
    service = ActionProposalService(pool)
    
    module_scope = ModuleScope(module) if module else None
    proposals = await service.list_pending(
        module=module_scope,
        scope_id=scope_id,
        session_id=session_id,
        limit=limit
    )
    
    return {
        "ok": True,
        "proposals": proposals,
        "count": len(proposals)
    }
