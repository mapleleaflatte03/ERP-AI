"""
ERPX AI Accounting - Evidence / Audit Trail
===========================================
Centralized logging for all critical agent actions.
"""
import logging
import json
import uuid
from datetime import datetime
from src.db import get_pool

logger = logging.getLogger(__name__)

async def write_evidence(
    document_id: str,
    stage: str,
    output_summary: dict | str,
    decision: str = "info",  # approved, rejected, info, error
    job_id: str | None = None,
    trace_id: str | None = None,
    input_preview: str | None = None,
    action: str | None = None,
    tenant_id: str | None = None,
):
    """
    Write an evidence record to the audit_evidence table.
    """
    try:
        pool = await get_pool()
        if not pool:
            logger.error("DB Pool unavailable for writing evidence")
            return

        if isinstance(output_summary, dict):
            if action:
                output_summary["action"] = action
            output_summary = json.dumps(output_summary, ensure_ascii=False)

        async with pool.acquire() as conn:
            # Ensure UUIDs
            doc_uuid = uuid.UUID(str(document_id)) if document_id else None
            job_uuid = uuid.UUID(str(job_id)) if job_id else (doc_uuid if doc_uuid else None)

            # Ensure tenant_id (DB requires not null)
            final_tenant = str(tenant_id) if tenant_id else "default"

            await conn.execute(
                """
                INSERT INTO audit_evidence (
                    id, 
                    document_id, 
                    job_id, 
                    tenant_id,
                    llm_stage, 
                    decision, 
                    llm_input_preview, 
                    llm_output_raw, 
                    created_at, 
                    updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW(), NOW())
                """,
                str(uuid.uuid4()),
                doc_uuid,
                job_uuid,
                final_tenant,
                stage,
                decision,
                input_preview,
                output_summary
            )
            logger.info(f"Evidence written for doc {document_id} stage {stage}")

    except Exception as e:
        logger.error(f"Failed to write evidence: {e}")
