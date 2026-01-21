"""
ERPX AI - LangGraph Orchestrator
=================================
Main orchestration using LangGraph for document processing pipeline.

Pipeline:
1. Document Upload → Extract Text
2. RAG Retrieval → Get relevant context
3. LLM Classification → Identify document type
4. LLM Extraction → Extract data fields
5. LLM Proposal → Generate journal entries
6. Guardrails Validation → Check compliance
7. Human Review (if needed) → Approve/Reject
8. Commit to Ledger
"""

import json
import logging
import operator
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import Annotated, Any, Dict, List, Optional, TypedDict

# LangGraph imports
try:
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.graph import END, StateGraph

    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    StateGraph = None
    END = "end"

sys.path.insert(0, "/root/erp-ai")

from src.guardrails import GuardrailsEngine, get_guardrails_engine
from src.llm import LLMClient, get_llm_client

logger = logging.getLogger("erpx.orchestrator")


# ===========================================================================
# State Definition
# ===========================================================================


class DocumentState(TypedDict):
    """State for document processing pipeline"""

    # Input
    job_id: str
    file_path: str
    file_info: dict[str, Any]
    tenant_id: str

    # Extracted content
    raw_text: str
    text_chunks: list[str]

    # RAG context
    rag_context: list[dict[str, Any]]
    rag_scores: list[float]

    # Classification result
    doc_type: str
    doc_type_confidence: float

    # Extraction result
    extracted_data: dict[str, Any]

    # Proposal
    proposal: dict[str, Any]

    # Validation
    validation_result: dict[str, Any]

    # Final status
    status: str  # processing, completed, needs_review, failed
    error: str | None

    # Audit trail
    steps: list[dict[str, Any]]


# ===========================================================================
# Node Functions
# ===========================================================================


async def extract_text_node(state: DocumentState) -> DocumentState:
    """Node: Extract text from document"""
    logger.info(f"[{state['job_id']}] Extracting text from {state['file_info'].get('filename')}")

    try:
        file_path = state["file_path"]
        content_type = state["file_info"].get("content_type", "")

        text = ""

        if "pdf" in content_type:
            text = await extract_pdf(file_path)
        elif "image" in content_type:
            text = await extract_image(file_path)
        elif "spreadsheet" in content_type or "excel" in content_type:
            text = await extract_excel(file_path)
        else:
            # Try as text
            try:
                with open(file_path, encoding="utf-8", errors="ignore") as f:
                    text = f.read()
            except:
                pass

        if not text:
            raise ValueError("Failed to extract text from document")

        # Chunk text
        chunks = chunk_text(text, max_chunk_size=2000)

        state["raw_text"] = text
        state["text_chunks"] = chunks
        state["steps"].append(
            {
                "node": "extract_text",
                "timestamp": datetime.utcnow().isoformat(),
                "result": f"Extracted {len(text)} chars, {len(chunks)} chunks",
            }
        )

        logger.info(f"[{state['job_id']}] Extracted {len(text)} chars")

    except Exception as e:
        state["error"] = f"Text extraction failed: {e}"
        state["status"] = "failed"
        logger.error(f"[{state['job_id']}] Text extraction failed: {e}")

    return state


async def rag_retrieval_node(state: DocumentState) -> DocumentState:
    """Node: Retrieve RAG context"""
    logger.info(f"[{state['job_id']}] RAG retrieval")

    try:
        # Get first chunk for retrieval
        query_text = state["text_chunks"][0] if state["text_chunks"] else state["raw_text"][:1000]

        # Call RAG service
        contexts, scores = await retrieve_rag_context(query_text, top_k=5)

        state["rag_context"] = contexts
        state["rag_scores"] = scores
        state["steps"].append(
            {
                "node": "rag_retrieval",
                "timestamp": datetime.utcnow().isoformat(),
                "result": f"Retrieved {len(contexts)} contexts",
            }
        )

        logger.info(f"[{state['job_id']}] Retrieved {len(contexts)} RAG contexts")

    except Exception as e:
        logger.warning(f"[{state['job_id']}] RAG retrieval failed: {e}, continuing without context")
        state["rag_context"] = []
        state["rag_scores"] = []

    return state


async def classify_document_node(state: DocumentState) -> DocumentState:
    """Node: Classify document type"""
    logger.info(f"[{state['job_id']}] Classifying document")

    try:
        llm = get_llm_client()

        system_prompt = """Bạn là chuyên gia phân loại chứng từ kế toán Việt Nam.
Phân loại tài liệu vào một trong các loại sau:
- purchase_invoice: Hóa đơn mua hàng/dịch vụ
- sales_invoice: Hóa đơn bán hàng
- expense: Chi phí (công tác phí, văn phòng phẩm, ...)
- receipt: Phiếu thu/chi
- bank_statement: Sao kê ngân hàng
- payroll: Bảng lương
- tax_return: Tờ khai thuế
- other: Khác

Trả về JSON:
{"doc_type": "loại", "confidence": 0.0-1.0, "reasoning": "lý do"}"""

        user_prompt = f"""Phân loại tài liệu sau:

---
{state["raw_text"][:2000]}
---

Trả về JSON."""

        response = llm.generate_json(
            prompt=user_prompt,
            system=system_prompt,
            temperature=0.1,
            max_tokens=256,
            request_id=state["job_id"],
            trace_id=state["job_id"],
        )

        state["doc_type"] = response.get("doc_type", "other")
        state["doc_type_confidence"] = float(response.get("confidence", 0.5))
        state["steps"].append(
            {
                "node": "classify_document",
                "timestamp": datetime.utcnow().isoformat(),
                "result": f"Type: {state['doc_type']} ({state['doc_type_confidence']:.2f})",
            }
        )

        logger.info(f"[{state['job_id']}] Classified as {state['doc_type']}")

    except Exception as e:
        logger.error(f"[{state['job_id']}] Classification failed: {e}")
        state["doc_type"] = "other"
        state["doc_type_confidence"] = 0.0

    return state


async def extract_data_node(state: DocumentState) -> DocumentState:
    """Node: Extract structured data from document"""
    logger.info(f"[{state['job_id']}] Extracting data")

    try:
        llm = get_llm_client()

        # Build context from RAG
        context_text = ""
        if state["rag_context"]:
            context_text = "\n\nTham khảo:\n" + "\n".join(
                [f"- {ctx.get('content', '')[:200]}..." for ctx in state["rag_context"][:3]]
            )

        system_prompt = f"""Bạn là chuyên gia kế toán Việt Nam. Trích xuất thông tin từ {state["doc_type"]}.

Trả về JSON với format:
{{
    "vendor": "tên nhà cung cấp/khách hàng",
    "invoice_no": "số hóa đơn",
    "invoice_date": "YYYY-MM-DD",
    "total_amount": số_tiền,
    "vat_amount": tiền_thuế,
    "vat_rate": tỷ_lệ_VAT (0.08 hoặc 0.10),
    "currency": "VND",
    "items": [
        {{"description": "mô tả", "quantity": số, "unit_price": đơn_giá, "amount": thành_tiền}}
    ],
    "payment_method": "cash|bank_transfer|credit",
    "notes": "ghi chú"
}}{context_text}"""

        user_prompt = f"""Trích xuất thông tin từ tài liệu:

---
{state["raw_text"][:3000]}
---

Trả về JSON."""

        response = llm.generate_json(
            prompt=user_prompt,
            system=system_prompt,
            temperature=0.1,
            max_tokens=1024,
            request_id=f"{state['job_id']}-extract",
            trace_id=state["job_id"],
        )

        state["extracted_data"] = response
        state["steps"].append(
            {
                "node": "extract_data",
                "timestamp": datetime.utcnow().isoformat(),
                "result": f"Extracted: vendor={response.get('vendor')}, total={response.get('total_amount')}",
            }
        )

        logger.info(f"[{state['job_id']}] Extracted data: {response.get('vendor')}")

    except Exception as e:
        logger.error(f"[{state['job_id']}] Data extraction failed: {e}")
        state["extracted_data"] = {}
        state["error"] = f"Data extraction failed: {e}"

    return state


async def generate_proposal_node(state: DocumentState) -> DocumentState:
    """Node: Generate journal entry proposal"""
    logger.info(f"[{state['job_id']}] Generating proposal")

    try:
        llm = get_llm_client()

        # Build prompt based on doc type
        doc_type = state["doc_type"]
        extracted = state["extracted_data"]

        # Get accounting rules from RAG
        rules_context = ""
        for ctx in state.get("rag_context", []):
            if "TT200" in str(ctx) or "account" in str(ctx).lower():
                rules_context += f"\n- {ctx.get('content', '')[:300]}"

        system_prompt = f"""Bạn là chuyên gia kế toán Việt Nam theo TT200.

Loại chứng từ: {doc_type}
Thông tin đã trích xuất:
- Nhà cung cấp: {extracted.get("vendor", "N/A")}
- Số HĐ: {extracted.get("invoice_no", "N/A")}
- Tổng tiền: {extracted.get("total_amount", 0):,.0f} VND
- Thuế VAT: {extracted.get("vat_amount", 0):,.0f} VND
{rules_context}

Đề xuất bút toán kế toán phù hợp.

Trả về JSON:
{{
    "entries": [
        {{"account_code": "xxx", "account_name": "tên TK", "debit": số, "credit": số, "description": "mô tả"}}
    ],
    "explanation": "giải thích chi tiết bút toán",
    "confidence": 0.0-1.0,
    "needs_human_review": true/false,
    "risks": ["danh sách rủi ro nếu có"],
    "assumptions": ["giả định đã sử dụng"]
}}"""

        user_prompt = f"""Đề xuất bút toán cho chứng từ đã phân tích.

Thông tin bổ sung từ chứng từ gốc:
---
{state["raw_text"][:1500]}
---

Trả về JSON bút toán."""

        response = llm.generate_json(
            prompt=user_prompt,
            system=system_prompt,
            temperature=0.2,
            max_tokens=1536,
            request_id=f"{state['job_id']}-proposal",
            trace_id=state["job_id"],
        )

        # Merge with extracted data
        proposal = {
            "doc_id": state["job_id"],
            "doc_type": doc_type,
            "vendor": extracted.get("vendor", ""),
            "invoice_no": extracted.get("invoice_no", ""),
            "invoice_date": extracted.get("invoice_date", ""),
            "total_amount": float(extracted.get("total_amount", 0) or 0),
            "vat_amount": float(extracted.get("vat_amount", 0) or 0),
            "entries": response.get("entries", []),
            "explanation": response.get("explanation", ""),
            "confidence": float(response.get("confidence", 0.5)),
            "needs_human_review": response.get("needs_human_review", True),
            "risks": response.get("risks", []),
            "assumptions": response.get("assumptions", []),
        }

        state["proposal"] = proposal
        state["steps"].append(
            {
                "node": "generate_proposal",
                "timestamp": datetime.utcnow().isoformat(),
                "result": f"Generated {len(proposal['entries'])} entries",
            }
        )

        logger.info(f"[{state['job_id']}] Generated proposal with {len(proposal['entries'])} entries")

    except Exception as e:
        logger.error(f"[{state['job_id']}] Proposal generation failed: {e}")
        state["proposal"] = {"entries": [], "error": str(e)}
        state["error"] = f"Proposal generation failed: {e}"

    return state


async def validate_proposal_node(state: DocumentState) -> DocumentState:
    """Node: Validate proposal with guardrails"""
    logger.info(f"[{state['job_id']}] Validating proposal")

    try:
        engine = get_guardrails_engine()

        # Validate input
        input_data = {
            "file_size": state["file_info"].get("size", 0),
            "content_type": state["file_info"].get("content_type", ""),
            "text": state["raw_text"],
        }

        # Validate output
        result = engine.process(input_data, state["proposal"])

        state["validation_result"] = result

        # Update status based on validation
        if not result["overall_valid"]:
            state["status"] = "failed"
            state["error"] = "; ".join(result["all_errors"])
        elif result["needs_human_review"]:
            state["status"] = "needs_review"
        else:
            state["status"] = "completed"

        # Update proposal with validation info
        state["proposal"]["needs_human_review"] = result["needs_human_review"]
        if result["all_warnings"]:
            state["proposal"]["risks"] = state["proposal"].get("risks", []) + result["all_warnings"]

        state["steps"].append(
            {
                "node": "validate_proposal",
                "timestamp": datetime.utcnow().isoformat(),
                "result": f"Valid: {result['overall_valid']}, Review: {result['needs_human_review']}",
            }
        )

        logger.info(f"[{state['job_id']}] Validation: valid={result['overall_valid']}")

    except Exception as e:
        logger.error(f"[{state['job_id']}] Validation failed: {e}")
        state["validation_result"] = {"error": str(e)}
        state["status"] = "needs_review"  # Fail safe - require review

    return state


def finalize_node(state: DocumentState) -> DocumentState:
    """Node: Finalize processing"""
    logger.info(f"[{state['job_id']}] Finalizing - status: {state['status']}")

    state["steps"].append(
        {"node": "finalize", "timestamp": datetime.utcnow().isoformat(), "result": f"Final status: {state['status']}"}
    )

    return state


# ===========================================================================
# Routing Functions
# ===========================================================================


def should_continue_after_extract(state: DocumentState) -> str:
    """Decide next step after text extraction"""
    if state.get("error"):
        return "finalize"
    return "rag_retrieval"


def should_continue_after_proposal(state: DocumentState) -> str:
    """Decide next step after proposal generation"""
    if state.get("error"):
        return "finalize"
    return "validate"


# ===========================================================================
# Helper Functions
# ===========================================================================


async def extract_pdf(file_path: str) -> str:
    """Extract text from PDF"""
    try:
        import pdfplumber

        text_parts = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                text_parts.append(page_text)
        return "\n".join(text_parts)
    except Exception as e:
        logger.warning(f"pdfplumber failed: {e}")
        return ""


async def extract_image(file_path: str) -> str:
    """Extract text from image using OCR"""
    try:
        from paddleocr import PaddleOCR

        ocr = PaddleOCR(use_angle_cls=True, lang="vi")
        result = ocr.ocr(file_path, cls=True)

        lines = []
        if result and result[0]:
            for line in result[0]:
                if line and len(line) > 1:
                    lines.append(line[1][0])
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"OCR failed: {e}")
        return ""


async def extract_excel(file_path: str) -> str:
    """Extract data from Excel"""
    try:
        import pandas as pd

        df = pd.read_excel(file_path)

        lines = []
        for col in df.columns:
            lines.append(f"Cột: {col}")
        for idx, row in df.iterrows():
            row_text = " | ".join([f"{col}: {val}" for col, val in row.items() if pd.notna(val)])
            lines.append(f"Dòng {idx + 1}: {row_text}")
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Excel extraction failed: {e}")
        return ""


def chunk_text(text: str, max_chunk_size: int = 2000, overlap: int = 200) -> list[str]:
    """Split text into overlapping chunks"""
    if len(text) <= max_chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + max_chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        start = end - overlap

    return chunks


async def retrieve_rag_context(query: str, top_k: int = 5) -> tuple:
    """Retrieve context from RAG system"""
    # TODO: Integrate with Qdrant
    # For now, return empty
    return [], []


# ===========================================================================
# Graph Builder
# ===========================================================================


def build_processing_graph():
    """Build the LangGraph processing pipeline"""

    if not LANGGRAPH_AVAILABLE:
        logger.warning("LangGraph not available, using simple pipeline")
        return None

    # Create graph
    workflow = StateGraph(DocumentState)

    # Add nodes
    workflow.add_node("extract_text", extract_text_node)
    workflow.add_node("rag_retrieval", rag_retrieval_node)
    workflow.add_node("classify", classify_document_node)
    workflow.add_node("extract_data", extract_data_node)
    workflow.add_node("generate_proposal", generate_proposal_node)
    workflow.add_node("validate", validate_proposal_node)
    workflow.add_node("finalize", finalize_node)

    # Add edges
    workflow.set_entry_point("extract_text")

    workflow.add_conditional_edges(
        "extract_text", should_continue_after_extract, {"rag_retrieval": "rag_retrieval", "finalize": "finalize"}
    )

    workflow.add_edge("rag_retrieval", "classify")
    workflow.add_edge("classify", "extract_data")
    workflow.add_edge("extract_data", "generate_proposal")

    workflow.add_conditional_edges(
        "generate_proposal", should_continue_after_proposal, {"validate": "validate", "finalize": "finalize"}
    )

    workflow.add_edge("validate", "finalize")
    workflow.add_edge("finalize", END)

    # Compile
    memory = MemorySaver()
    app = workflow.compile(checkpointer=memory)

    return app


# ===========================================================================
# Main Orchestrator Class
# ===========================================================================


class DocumentOrchestrator:
    """Main orchestrator for document processing"""

    def __init__(self):
        self.graph = build_processing_graph()
        self.llm = None
        self.guardrails = None

    async def process(
        self, job_id: str, file_path: str, file_info: dict[str, Any], tenant_id: str = "default"
    ) -> dict[str, Any]:
        """Process a document through the full pipeline"""

        # Initialize state
        initial_state: DocumentState = {
            "job_id": job_id,
            "file_path": file_path,
            "file_info": file_info,
            "tenant_id": tenant_id,
            "raw_text": "",
            "text_chunks": [],
            "rag_context": [],
            "rag_scores": [],
            "doc_type": "",
            "doc_type_confidence": 0.0,
            "extracted_data": {},
            "proposal": {},
            "validation_result": {},
            "status": "processing",
            "error": None,
            "steps": [],
        }

        try:
            if self.graph:
                # Use LangGraph
                config = {"configurable": {"thread_id": job_id}}
                final_state = await self.graph.ainvoke(initial_state, config)
                return final_state
            else:
                # Fallback: run nodes sequentially
                state = initial_state
                state = await extract_text_node(state)
                if not state.get("error"):
                    state = await rag_retrieval_node(state)
                    state = await classify_document_node(state)
                    state = await extract_data_node(state)
                    state = await generate_proposal_node(state)
                    state = await validate_proposal_node(state)
                state = finalize_node(state)
                return state

        except Exception as e:
            logger.error(f"Orchestration failed: {e}", exc_info=True)
            initial_state["status"] = "failed"
            initial_state["error"] = str(e)
            return initial_state


# ===========================================================================
# Singleton
# ===========================================================================

_orchestrator: DocumentOrchestrator | None = None


def get_orchestrator() -> DocumentOrchestrator:
    """Get or create orchestrator"""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = DocumentOrchestrator()
    return _orchestrator


# ===========================================================================
# Convenience Function
# ===========================================================================


async def process_document(
    job_id: str, file_path: str, file_info: dict[str, Any], tenant_id: str = "default"
) -> dict[str, Any]:
    """Process document (convenience function)"""
    orchestrator = get_orchestrator()
    return await orchestrator.process(job_id, file_path, file_info, tenant_id)
