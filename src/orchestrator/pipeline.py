"""
ERPX AI Accounting - Document Processing Pipeline (LangGraph)
==============================================================
Orchestrates document processing workflow with state machine.
"""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime
from typing import Any, Literal, TypedDict

from src.core import config

# LangGraph imports
try:
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.graph import END, StateGraph

    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    StateGraph = None
    END = None
    MemorySaver = None

logger = logging.getLogger(__name__)

# Semaphores to bound concurrency
_EXTRACT_SEMAPHORE = asyncio.Semaphore(5)  # CPU intensive OCR
_RAG_SEMAPHORE = asyncio.Semaphore(10)  # IO bound but potentially heavy

# =============================================================================
# Pipeline State
# =============================================================================


class PipelineState(TypedDict):
    """State for document processing pipeline"""

    # Input
    job_id: str
    company_id: str
    document_key: str
    document_type: str
    user_id: str

    # Processing stages
    stage: str

    # Extracted data
    extracted_text: str
    key_fields: dict[str, Any]
    tables: list[list[list[str]]]

    # RAG context
    rag_context: str
    rag_sources: list[str]

    # LLM outputs
    journal_proposal: dict[str, Any]
    llm_request_id: str
    llm_latency_ms: float

    # Validation
    validation_result: dict[str, Any]
    opa_decision: dict[str, Any]

    # Final output
    status: str
    error_message: str | None

    # Metadata
    trace_id: str
    timestamps: dict[str, str]


# =============================================================================
# Pipeline Nodes
# =============================================================================


async def node_extract_document(state: PipelineState) -> PipelineState:
    """Extract text and data from document"""
    from src.processing import process_document
    from src.storage import download_document

    logger.info(f"[{state['job_id']}] Extracting document: {state['document_key']}")
    state["stage"] = "extracting"
    state["timestamps"]["extract_start"] = datetime.utcnow().isoformat()

    try:
        # Acquire semaphore to limit concurrent heavy processing
        async with _EXTRACT_SEMAPHORE:
            # Download document from MinIO (Run in thread)
            # Fix: Pass bucket name explicitly
            doc_data = await asyncio.to_thread(download_document, config.MINIO_BUCKET, state["document_key"])

            if doc_data is None:
                state["status"] = "failed"
                state["error_message"] = f"Document not found: {state['document_key']}"
                return state

            # Determine content type from extension
            ext = state["document_key"].lower().split(".")[-1]
            content_type_map = {
                "pdf": "application/pdf",
                "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "xls": "application/vnd.ms-excel",
                "png": "image/png",
                "jpg": "image/jpeg",
                "jpeg": "image/jpeg",
            }
            content_type = content_type_map.get(ext, "application/octet-stream")

            # Process document (Run in thread as it is CPU intensive)
            result = await asyncio.to_thread(process_document, doc_data, content_type, state["document_key"])

        if not result.success:
            state["status"] = "failed"
            state["error_message"] = f"Extraction failed: {result.error_message}"
            return state

        state["extracted_text"] = result.document_text
        state["key_fields"] = result.key_fields
        state["tables"] = result.tables
        state["timestamps"]["extract_end"] = datetime.utcnow().isoformat()

        logger.info(f"[{state['job_id']}] Extraction complete: {len(result.document_text)} chars")
        return state

    except Exception as e:
        logger.error(f"[{state['job_id']}] Extraction error: {e}")
        state["status"] = "failed"
        state["error_message"] = str(e)
        return state


async def node_retrieve_context(state: PipelineState) -> PipelineState:
    """Retrieve relevant context from RAG"""
    from src.rag import format_context_for_llm, search_accounting_context

    logger.info(f"[{state['job_id']}] Retrieving RAG context")
    state["stage"] = "retrieving"
    state["timestamps"]["rag_start"] = datetime.utcnow().isoformat()

    try:
        # Build search query from extracted data
        query_parts = []

        # Add key fields to query
        if state["key_fields"].get("vendor_name"):
            query_parts.append(state["key_fields"]["vendor_name"])
        if state["key_fields"].get("invoice_number"):
            query_parts.append(f"hóa đơn {state['key_fields']['invoice_number']}")

        # Add document type context
        doc_type = state.get("document_type", "invoice")
        if doc_type == "invoice":
            query_parts.append("hạch toán hóa đơn mua hàng")
        elif doc_type == "receipt":
            query_parts.append("hạch toán phiếu thu chi")
        elif doc_type == "payroll":
            query_parts.append("hạch toán lương nhân viên")

        # Add first 200 chars of extracted text
        if state["extracted_text"]:
            query_parts.append(state["extracted_text"][:200])

        search_query = " ".join(query_parts)

        # Search RAG (Run in thread)
        async with _RAG_SEMAPHORE:
            results = await asyncio.to_thread(search_accounting_context, search_query, limit=3)

        # Format for LLM
        state["rag_context"] = format_context_for_llm(results)
        state["rag_sources"] = [r.source for r in results]
        state["timestamps"]["rag_end"] = datetime.utcnow().isoformat()

        logger.info(f"[{state['job_id']}] RAG retrieved {len(results)} sources")
        return state

    except Exception as e:
        logger.warning(f"[{state['job_id']}] RAG retrieval warning: {e}")
        # RAG failure is not fatal - continue without context
        state["rag_context"] = ""
        state["rag_sources"] = []
        state["timestamps"]["rag_end"] = datetime.utcnow().isoformat()
        return state


async def node_generate_proposal(state: PipelineState) -> PipelineState:
    """Generate journal entry proposal using DO Agent LLM"""
    from src.llm import get_llm_client

    logger.info(f"[{state['job_id']}] Generating journal proposal via DO Agent")
    state["stage"] = "generating"
    state["timestamps"]["llm_start"] = datetime.utcnow().isoformat()

    try:
        client = get_llm_client()

        # Build prompt
        system_prompt = """Bạn là chuyên gia kế toán Việt Nam theo Thông tư 200/2014/TT-BTC.
Phân tích chứng từ và đề xuất bút toán kế toán chuẩn.

QUY TẮC:
1. Chỉ dùng tài khoản theo TT200
2. Bút toán PHẢI CÂN ĐỐI: Tổng Nợ = Tổng Có
3. Tách thuế GTGT đầu vào (TK 133)
4. Ghi rõ diễn giải và lý do

OUTPUT JSON:
{
  "invoice_summary": {
    "invoice_number": "...",
    "vendor_name": "...",
    "invoice_date": "...",
    "total_amount": 0,
    "vat_amount": 0,
    "pre_vat_amount": 0
  },
  "journal_entries": [
    {
      "debit_account": "152",
      "debit_account_name": "Nguyên liệu, vật liệu",
      "debit_amount": 0,
      "credit_account": "331",
      "credit_account_name": "Phải trả cho người bán",
      "credit_amount": 0,
      "description": "..."
    }
  ],
  "explanation": "...",
  "confidence": 0.9
}"""

        user_prompt = f"""### CHỨNG TỪ:
{state["extracted_text"][:3000]}

### THÔNG TIN TRÍCH XUẤT:
{json.dumps(state["key_fields"], ensure_ascii=False, indent=2)}

### TÀI LIỆU THAM KHẢO:
{state["rag_context"] or "Thông tư 200/2014/TT-BTC"}

Phân tích và đề xuất bút toán kế toán (JSON)."""

        # Call LLM
        response = await client.generate(
            prompt=user_prompt,
            system=system_prompt,
            json_schema={"type": "object"},
            temperature=0.2,
            max_tokens=2000,
            trace_id=state["trace_id"],
        )

        state["llm_request_id"] = response.request_id
        state["llm_latency_ms"] = response.latency_ms
        state["timestamps"]["llm_end"] = datetime.utcnow().isoformat()

        # Parse JSON response
        content = response.content.strip()

        # Handle markdown code blocks
        if "```json" in content:
            start = content.find("```json") + 7
            end = content.find("```", start)
            if end > start:
                content = content[start:end].strip()
        elif "```" in content:
            start = content.find("```") + 3
            end = content.find("```", start)
            if end > start:
                content = content[start:end].strip()

        proposal = json.loads(content)
        state["journal_proposal"] = proposal

        logger.info(
            f"[{state['job_id']}] Proposal generated: "
            f"latency={response.latency_ms:.0f}ms, "
            f"request_id={response.request_id}"
        )
        return state

    except json.JSONDecodeError as e:
        logger.error(f"[{state['job_id']}] LLM response not valid JSON: {e}")
        state["status"] = "failed"
        state["error_message"] = f"LLM response parsing failed: {e}"
        return state

    except Exception as e:
        logger.error(f"[{state['job_id']}] LLM generation error: {e}")
        state["status"] = "failed"
        state["error_message"] = str(e)
        return state


async def node_validate_policy(state: PipelineState) -> PipelineState:
    """Validate journal proposal against OPA policies"""
    import httpx

    logger.info(f"[{state['job_id']}] Validating against OPA policies")
    state["stage"] = "validating"
    state["timestamps"]["opa_start"] = datetime.utcnow().isoformat()

    opa_url = os.getenv("OPA_URL", "http://localhost:8181")

    try:
        # Build OPA input
        opa_input = {
            "input": {
                "job_id": state["job_id"],
                "company_id": state["company_id"],
                "user_id": state["user_id"],
                "proposal": state["journal_proposal"],
                "key_fields": state["key_fields"],
            }
        }

        # Call OPA
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(f"{opa_url}/v1/data/erpx/journal/validate", json=opa_input)

            if response.status_code == 200:
                result = response.json()
                decision = result.get("result", {})

                state["opa_decision"] = decision
                state["validation_result"] = {
                    "is_valid": decision.get("allow", True),
                    "issues": decision.get("issues", []),
                    "risk_level": decision.get("risk_level", "low"),
                }
            else:
                # OPA not configured - default allow
                logger.warning(f"OPA returned {response.status_code}, defaulting to allow")
                state["opa_decision"] = {"allow": True}
                state["validation_result"] = {
                    "is_valid": True,
                    "issues": [],
                    "risk_level": "low",
                }

        state["timestamps"]["opa_end"] = datetime.utcnow().isoformat()

        # Check if validation passed
        if not state["validation_result"]["is_valid"]:
            logger.warning(f"[{state['job_id']}] OPA validation failed: {state['validation_result']['issues']}")

        return state

    except Exception as e:
        logger.warning(f"[{state['job_id']}] OPA validation error (non-fatal): {e}")
        # OPA failure is not fatal - default allow
        state["opa_decision"] = {"allow": True, "error": str(e)}
        state["validation_result"] = {
            "is_valid": True,
            "issues": [],
            "risk_level": "unknown",
        }
        state["timestamps"]["opa_end"] = datetime.utcnow().isoformat()
        return state


def node_finalize(state: PipelineState) -> PipelineState:
    """Finalize processing and set status"""
    logger.info(f"[{state['job_id']}] Finalizing pipeline")
    state["stage"] = "completed"
    state["timestamps"]["completed"] = datetime.utcnow().isoformat()

    # Check if we have a valid proposal
    if state.get("journal_proposal"):
        if state["validation_result"].get("is_valid", True):
            state["status"] = "pending_approval"
        else:
            state["status"] = "validation_failed"
    else:
        if not state.get("error_message"):
            state["status"] = "failed"
            state["error_message"] = "No journal proposal generated"

    logger.info(f"[{state['job_id']}] Pipeline completed: status={state['status']}")
    return state


def should_continue(state: PipelineState) -> Literal["continue", "end"]:
    """Check if pipeline should continue or end early"""
    if state.get("status") == "failed":
        return "end"
    return "continue"


# =============================================================================
# Pipeline Builder
# =============================================================================


def build_pipeline():
    """Build the document processing pipeline graph"""
    if not LANGGRAPH_AVAILABLE:
        logger.warning("LangGraph not available, using simple sequential pipeline")
        return None

    # Create state graph
    workflow = StateGraph(PipelineState)

    # Add nodes
    workflow.add_node("extract", node_extract_document)
    workflow.add_node("retrieve", node_retrieve_context)
    workflow.add_node("generate", node_generate_proposal)
    workflow.add_node("validate", node_validate_policy)
    workflow.add_node("finalize", node_finalize)

    # Set entry point
    workflow.set_entry_point("extract")

    # Add edges with conditional
    workflow.add_conditional_edges("extract", should_continue, {"continue": "retrieve", "end": "finalize"})

    workflow.add_conditional_edges("retrieve", should_continue, {"continue": "generate", "end": "finalize"})

    workflow.add_conditional_edges("generate", should_continue, {"continue": "validate", "end": "finalize"})

    workflow.add_edge("validate", "finalize")
    workflow.add_edge("finalize", END)

    # Compile with memory checkpoint
    memory = MemorySaver()

    return workflow.compile(checkpointer=memory)


# Singleton pipeline
_pipeline = None


def get_pipeline():
    """Get singleton pipeline"""
    global _pipeline
    if _pipeline is None:
        _pipeline = build_pipeline()
    return _pipeline


# =============================================================================
# Simple Sequential Pipeline (Fallback)
# =============================================================================


async def run_simple_pipeline(state: PipelineState) -> PipelineState:
    """Run pipeline without LangGraph (fallback)"""
    logger.info(f"Running simple sequential pipeline for job {state['job_id']}")

    # Extract
    state = await node_extract_document(state)
    if state.get("status") == "failed":
        return node_finalize(state)

    # Retrieve RAG context
    state = await node_retrieve_context(state)
    if state.get("status") == "failed":
        return node_finalize(state)

    # Generate proposal
    state = await node_generate_proposal(state)
    if state.get("status") == "failed":
        return node_finalize(state)

    # Validate with OPA
    state = await node_validate_policy(state)

    # Finalize
    return node_finalize(state)


# =============================================================================
# Main Entry Point
# =============================================================================


async def process_document_pipeline(
    job_id: str,
    company_id: str,
    document_key: str,
    document_type: str = "invoice",
    user_id: str = "system",
    trace_id: str | None = None,
) -> PipelineState:
    """
    Process a document through the full pipeline.

    Args:
        job_id: Unique job identifier
        company_id: Company ID
        document_key: MinIO object key
        document_type: Type of document (invoice, receipt, payroll)
        user_id: User who uploaded the document
        trace_id: Distributed trace ID

    Returns:
        PipelineState with results
    """
    if not trace_id:
        trace_id = str(uuid.uuid4())

    # Initialize state
    initial_state: PipelineState = {
        "job_id": job_id,
        "company_id": company_id,
        "document_key": document_key,
        "document_type": document_type,
        "user_id": user_id,
        "stage": "initialized",
        "extracted_text": "",
        "key_fields": {},
        "tables": [],
        "rag_context": "",
        "rag_sources": [],
        "journal_proposal": {},
        "llm_request_id": "",
        "llm_latency_ms": 0,
        "validation_result": {},
        "opa_decision": {},
        "status": "processing",
        "error_message": None,
        "trace_id": trace_id,
        "timestamps": {
            "started": datetime.utcnow().isoformat(),
        },
    }

    logger.info(f"Starting pipeline for job {job_id}, trace_id={trace_id}")

    # Run pipeline
    pipeline = get_pipeline()

    if pipeline is not None:
        # Use LangGraph
        config = {"configurable": {"thread_id": job_id}}
        result = await pipeline.ainvoke(initial_state, config)
        return result
    else:
        # Use simple sequential fallback
        return await run_simple_pipeline(initial_state)


__all__ = [
    "PipelineState",
    "process_document_pipeline",
    "build_pipeline",
    "get_pipeline",
]
