"""
ERPX AI - Temporal Workflows
============================
Durable workflows using Temporal for reliable document processing.

Workflows:
- DocumentProcessingWorkflow: Main processing workflow
- ApprovalWorkflow: Human approval workflow
- LedgerCommitWorkflow: Commit to accounting ledger
"""

import json
import logging
import os
import sys
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Dict, List, Optional

# Temporal imports
try:
    from temporalio import activity, workflow
    from temporalio.client import Client
    from temporalio.common import RetryPolicy
    from temporalio.worker import Worker

    TEMPORAL_AVAILABLE = True
except ImportError:
    TEMPORAL_AVAILABLE = False
    workflow = None
    activity = None

sys.path.insert(0, "/root/erp-ai")

logger = logging.getLogger("erpx.workflows")


# ===========================================================================
# Data Classes
# ===========================================================================


@dataclass
class DocumentInput:
    """Input for document processing workflow"""

    job_id: str
    file_path: str
    file_info: dict[str, Any]
    tenant_id: str = "default"


@dataclass
class ProcessingResult:
    """Result of document processing"""

    job_id: str
    status: str
    proposal: dict[str, Any] | None = None
    error: str | None = None


@dataclass
class ApprovalInput:
    """Input for approval workflow"""

    job_id: str
    proposal: dict[str, Any]
    approver_id: str
    timeout_hours: int = 72


@dataclass
class ApprovalResult:
    """Result of approval workflow"""

    job_id: str
    approved: bool
    approver_id: str
    notes: str = ""
    approved_at: str = ""


# ===========================================================================
# Activities
# ===========================================================================

if TEMPORAL_AVAILABLE:

    @activity.defn
    async def extract_text_activity(job_id: str, file_path: str, content_type: str) -> str:
        """Activity: Extract text from document"""
        logger.info(f"[Activity] Extracting text for {job_id}")

        try:
            if "pdf" in content_type:
                import pdfplumber

                text_parts = []
                with pdfplumber.open(file_path) as pdf:
                    for page in pdf.pages:
                        text_parts.append(page.extract_text() or "")
                return "\n".join(text_parts)

            elif "image" in content_type:
                from paddleocr import PaddleOCR

                ocr = PaddleOCR(use_angle_cls=True, lang="vi")
                result = ocr.ocr(file_path, cls=True)
                lines = []
                if result and result[0]:
                    for line in result[0]:
                        if line and len(line) > 1:
                            lines.append(line[1][0])
                return "\n".join(lines)

            elif "excel" in content_type or "spreadsheet" in content_type:
                import pandas as pd

                df = pd.read_excel(file_path)
                lines = [f"Cột: {col}" for col in df.columns]
                for idx, row in df.iterrows():
                    row_text = " | ".join([f"{col}: {val}" for col, val in row.items() if pd.notna(val)])
                    lines.append(f"Dòng {idx + 1}: {row_text}")
                return "\n".join(lines)

            else:
                with open(file_path, encoding="utf-8", errors="ignore") as f:
                    return f.read()

        except Exception as e:
            logger.error(f"[Activity] Text extraction failed: {e}")
            raise

    @activity.defn
    async def classify_document_activity(job_id: str, text: str) -> dict[str, Any]:
        """Activity: Classify document type using LLM"""
        logger.info(f"[Activity] Classifying document for {job_id}")

        from src.llm import get_llm_client

        llm = get_llm_client()

        system_prompt = """Phân loại tài liệu kế toán Việt Nam:
- purchase_invoice, sales_invoice, expense, receipt, bank_statement, payroll, tax_return, other

Trả về JSON: {"doc_type": "loại", "confidence": 0.0-1.0}"""

        response = llm.generate_json(
            prompt=f"Phân loại:\n{text[:2000]}",
            system=system_prompt,
            temperature=0.1,
            max_tokens=256,
            request_id=f"{job_id}-classify",
        )

        return {"doc_type": response.get("doc_type", "other"), "confidence": float(response.get("confidence", 0.5))}

    @activity.defn
    async def extract_data_activity(job_id: str, text: str, doc_type: str) -> dict[str, Any]:
        """Activity: Extract structured data using LLM"""
        logger.info(f"[Activity] Extracting data for {job_id}")

        from src.llm import get_llm_client

        llm = get_llm_client()

        system_prompt = f"""Trích xuất thông tin từ {doc_type}:
{{
    "vendor": "tên NCC",
    "invoice_no": "số HĐ",
    "invoice_date": "YYYY-MM-DD",
    "total_amount": số,
    "vat_amount": số,
    "items": [{{"description": "", "amount": số}}]
}}"""

        response = llm.generate_json(
            prompt=f"Trích xuất:\n{text[:3000]}",
            system=system_prompt,
            temperature=0.1,
            max_tokens=1024,
            request_id=f"{job_id}-extract",
        )

        return response

    @activity.defn
    async def generate_proposal_activity(
        job_id: str, doc_type: str, extracted_data: dict[str, Any], text: str
    ) -> dict[str, Any]:
        """Activity: Generate journal entry proposal using LLM"""
        logger.info(f"[Activity] Generating proposal for {job_id}")

        from src.llm import get_llm_client

        llm = get_llm_client()

        system_prompt = f"""Đề xuất bút toán kế toán theo TT200 cho {doc_type}.

Thông tin: vendor={extracted_data.get("vendor")}, total={extracted_data.get("total_amount")}, vat={extracted_data.get("vat_amount")}

Trả về JSON:
{{
    "entries": [{{"account_code": "xxx", "account_name": "tên TK", "debit": số, "credit": số, "description": ""}}],
    "explanation": "giải thích",
    "confidence": 0.0-1.0,
    "needs_human_review": true/false,
    "risks": []
}}"""

        response = llm.generate_json(
            prompt=f"Đề xuất bút toán:\n{text[:1500]}",
            system=system_prompt,
            temperature=0.2,
            max_tokens=1536,
            request_id=f"{job_id}-proposal",
        )

        # Merge
        return {
            "doc_id": job_id,
            "doc_type": doc_type,
            "vendor": extracted_data.get("vendor", ""),
            "invoice_no": extracted_data.get("invoice_no", ""),
            "invoice_date": extracted_data.get("invoice_date", ""),
            "total_amount": float(extracted_data.get("total_amount", 0) or 0),
            "vat_amount": float(extracted_data.get("vat_amount", 0) or 0),
            "entries": response.get("entries", []),
            "explanation": response.get("explanation", ""),
            "confidence": float(response.get("confidence", 0.5)),
            "needs_human_review": response.get("needs_human_review", True),
            "risks": response.get("risks", []),
        }

    @activity.defn
    async def validate_proposal_activity(proposal: dict[str, Any]) -> dict[str, Any]:
        """Activity: Validate proposal with guardrails"""
        logger.info(f"[Activity] Validating proposal for {proposal.get('doc_id')}")

        from src.guardrails import get_guardrails_engine

        engine = get_guardrails_engine()

        valid, errors, warnings = engine.validate_output(proposal)

        return {
            "valid": valid,
            "errors": errors,
            "warnings": warnings,
            "needs_human_review": not valid or len(warnings) > 0,
        }

    @activity.defn
    async def send_approval_notification_activity(job_id: str, proposal: dict[str, Any], approver_id: str) -> bool:
        """Activity: Send notification for approval"""
        logger.info(f"[Activity] Sending approval notification for {job_id}")

        from src.db import get_connection
        from src.notifications import send_email, send_telegram_message

        email = None
        telegram_chat_id = None

        # 1. Resolve approver contact info
        # If approver_id looks like a numeric ID, assume it's a Telegram chat ID (direct bot usage)
        if approver_id.isdigit():
            telegram_chat_id = approver_id
        else:
            # Assume UUID -> lookup in DB
            try:
                async with get_connection() as conn:
                    row = await conn.fetchrow("SELECT email, telegram_chat_id FROM users WHERE id = $1", approver_id)
                    if row:
                        email = row["email"]
                        telegram_chat_id = row["telegram_chat_id"]
            except Exception as e:
                logger.error(f"Failed to lookup user {approver_id}: {e}")

        # 2. Format message
        invoice_no = proposal.get("invoice_no", "N/A")
        vendor = proposal.get("vendor", "N/A")
        amount = proposal.get("total_amount", 0)
        currency = proposal.get("currency", "VND")

        subject = f"Approval Required: Invoice {invoice_no} from {vendor}"

        body_text = f"""
Approval Request for Job {job_id}

Vendor: {vendor}
Invoice No: {invoice_no}
Total Amount: {amount:,.0f} {currency}

Please review the journal entries proposed by AI.
"""

        # 3. Send notifications
        sent = False

        if email:
            email_sent = await send_email(email, subject, body_text)
            if email_sent:
                logger.info(f"Email sent to {email}")
                sent = True

        if telegram_chat_id:
            telegram_msg = f"""
🔔 Approval Required

Vendor: {vendor}
Invoice: {invoice_no}
Amount: {amount:,.0f} {currency}

Reply with:
/approve {job_id}
/reject {job_id}
"""
            tg_sent = await send_telegram_message(telegram_chat_id, telegram_msg)
            if tg_sent:
                logger.info(f"Telegram sent to {telegram_chat_id}")
                sent = True

        if not sent:
            logger.warning(f"No notification sent for {job_id} (approver: {approver_id})")

        return True

    @activity.defn
    async def commit_to_ledger_activity(job_id: str, proposal: dict[str, Any], approver_id: str) -> dict[str, Any]:
        """Activity: Commit approved journal to ledger"""
        logger.info(f"[Activity] Committing to ledger for {job_id}")

        # TODO: Integrate with PostgreSQL ledger
        # For now, return success
        from datetime import datetime

        return {
            "job_id": job_id,
            "committed": True,
            "committed_at": datetime.utcnow().isoformat() + "Z",
            "ledger_entry_id": f"LED-{job_id[:8]}",
        }

    @activity.defn
    async def store_job_result_activity(job_id: str, result: dict[str, Any]) -> bool:
        """Activity: Store job result to database"""
        logger.info(f"[Activity] Storing result for {job_id}")

        # TODO: Store to PostgreSQL
        return True


# ===========================================================================
# Workflows
# ===========================================================================

if TEMPORAL_AVAILABLE:

    @workflow.defn
    class DocumentProcessingWorkflow:
        """Main workflow for document processing"""

        @workflow.run
        async def run(self, input: DocumentInput) -> ProcessingResult:
            """Execute document processing workflow"""

            retry_policy = RetryPolicy(
                initial_interval=timedelta(seconds=1), maximum_interval=timedelta(minutes=1), maximum_attempts=3
            )

            try:
                # Step 1: Extract text
                text = await workflow.execute_activity(
                    extract_text_activity,
                    args=[input.job_id, input.file_path, input.file_info.get("content_type", "")],
                    start_to_close_timeout=timedelta(minutes=5),
                    retry_policy=retry_policy,
                )

                if not text:
                    return ProcessingResult(job_id=input.job_id, status="failed", error="Failed to extract text")

                # Step 2: Classify
                classification = await workflow.execute_activity(
                    classify_document_activity,
                    args=[input.job_id, text],
                    start_to_close_timeout=timedelta(minutes=2),
                    retry_policy=retry_policy,
                )

                doc_type = classification.get("doc_type", "other")

                # Step 3: Extract data
                extracted = await workflow.execute_activity(
                    extract_data_activity,
                    args=[input.job_id, text, doc_type],
                    start_to_close_timeout=timedelta(minutes=3),
                    retry_policy=retry_policy,
                )

                # Step 4: Generate proposal
                proposal = await workflow.execute_activity(
                    generate_proposal_activity,
                    args=[input.job_id, doc_type, extracted, text],
                    start_to_close_timeout=timedelta(minutes=3),
                    retry_policy=retry_policy,
                )

                # Step 5: Validate
                validation = await workflow.execute_activity(
                    validate_proposal_activity,
                    args=[proposal],
                    start_to_close_timeout=timedelta(minutes=1),
                    retry_policy=retry_policy,
                )

                # Determine status
                if not validation.get("valid"):
                    status = "failed"
                elif validation.get("needs_human_review"):
                    status = "needs_review"
                else:
                    status = "completed"

                # Store result
                await workflow.execute_activity(
                    store_job_result_activity,
                    args=[input.job_id, {"proposal": proposal, "status": status}],
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=retry_policy,
                )

                return ProcessingResult(job_id=input.job_id, status=status, proposal=proposal)

            except Exception as e:
                return ProcessingResult(job_id=input.job_id, status="failed", error=str(e))

    @workflow.defn
    class ApprovalWorkflow:
        """Workflow for human approval with timeout"""

        def __init__(self):
            self.approval_received = False
            self.approved = False
            self.notes = ""

        @workflow.signal
        def approve(self, approved: bool, notes: str = ""):
            """Signal to approve/reject"""
            self.approval_received = True
            self.approved = approved
            self.notes = notes

        @workflow.run
        async def run(self, input: ApprovalInput) -> ApprovalResult:
            """Execute approval workflow"""

            # Send notification
            await workflow.execute_activity(
                send_approval_notification_activity,
                args=[input.job_id, input.proposal, input.approver_id],
                start_to_close_timeout=timedelta(seconds=30),
            )

            # Wait for approval signal with timeout
            try:
                await workflow.wait_condition(
                    lambda: self.approval_received, timeout=timedelta(hours=input.timeout_hours)
                )
            except TimeoutError:
                return ApprovalResult(
                    job_id=input.job_id,
                    approved=False,
                    approver_id=input.approver_id,
                    notes="Approval timeout - auto rejected",
                )

            # If approved, commit to ledger
            if self.approved:
                await workflow.execute_activity(
                    commit_to_ledger_activity,
                    args=[input.job_id, input.proposal, input.approver_id],
                    start_to_close_timeout=timedelta(minutes=1),
                )

            from datetime import datetime

            return ApprovalResult(
                job_id=input.job_id,
                approved=self.approved,
                approver_id=input.approver_id,
                notes=self.notes,
                approved_at=datetime.utcnow().isoformat() + "Z",
            )


# ===========================================================================
# Worker
# ===========================================================================


async def run_worker():
    """Run Temporal worker"""
    if not TEMPORAL_AVAILABLE:
        logger.error("Temporal not available")
        return

    temporal_address = os.getenv("TEMPORAL_ADDRESS", "localhost:7233")

    client = await Client.connect(temporal_address)

    worker = Worker(
        client,
        task_queue="erpx-document-processing",
        workflows=[DocumentProcessingWorkflow, ApprovalWorkflow],
        activities=[
            extract_text_activity,
            classify_document_activity,
            extract_data_activity,
            generate_proposal_activity,
            validate_proposal_activity,
            send_approval_notification_activity,
            commit_to_ledger_activity,
            store_job_result_activity,
        ],
    )

    logger.info("Starting Temporal worker...")
    await worker.run()


# ===========================================================================
# Client Helper
# ===========================================================================


class WorkflowClient:
    """Client for starting and managing workflows"""

    def __init__(self):
        self.client = None

    async def connect(self):
        """Connect to Temporal"""
        if not TEMPORAL_AVAILABLE:
            raise RuntimeError("Temporal not available")

        temporal_address = os.getenv("TEMPORAL_ADDRESS", "localhost:7233")
        self.client = await Client.connect(temporal_address)

    async def start_document_processing(
        self, job_id: str, file_path: str, file_info: dict[str, Any], tenant_id: str = "default"
    ) -> str:
        """Start document processing workflow"""
        if not self.client:
            await self.connect()

        input_data = DocumentInput(job_id=job_id, file_path=file_path, file_info=file_info, tenant_id=tenant_id)

        handle = await self.client.start_workflow(
            DocumentProcessingWorkflow.run, input_data, id=f"doc-{job_id}", task_queue="erpx-document-processing"
        )

        return handle.id

    async def start_approval(
        self, job_id: str, proposal: dict[str, Any], approver_id: str, timeout_hours: int = 72
    ) -> str:
        """Start approval workflow"""
        if not self.client:
            await self.connect()

        input_data = ApprovalInput(
            job_id=job_id, proposal=proposal, approver_id=approver_id, timeout_hours=timeout_hours
        )

        handle = await self.client.start_workflow(
            ApprovalWorkflow.run, input_data, id=f"approval-{job_id}", task_queue="erpx-document-processing"
        )

        return handle.id

    async def send_approval_signal(self, workflow_id: str, approved: bool, notes: str = ""):
        """Send approval signal to workflow"""
        if not self.client:
            await self.connect()

        handle = self.client.get_workflow_handle(workflow_id)
        await handle.signal(ApprovalWorkflow.approve, approved, notes)

    async def get_workflow_result(self, workflow_id: str) -> Any:
        """Get workflow result"""
        if not self.client:
            await self.connect()

        handle = self.client.get_workflow_handle(workflow_id)
        return await handle.result()


# ===========================================================================
# Main
# ===========================================================================

if __name__ == "__main__":
    import asyncio

    asyncio.run(run_worker())
