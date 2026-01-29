"""
ERPX AI Accounting - Temporal Workflows
========================================
Document processing workflows using Temporal.
"""

import asyncio
import logging
import os
import sys
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

# Temporal imports
try:
    from temporalio import activity, workflow
    from temporalio.client import Client as TemporalClient
    from temporalio.common import RetryPolicy
    from temporalio.worker import Worker

    TEMPORAL_AVAILABLE = True
except ImportError:
    TEMPORAL_AVAILABLE = False

sys.path.insert(0, "/root/erp-ai")

logger = logging.getLogger("erpx.workflows")

# Configuration
TEMPORAL_ADDRESS = os.getenv("TEMPORAL_ADDRESS", "localhost:7233")
TASK_QUEUE = os.getenv("TEMPORAL_TASK_QUEUE", "erpx-document-processing")


# =============================================================================
# Activity Inputs/Outputs
# =============================================================================


@dataclass
class DocumentInput:
    """Input for document processing workflow"""

    job_id: str
    company_id: str
    user_id: str
    document_key: str
    document_type: str
    trace_id: str


@dataclass
class ExtractionResult:
    """Result of document extraction"""

    success: bool
    extracted_text: str
    key_fields: dict[str, Any]
    error: str | None = None


@dataclass
class RAGResult:
    """Result of RAG retrieval"""

    context: str
    sources: list


@dataclass
class ProposalResult:
    """Result of journal proposal generation"""

    success: bool
    proposal: dict[str, Any]
    llm_request_id: str
    llm_latency_ms: float
    error: str | None = None


@dataclass
class ValidationResult:
    """Result of policy validation"""

    is_valid: bool
    issues: list
    risk_level: str


@dataclass
class WorkflowResult:
    """Final workflow result"""

    job_id: str
    status: str
    proposal: dict[str, Any] | None = None
    validation: dict[str, Any] | None = None
    llm_request_id: str | None = None
    llm_latency_ms: float = 0
    error: str | None = None


# =============================================================================
# Activities
# =============================================================================

if TEMPORAL_AVAILABLE:

    @activity.defn(name="extract_document")
    async def extract_document_activity(input: DocumentInput) -> ExtractionResult:
        """Extract text and fields from document"""
        from src.core import config
        from src.processing import process_document
        from src.storage import download_document

        logger.info(f"[{input.job_id}] Extracting document: {input.document_key}")

        try:
            # Download document (Phase 1.1 Fix)
            # Assuming input.document_key is the key, and we use default bucket
            doc_data = download_document(config.MINIO_BUCKET, input.document_key)
            if doc_data is None:
                return ExtractionResult(
                    success=False, extracted_text="", key_fields={}, error=f"Document not found: {input.document_key}"
                )

            # Determine content type
            ext = input.document_key.lower().split(".")[-1]
            content_type_map = {
                "pdf": "application/pdf",
                "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "xls": "application/vnd.ms-excel",
                "png": "image/png",
                "jpg": "image/jpeg",
                "jpeg": "image/jpeg",
            }
            content_type = content_type_map.get(ext, "application/octet-stream")

            # Process
            result = process_document(doc_data, content_type, input.document_key)

            if not result.success:
                return ExtractionResult(success=False, extracted_text="", key_fields={}, error=result.error_message)

            return ExtractionResult(success=True, extracted_text=result.document_text, key_fields=result.key_fields)

        except Exception as e:
            logger.error(f"[{input.job_id}] Extraction error: {e}")
            return ExtractionResult(success=False, extracted_text="", key_fields={}, error=str(e))

    @activity.defn(name="retrieve_rag_context")
    async def retrieve_rag_activity(extracted_text: str, key_fields: dict[str, Any], document_type: str) -> RAGResult:
        """Retrieve relevant context from RAG"""
        from src.rag import format_context_for_llm, search_accounting_context

        try:
            # Build query
            query_parts = []
            if key_fields.get("vendor_name"):
                query_parts.append(key_fields["vendor_name"])
            if document_type == "invoice":
                query_parts.append("hạch toán hóa đơn mua hàng")
            query_parts.append(extracted_text[:200])

            # Search
            results = search_accounting_context(" ".join(query_parts), limit=3)

            return RAGResult(context=format_context_for_llm(results), sources=[r.source for r in results])

        except Exception as e:
            logger.warning(f"RAG retrieval error: {e}")
            return RAGResult(context="", sources=[])

    @activity.defn(name="generate_proposal")
    async def generate_proposal_activity(
        extracted_text: str, key_fields: dict[str, Any], rag_context: str, trace_id: str
    ) -> ProposalResult:
        """Generate journal entry proposal using DO Agent LLM"""
        import json

        from src.llm import get_llm_client

        try:
            client = get_llm_client()

            system_prompt = """Bạn là chuyên gia kế toán Việt Nam theo Thông tư 200/2014/TT-BTC.
Phân tích chứng từ và đề xuất bút toán kế toán chuẩn.

OUTPUT JSON:
{
  "invoice_summary": {...},
  "journal_entries": [...],
  "explanation": "...",
  "confidence": 0.9
}"""

            user_prompt = f"""### CHỨNG TỪ:
{extracted_text[:3000]}

### THÔNG TIN:
{json.dumps(key_fields, ensure_ascii=False)}

### TÀI LIỆU THAM KHẢO:
{rag_context or "TT200/2014"}

Đề xuất bút toán kế toán (JSON)."""

            response = await client.generate(
                prompt=user_prompt,
                system=system_prompt,
                json_schema={"type": "object"},
                temperature=0.2,
                max_tokens=2000,
                trace_id=trace_id,
            )

            # Parse response
            content = response.content.strip()
            if "```json" in content:
                start = content.find("```json") + 7
                end = content.find("```", start)
                content = content[start:end].strip()
            elif "```" in content:
                start = content.find("```") + 3
                end = content.find("```", start)
                content = content[start:end].strip()

            proposal = json.loads(content)

            return ProposalResult(
                success=True, proposal=proposal, llm_request_id=response.request_id, llm_latency_ms=response.latency_ms
            )

        except Exception as e:
            logger.error(f"Proposal generation error: {e}")
            return ProposalResult(success=False, proposal={}, llm_request_id="", llm_latency_ms=0, error=str(e))

    @activity.defn(name="validate_with_opa")
    async def validate_opa_activity(proposal: dict[str, Any], company_id: str, user_id: str) -> ValidationResult:
        """Validate proposal with OPA policies"""
        import httpx

        opa_url = os.getenv("OPA_URL", "http://localhost:8181")

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{opa_url}/v1/data/erpx/journal/validate",
                    json={"input": {"company_id": company_id, "user_id": user_id, "proposal": proposal}},
                )

                if response.status_code == 200:
                    result = response.json().get("result", {})
                    return ValidationResult(
                        is_valid=result.get("allow", True),
                        issues=result.get("issues", []),
                        risk_level=result.get("risk_level", "low"),
                    )

            # OPA not configured - default allow
            return ValidationResult(is_valid=True, issues=[], risk_level="unknown")

        except Exception as e:
            logger.warning(f"OPA validation error: {e}")
            return ValidationResult(is_valid=True, issues=[], risk_level="unknown")

    @activity.defn(name="update_job_status")
    async def update_job_activity(
        job_id: str, status: str, proposal: dict | None = None, error: str | None = None
    ) -> bool:
        """Update job status in database"""
        try:
            from src.db import update_job_status

            await update_job_status(job_id, status)
            return True
        except Exception as e:
            logger.error(f"Failed to update job {job_id}: {e}")
            return False


# =============================================================================
# Workflow
# =============================================================================

if TEMPORAL_AVAILABLE:

    @workflow.defn(name="DocumentProcessingWorkflow")
    class DocumentProcessingWorkflow:
        """
        Document Processing Workflow

        Steps:
        1. Extract document text and fields
        2. Retrieve RAG context
        3. Generate journal proposal with DO Agent LLM
        4. Validate with OPA policies
        5. Update job status
        """

        @workflow.run
        async def run(self, input: DocumentInput) -> WorkflowResult:
            """Run the document processing workflow"""

            # Retry policy for activities
            retry_policy = RetryPolicy(
                maximum_attempts=3,
                initial_interval=timedelta(seconds=1),
                maximum_interval=timedelta(seconds=30),
                backoff_coefficient=2.0,
            )

            # Step 1: Extract document
            extraction = await workflow.execute_activity(
                extract_document_activity,
                input,
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=retry_policy,
            )

            if not extraction.success:
                await workflow.execute_activity(
                    update_job_activity,
                    args=[input.job_id, "failed", None, extraction.error],
                    start_to_close_timeout=timedelta(seconds=30),
                )
                return WorkflowResult(job_id=input.job_id, status="failed", error=extraction.error)

            # Step 2: Retrieve RAG context
            rag_result = await workflow.execute_activity(
                retrieve_rag_activity,
                args=[extraction.extracted_text, extraction.key_fields, input.document_type],
                start_to_close_timeout=timedelta(minutes=2),
                retry_policy=retry_policy,
            )

            # Step 3: Generate proposal
            proposal_result = await workflow.execute_activity(
                generate_proposal_activity,
                args=[extraction.extracted_text, extraction.key_fields, rag_result.context, input.trace_id],
                start_to_close_timeout=timedelta(minutes=3),
                retry_policy=retry_policy,
            )

            if not proposal_result.success:
                await workflow.execute_activity(
                    update_job_activity,
                    args=[input.job_id, "failed", None, proposal_result.error],
                    start_to_close_timeout=timedelta(seconds=30),
                )
                return WorkflowResult(job_id=input.job_id, status="failed", error=proposal_result.error)

            # Step 4: Validate with OPA
            validation = await workflow.execute_activity(
                validate_opa_activity,
                args=[proposal_result.proposal, input.company_id, input.user_id],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=retry_policy,
            )

            # Determine final status
            if validation.is_valid:
                status = "pending_approval"
            else:
                status = "validation_failed"

            # Step 5: Update job
            await workflow.execute_activity(
                update_job_activity,
                args=[input.job_id, status, proposal_result.proposal, None],
                start_to_close_timeout=timedelta(seconds=30),
            )

            return WorkflowResult(
                job_id=input.job_id,
                status=status,
                proposal=proposal_result.proposal,
                validation={
                    "is_valid": validation.is_valid,
                    "issues": validation.issues,
                    "risk_level": validation.risk_level,
                },
                llm_request_id=proposal_result.llm_request_id,
                llm_latency_ms=proposal_result.llm_latency_ms,
            )


# =============================================================================
# Worker
# =============================================================================


async def run_worker():
    """Run Temporal worker"""
    if not TEMPORAL_AVAILABLE:
        logger.error("Temporal not available")
        return

    logger.info(f"Connecting to Temporal at {TEMPORAL_ADDRESS}")

    client = await TemporalClient.connect(TEMPORAL_ADDRESS)

    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[DocumentProcessingWorkflow],
        activities=[
            extract_document_activity,
            retrieve_rag_activity,
            generate_proposal_activity,
            validate_opa_activity,
            update_job_activity,
        ],
    )

    logger.info(f"Starting worker on task queue: {TASK_QUEUE}")
    await worker.run()


# =============================================================================
# Client Functions
# =============================================================================

_temporal_client = None


async def get_temporal_client() -> Any | None:
    """Get Temporal client"""
    global _temporal_client
    if not TEMPORAL_AVAILABLE:
        return None

    if _temporal_client is None:
        try:
            _temporal_client = await TemporalClient.connect(TEMPORAL_ADDRESS)
        except Exception as e:
            logger.error(f"Failed to connect to Temporal: {e}")
            return None

    return _temporal_client


async def start_document_workflow(
    job_id: str,
    company_id: str,
    user_id: str,
    document_key: str,
    document_type: str = "invoice",
    trace_id: str = "",
) -> str | None:
    """Start a document processing workflow"""
    client = await get_temporal_client()
    if client is None:
        logger.warning("Temporal not available, falling back to direct processing")
        return None

    input = DocumentInput(
        job_id=job_id,
        company_id=company_id,
        user_id=user_id,
        document_key=document_key,
        document_type=document_type,
        trace_id=trace_id or job_id,
    )

    try:
        handle = await client.start_workflow(
            DocumentProcessingWorkflow.run,
            input,
            id=f"doc-{job_id}",
            task_queue=TASK_QUEUE,
        )
        logger.info(f"Started workflow {handle.id} for job {job_id}")
        return handle.id
    except Exception as e:
        logger.error(f"Failed to start workflow: {e}")
        return None


async def get_workflow_result(workflow_id: str) -> WorkflowResult | None:
    """Get workflow result"""
    client = await get_temporal_client()
    if client is None:
        return None

    try:
        handle = client.get_workflow_handle(workflow_id)
        result = await handle.result()
        return result
    except Exception as e:
        logger.error(f"Failed to get workflow result: {e}")
        return None


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    if not TEMPORAL_AVAILABLE:
        print("Error: temporalio not installed")
        print("Install with: pip install temporalio")
        sys.exit(1)

    print("Starting Temporal worker...")
    asyncio.run(run_worker())


__all__ = [
    "DocumentInput",
    "WorkflowResult",
    "start_document_workflow",
    "get_workflow_result",
    "run_worker",
    "TASK_QUEUE",
]
