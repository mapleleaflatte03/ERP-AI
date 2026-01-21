"""
ERPX AI Accounting - Audit & Evidence Store
============================================
PR-7: Complete audit trail for compliance & traceability.

Stores:
- Raw file references
- Extracted text
- LLM inputs/outputs
- Validation results
- Decision chain
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Any

logger = logging.getLogger("erpx.audit")

# Max lengths for truncation (PII protection + storage efficiency)
MAX_EXTRACTED_TEXT_PREVIEW = 4000  # 4KB
MAX_LLM_INPUT_PREVIEW = 2000  # 2KB
MAX_LLM_OUTPUT_RAW = 8000  # 8KB


def truncate_text(text: str | None, max_length: int) -> str:
    """Truncate text to max length with ellipsis."""
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


async def create_audit_evidence(
    conn,
    job_id: str,
    tenant_id: str,
    request_id: str | None = None,
    document_id: str | None = None,
    raw_file_uri: str | None = None,
    extracted_text: str | None = None,
    extracted_text_uri: str | None = None,
    prompt_version: str = "v1",
    model_name: str | None = None,
    llm_stage: str | None = None,
    llm_input: str | None = None,
    llm_output_json: dict | None = None,
    llm_output_raw: str | None = None,
    llm_latency_ms: int | None = None,
    validation_errors: list | None = None,
    risk_flags: list | None = None,
    decision: str = "proposed",
    decision_reason: str | None = None,
) -> str:
    """
    Create audit evidence record for a job.

    Args:
        conn: asyncpg connection
        job_id: Job UUID
        tenant_id: Tenant identifier
        request_id: Request ID for tracing
        document_id: Document UUID
        raw_file_uri: MinIO path to original file
        extracted_text: Full extracted text (will be truncated for preview)
        extracted_text_uri: MinIO path to full extracted text
        prompt_version: Version of prompt template used
        model_name: LLM model name
        llm_stage: Parse stage (direct/extract/repair/self_fix)
        llm_input: LLM prompt input (will be truncated)
        llm_output_json: Parsed JSON output from LLM
        llm_output_raw: Raw LLM response (will be truncated)
        llm_latency_ms: LLM call latency
        validation_errors: List of validation errors
        risk_flags: List of risk flags
        decision: Decision state (proposed/needs_approval/approved/rejected/posted)
        decision_reason: Reason for decision

    Returns:
        Created evidence UUID
    """
    evidence_id = str(uuid.uuid4())

    # Truncate sensitive/large fields
    extracted_text_preview = truncate_text(extracted_text, MAX_EXTRACTED_TEXT_PREVIEW)
    llm_input_preview = truncate_text(llm_input, MAX_LLM_INPUT_PREVIEW)
    llm_output_raw_truncated = truncate_text(llm_output_raw, MAX_LLM_OUTPUT_RAW)

    await conn.execute(
        """
        INSERT INTO audit_evidence (
            id, job_id, tenant_id, request_id, document_id,
            raw_file_uri, extracted_text_preview, extracted_text_uri,
            prompt_version, model_name, llm_stage,
            llm_input_preview, llm_output_json, llm_output_raw, llm_latency_ms,
            validation_errors, risk_flags, decision, decision_reason
        ) VALUES (
            $1, $2, $3, $4::text, $5,
            $6, $7, $8,
            $9, $10, $11,
            $12, $13, $14, $15,
            $16, $17, $18, $19
        )
        """,
        uuid.UUID(evidence_id),
        uuid.UUID(job_id) if job_id else None,
        tenant_id,
        request_id,
        uuid.UUID(document_id) if document_id else None,
        raw_file_uri,
        extracted_text_preview,
        extracted_text_uri,
        prompt_version,
        model_name,
        llm_stage,
        llm_input_preview,
        json.dumps(llm_output_json) if llm_output_json else None,
        llm_output_raw_truncated,
        llm_latency_ms,
        json.dumps(validation_errors or []),
        json.dumps(risk_flags or []),
        decision,
        decision_reason,
    )

    logger.info(f"[{request_id}] Created audit evidence {evidence_id} for job {job_id}")
    return evidence_id


async def update_audit_decision(
    conn,
    job_id: str,
    decision: str,
    decision_reason: str | None = None,
    request_id: str | None = None,
) -> bool:
    """Update decision in audit evidence."""
    result = await conn.execute(
        """
        UPDATE audit_evidence
        SET decision = $1, decision_reason = $2
        WHERE job_id = $3
        """,
        decision,
        decision_reason,
        uuid.UUID(job_id),
    )
    logger.info(f"[{request_id}] Updated audit decision for job {job_id}: {decision}")
    return True


async def append_audit_event(
    conn,
    job_id: str,
    tenant_id: str,
    event_type: str,
    event_data: dict | None = None,
    actor: str = "system",
    request_id: str | None = None,
) -> str:
    """
    Append event to audit timeline.

    Args:
        conn: asyncpg connection
        job_id: Job UUID
        tenant_id: Tenant identifier
        event_type: Event type (upload/ocr_complete/llm_complete/validate/approve/reject/post)
        event_data: Additional event data
        actor: Who performed the action
        request_id: Request ID for tracing

    Returns:
        Created event UUID
    """
    event_id = str(uuid.uuid4())

    await conn.execute(
        """
        INSERT INTO audit_events (id, job_id, tenant_id, request_id, event_type, event_data, actor)
        VALUES ($1, $2, $3, $4::text, $5, $6, $7)
        """,
        uuid.UUID(event_id),
        uuid.UUID(job_id) if job_id else None,
        tenant_id,
        request_id,
        event_type,
        json.dumps(event_data or {}),
        actor,
    )

    logger.debug(f"[{request_id}] Audit event {event_type} for job {job_id}")
    return event_id


async def get_audit_evidence(conn, job_id: str) -> dict | None:
    """Get audit evidence for a job."""
    row = await conn.fetchrow(
        """
        SELECT 
            id, job_id, tenant_id, request_id, document_id,
            raw_file_uri, extracted_text_preview, extracted_text_uri,
            prompt_version, model_name, llm_stage,
            llm_input_preview, llm_output_json, llm_output_raw, llm_latency_ms,
            validation_errors, risk_flags, decision, decision_reason,
            created_at, updated_at
        FROM audit_evidence
        WHERE job_id = $1
        ORDER BY created_at DESC
        LIMIT 1
        """,
        uuid.UUID(job_id),
    )

    if not row:
        return None

    return {
        "id": str(row["id"]),
        "job_id": str(row["job_id"]),
        "tenant_id": row["tenant_id"],
        "request_id": row["request_id"],
        "document_id": str(row["document_id"]) if row["document_id"] else None,
        "raw_file_uri": row["raw_file_uri"],
        "extracted_text_preview": row["extracted_text_preview"],
        "extracted_text_uri": row["extracted_text_uri"],
        "prompt_version": row["prompt_version"],
        "model_name": row["model_name"],
        "llm_stage": row["llm_stage"],
        "llm_input_preview": row["llm_input_preview"],
        "llm_output_json": row["llm_output_json"],
        "llm_output_raw": row["llm_output_raw"],
        "llm_latency_ms": row["llm_latency_ms"],
        "validation_errors": row["validation_errors"],
        "risk_flags": row["risk_flags"],
        "decision": row["decision"],
        "decision_reason": row["decision_reason"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
    }


async def get_audit_timeline(conn, job_id: str) -> list[dict]:
    """Get audit timeline for a job."""
    rows = await conn.fetch(
        """
        SELECT id, job_id, tenant_id, request_id, event_type, event_data, actor, created_at
        FROM audit_events
        WHERE job_id = $1
        ORDER BY created_at ASC
        """,
        uuid.UUID(job_id),
    )

    return [
        {
            "id": str(row["id"]),
            "job_id": str(row["job_id"]),
            "tenant_id": row["tenant_id"],
            "request_id": row["request_id"],
            "event_type": row["event_type"],
            "event_data": row["event_data"],
            "actor": row["actor"],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        }
        for row in rows
    ]
