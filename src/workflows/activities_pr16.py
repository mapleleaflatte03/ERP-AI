"""
ERPX AI - Temporal Activities (PR16)
=====================================
Activities for document processing workflow.
"""

import asyncio
import logging
import os
import tempfile
from typing import Any

from temporalio import activity

from src.core import config

logger = logging.getLogger("erpx.activities.pr16")


@activity.defn
async def process_job_activity(job_id: str) -> str:
    """
    Activity: Process a document job.

    Steps:
    1. Load document record from DB to get minio_bucket/minio_key
    2. Download raw file from MinIO to temp path
    3. Run full pipeline (same as API process_document_async)
    4. Return terminal state

    Args:
        job_id: The job ID to process

    Returns:
        Terminal state string (completed/waiting_for_approval/failed)
    """
    activity.logger.info(f"[{job_id}] process_job_activity starting")

    try:
        # Get document info from DB
        import asyncpg

        db_url = os.getenv("DATABASE_URL", "postgresql://erpx:erpx_secret@postgres:5432/erpx")
        parts = db_url.replace("postgresql://", "").split("@")
        user_pass = parts[0].split(":")
        host_db = parts[1].split("/")
        host_port = host_db[0].split(":")

        conn = await asyncpg.connect(
            host=host_port[0],
            port=int(host_port[1]) if len(host_port) > 1 else 5432,
            user=user_pass[0],
            password=user_pass[1],
            database=host_db[1],
        )

        # Fetch document record
        doc_row = await conn.fetchrow(
            """
            SELECT d.id, d.tenant_id, d.filename, d.content_type, d.file_size, 
                   d.minio_bucket, d.minio_key, d.checksum, t.code as tenant_code
            FROM documents d
            JOIN tenants t ON d.tenant_id = t.id
            WHERE d.job_id = $1
            """,
            job_id,
        )

        if not doc_row:
            await conn.close()
            raise ValueError(f"Document not found for job_id: {job_id}")

        minio_bucket = doc_row["minio_bucket"]
        minio_key = doc_row["minio_key"]
        filename = doc_row["filename"]
        content_type = doc_row["content_type"]
        file_size = doc_row["file_size"]
        tenant_code = doc_row["tenant_code"]
        checksum = doc_row["checksum"]

        await conn.close()

        if not minio_bucket or not minio_key:
            raise ValueError(f"Document {job_id} has no MinIO location")

        activity.logger.info(f"[{job_id}] Found document: s3://{minio_bucket}/{minio_key}")

        # Download from MinIO to temp file
        from src.storage import download_document

        file_data = download_document(minio_bucket, minio_key)

        # Write to temp file
        file_ext = os.path.splitext(filename)[1] if filename else ".bin"
        with tempfile.NamedTemporaryFile(suffix=file_ext, delete=False) as tmp:
            tmp.write(file_data)
            temp_path = tmp.name

        activity.logger.info(f"[{job_id}] Downloaded {len(file_data)} bytes to {temp_path}")

        # Build file_info dict matching API format
        file_info = {
            "filename": filename,
            "content_type": content_type,
            "size": file_size,
            "checksum": checksum,
            "path": temp_path,
            "tenant_id": tenant_code,
        }

        # Run the pipeline using the shared function
        terminal_state = await run_document_pipeline(job_id, temp_path, file_info)

        # Cleanup temp file
        try:
            os.unlink(temp_path)
        except Exception:
            pass

        activity.logger.info(f"[{job_id}] process_job_activity completed: {terminal_state}")
        return terminal_state

    except Exception as e:
        activity.logger.error(f"[{job_id}] process_job_activity failed: {e}")
        raise


async def run_document_pipeline(job_id: str, file_path: str, file_info: dict[str, Any]) -> str:
    """
    Run the document processing pipeline.
    This is the shared logic used by both API (inline) and Worker (activity).

    Returns terminal state string.
    """
    import time
    import uuid

    import asyncpg

    from src.audit.store import (
        append_audit_event,
        create_audit_evidence,
        update_audit_decision,
    )
    from src.datazones import DataZone, JobState, create_job_state, track_zone_entry, update_job_state
    from src.observability import record_counter, record_latency
    from src.outbox import AggregateType, EventType, publish_event
    from src.policy.engine import evaluate_proposal as policy_evaluate

    request_id = job_id
    tenant_id = file_info.get("tenant_id", "default")
    pipeline_start = time.time()
    conn = None
    tenant_uuid = None

    try:
        logger.info(f"[{request_id}] Worker processing job {job_id}: {file_info.get('filename')}")

        # Get DB connection
        db_url = os.getenv("DATABASE_URL", "postgresql://erpx:erpx_secret@postgres:5432/erpx")
        parts = db_url.replace("postgresql://", "").split("@")
        user_pass = parts[0].split(":")
        host_db = parts[1].split("/")
        host_port = host_db[0].split(":")

        conn = await asyncpg.connect(
            host=host_port[0],
            port=int(host_port[1]) if len(host_port) > 1 else 5432,
            user=user_pass[0],
            password=user_pass[1],
            database=host_db[1],
        )

        # Get tenant
        tenant_row = await conn.fetchrow("SELECT id FROM tenants WHERE code = $1", tenant_id)
        if not tenant_row:
            raise ValueError(f"Tenant not found: {tenant_id}")

        tenant_uuid = tenant_row["id"]
        doc_uuid = uuid.UUID(job_id)

        # PR16: Create job state at start
        await create_job_state(conn, job_id, JobState.UPLOADED, str(tenant_uuid), request_id=request_id)

        # Update job state to processing
        await update_job_state(conn, job_id, JobState.EXTRACTING, request_id=request_id)

        # =========== STEP 1: Extract Text ===========
        from src.api.main import extract_excel, extract_image, extract_pdf

        content_type = file_info.get("content_type", "")
        text = ""
        ocr_start = time.time()

        if "pdf" in content_type:
            text = await extract_pdf(file_path)
        elif "image" in content_type:
            text = await extract_image(file_path)
        elif "spreadsheet" in content_type or "excel" in content_type:
            text = await extract_excel(file_path)
        else:
            with open(file_path, encoding="utf-8", errors="ignore") as f:
                text = f.read()

        ocr_latency_ms = int((time.time() - ocr_start) * 1000)

        if not text:
            raise ValueError("Failed to extract text from document")

        logger.info(f"[{request_id}] Extracted {len(text)} chars in {ocr_latency_ms}ms")

        # Record metrics
        await record_counter(conn, "ocr_calls_total", 1.0, {"tenant": tenant_id})
        await record_latency(conn, "ocr_latency", float(ocr_latency_ms), labels={"tenant": tenant_id})

        # Update state
        await update_job_state(
            conn,
            job_id,
            JobState.EXTRACTED,
            checkpoint_data={"text_length": len(text)},
            request_id=request_id,
        )
        await track_zone_entry(
            conn,
            job_id=job_id,
            zone=DataZone.EXTRACTED,
            tenant_id=str(tenant_uuid),
            document_id=job_id,
            extracted_text_preview=text[:4000],
            byte_count=len(text.encode("utf-8")),
            processing_time_ms=ocr_latency_ms,
            request_id=request_id,
        )
        await append_audit_event(
            conn,
            job_id=job_id,
            tenant_id=str(tenant_uuid),
            event_type="extracted",
            event_data={"text_length": len(text), "ocr_latency_ms": ocr_latency_ms},
            actor="worker",
            request_id=request_id,
        )

        # =========== PR14: Qdrant Embedding ===========
        if config.ENABLE_QDRANT:
            try:
                from src.rag import generate_embedding, get_qdrant_client

                text_for_embedding = text[:4000]
                embedding = generate_embedding(text_for_embedding)
                if embedding:
                    qdrant_client = get_qdrant_client()
                    qdrant_client.upsert_documents(
                        texts=[text_for_embedding],
                        metadatas=[
                            {
                                "job_id": job_id,
                                "tenant_id": str(tenant_uuid),
                                "filename": file_info.get("filename", "unknown"),
                                "doc_type": "invoice",
                                "source": "worker",
                            }
                        ],
                        collection_name="documents_ingested",
                    )
                    logger.info(f"[{request_id}] Qdrant upsert from worker")
            except Exception as e:
                logger.warning(f"[{request_id}] Qdrant failed (non-fatal): {e}")

        # =========== STEP 2: Call LLM ===========
        await update_job_state(conn, job_id, JobState.PROPOSING, request_id=request_id)

        from src.llm import get_llm_client

        llm_client = get_llm_client()
        model_name = llm_client.config.model

        system_prompt = """Bạn là chuyên gia kế toán Việt Nam. Nhiệm vụ:
1. Phân loại hóa đơn (mua hàng/bán hàng/chi phí/khác)
2. Trích xuất thông tin: số HĐ, ngày, nhà cung cấp, tổng tiền, thuế VAT
3. Đề xuất bút toán kế toán theo TT200
4. Giải thích lý do

Trả về JSON với format:
{
    "doc_type": "purchase_invoice|sales_invoice|expense|other",
    "vendor": "tên nhà cung cấp",
    "invoice_no": "số hóa đơn",
    "invoice_date": "YYYY-MM-DD",
    "total_amount": số tiền,
    "vat_amount": tiền thuế,
    "entries": [
        {"account_code": "xxx", "account_name": "tên TK", "debit": số, "credit": số, "description": "mô tả"}
    ],
    "explanation": "giải thích bút toán",
    "confidence": 0.0-1.0,
    "needs_human_review": true/false,
    "risks": ["danh sách rủi ro nếu có"]
}"""

        user_prompt = f"""Phân tích hóa đơn sau và đề xuất bút toán:

---
{text[:4000]}
---

Trả về JSON theo format đã định."""

        llm_start = time.time()
        response = await llm_client.generate_json(
            prompt=user_prompt,
            system=system_prompt,
            temperature=0.2,
            max_tokens=2048,
            request_id=request_id,
            trace_id=job_id,
        )
        llm_latency_ms = int((time.time() - llm_start) * 1000)

        # Record metrics
        await record_counter(conn, "llm_calls_total", 1.0, {"tenant": tenant_id, "model": model_name})
        await record_latency(conn, "llm_latency", float(llm_latency_ms), labels={"tenant": tenant_id})

        response["doc_id"] = job_id
        from src.api.main import validate_proposal

        proposal = validate_proposal(response)

        logger.info(f"[{request_id}] LLM response in {llm_latency_ms}ms, confidence={proposal.get('confidence')}")

        await update_job_state(conn, job_id, JobState.PROPOSED, request_id=request_id)

        await append_audit_event(
            conn,
            job_id=job_id,
            tenant_id=str(tenant_uuid),
            event_type="llm_proposed",
            event_data={
                "model": model_name,
                "llm_latency_ms": llm_latency_ms,
                "confidence": proposal.get("confidence"),
                "doc_type": proposal.get("doc_type"),
            },
            actor="llm",
            request_id=request_id,
        )

        # =========== STEP 3: Policy Evaluation ===========
        policy_result = await policy_evaluate(
            conn,
            proposal=proposal,
            job_id=job_id,
            tenant_id=str(tenant_uuid),
            request_id=request_id,
        )

        await append_audit_event(
            conn,
            job_id=job_id,
            tenant_id=str(tenant_uuid),
            event_type="policy_evaluated",
            event_data={
                "overall_result": policy_result.overall_result.value,
                "auto_approved": policy_result.auto_approved,
                "rules_passed": policy_result.rules_passed,
                "rules_failed": policy_result.rules_failed,
            },
            actor="policy_engine",
            request_id=request_id,
        )

        # Create audit evidence
        await create_audit_evidence(
            conn,
            job_id=job_id,
            tenant_id=str(tenant_uuid),
            request_id=request_id,
            document_id=job_id,
            raw_file_uri=file_info.get("path"),
            extracted_text=text,
            prompt_version="v1",
            model_name=model_name,
            llm_stage="direct",
            llm_input=user_prompt,
            llm_output_json=proposal,
            llm_output_raw=str(response),
            llm_latency_ms=llm_latency_ms,
            validation_errors=proposal.get("risks", []),
            risk_flags=proposal.get("risks", []),
            decision="proposed",
        )

        await track_zone_entry(
            conn,
            job_id=job_id,
            zone=DataZone.PROPOSED,
            tenant_id=str(tenant_uuid),
            document_id=job_id,
            processing_time_ms=llm_latency_ms,
            request_id=request_id,
        )

        # =========== STEP 4: GOVERNANCE GATING ===========
        needs_approval = policy_result.overall_result.value == "requires_review" or not policy_result.auto_approved

        # PR17: Persist proposal data for BOTH paths (so finalize can access it later)
        # We DO NOT post to ledger_entries yet - just extracted_invoices + journal_proposals
        from src.api.main import persist_proposal_only

        proposal_persist_result = await persist_proposal_only(
            conn, job_id, file_info, proposal, str(tenant_uuid), request_id
        )
        proposal_id = proposal_persist_result.get("proposal_id")

        if needs_approval:
            # NEEDS APPROVAL path
            logger.info(f"[{request_id}] Job {job_id} requires approval - NOT posting ledger")

            approval_id = uuid.uuid4()
            await conn.execute(
                """INSERT INTO approvals
                (id, proposal_id, tenant_id, job_id, approver_name, action, status, comments)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8) ON CONFLICT DO NOTHING""",
                approval_id,
                proposal_id,
                tenant_uuid,
                doc_uuid,
                "System",
                "pending",
                "pending",
                f"Pending approval (policy: {policy_result.overall_result.value})",
            )

            await append_audit_event(
                conn,
                job_id,
                str(tenant_uuid),
                "needs_approval",
                {
                    "reason": f"Policy result: {policy_result.overall_result.value}",
                    "rules_failed": policy_result.rules_failed,
                },
                "policy_engine",
                request_id,
            )
            await update_audit_decision(
                conn, job_id, "waiting_approval", policy_result.overall_result.value, request_id
            )
            await update_job_state(conn, job_id, JobState.WAITING_FOR_APPROVAL, request_id=request_id)
            await record_counter(conn, "approvals_pending_total", 1.0, {"tenant": str(tenant_uuid)})

            e2e_latency_ms = int((time.time() - pipeline_start) * 1000)
            await record_latency(conn, "end_to_end_latency", float(e2e_latency_ms), labels={"tenant": str(tenant_uuid)})

            logger.info(f"[{request_id}] Job {job_id} stopped at WAITING_FOR_APPROVAL in {e2e_latency_ms}ms")
            await conn.close()
            return "waiting_for_approval"

        # AUTO APPROVED path
        logger.info(f"[{request_id}] Job {job_id} auto-approved - posting ledger")

        # PR18: Idempotency check - ensure we don't double-post ledger on retry
        existing_ledger = await conn.fetchrow(
            """
            SELECT le.id FROM ledger_entries le
            JOIN journal_proposals jp ON le.proposal_id = jp.id
            JOIN extracted_invoices ei ON jp.invoice_id = ei.id
            JOIN documents d ON ei.document_id = d.id
            WHERE d.job_id = $1
            """,
            job_id,
        )

        if existing_ledger:
            logger.info(f"[{request_id}] [PR18] Job {job_id} already posted to ledger (idempotent skip)")
            # Just update state to completed and return
            await update_job_state(conn, job_id, JobState.COMPLETED, request_id=request_id)
            await conn.close()
            return "completed"

        await append_audit_event(
            conn,
            job_id,
            str(tenant_uuid),
            "auto_approved",
            {"reason": "Policy rules passed", "rules_passed": policy_result.rules_passed},
            "policy_engine",
            request_id,
        )
        await record_counter(conn, "auto_approved_total", 1.0, {"tenant": str(tenant_uuid)})
        await update_audit_decision(conn, job_id, "auto_approved", "Policy rules passed", request_id)

        # =========== STEP 5: Persist to Golden Tables ===========
        await update_job_state(conn, job_id, JobState.POSTING, request_id=request_id)

        from src.api.main import persist_to_db_with_conn

        persist_result = await persist_to_db_with_conn(conn, job_id, file_info, proposal, str(tenant_uuid), request_id)

        await track_zone_entry(
            conn,
            job_id=job_id,
            zone=DataZone.POSTED,
            tenant_id=str(tenant_uuid),
            document_id=job_id,
            proposal_id=persist_result.get("proposal_id"),
            ledger_entry_id=persist_result.get("ledger_id"),
            request_id=request_id,
        )

        # =========== STEP 6: Emit Outbox Event ===========
        await publish_event(
            conn,
            event_type=EventType.LEDGER_POSTED,
            aggregate_type=AggregateType.LEDGER,
            aggregate_id=persist_result.get("ledger_id", job_id),
            payload={
                "job_id": job_id,
                "proposal_id": persist_result.get("proposal_id"),
                "ledger_entry_id": persist_result.get("ledger_id"),
                "invoice_no": proposal.get("invoice_no"),
                "vendor": proposal.get("vendor"),
                "total_amount": proposal.get("total_amount"),
                "currency": "VND",
            },
            tenant_id=str(tenant_uuid),
            request_id=request_id,
        )

        await record_counter(conn, "ledger_posted_total", 1.0, {"tenant": str(tenant_uuid)})
        await append_audit_event(
            conn,
            job_id,
            str(tenant_uuid),
            "posted_to_ledger",
            {"ledger_id": persist_result.get("ledger_id"), "entry_number": persist_result.get("entry_number")},
            "worker",
            request_id,
        )

        # =========== STEP 7: Complete ===========
        await update_job_state(conn, job_id, JobState.COMPLETED, request_id=request_id)

        e2e_latency_ms = int((time.time() - pipeline_start) * 1000)
        await record_latency(conn, "end_to_end_latency", float(e2e_latency_ms), labels={"tenant": str(tenant_uuid)})

        await append_audit_event(
            conn,
            job_id,
            str(tenant_uuid),
            "completed",
            {"e2e_latency_ms": e2e_latency_ms, "doc_type": proposal.get("doc_type")},
            "worker",
            request_id,
        )

        logger.info(f"[{request_id}] Job {job_id} completed in {e2e_latency_ms}ms")
        await conn.close()
        return "completed"

    except Exception as e:
        logger.error(f"[{request_id}] Job {job_id} failed: {e}", exc_info=True)

        if conn:
            try:
                t_id = str(tenant_uuid) if tenant_uuid else tenant_id
                await update_job_state(conn, job_id, JobState.FAILED, error=str(e), request_id=request_id)
                await append_audit_event(
                    conn,
                    job_id,
                    t_id,
                    "failed",
                    {"error": str(e)[:1000]},
                    "worker",
                    request_id,
                )
                await update_audit_decision(conn, job_id, "failed", str(e)[:500], request_id)
            except Exception:
                pass
            await conn.close()

        raise
