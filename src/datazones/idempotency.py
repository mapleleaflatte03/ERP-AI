"""
ERPX AI Accounting - Idempotency Service
========================================
PR-10: Request deduplication and idempotent processing.

Features:
- Idempotency key management
- Document checksum deduplication
- Job state tracking for resume
"""

import hashlib
import json
import logging
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

logger = logging.getLogger("erpx.idempotency")


class IdempotencyStatus(str, Enum):
    """Idempotency key status."""

    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class JobState(str, Enum):
    """Job processing state."""

    UPLOADED = "uploaded"
    EXTRACTING = "extracting"
    EXTRACTED = "extracted"
    PROPOSING = "proposing"
    PROPOSED = "proposed"
    APPROVING = "approving"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    POSTING = "posting"
    COMPLETED = "completed"
    FAILED = "failed"


def compute_checksum(content: bytes) -> str:
    """Compute SHA256 checksum of content."""
    return hashlib.sha256(content).hexdigest()


def compute_request_hash(body: dict) -> str:
    """Compute hash of request body for validation."""
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()


# ===========================================================================
# Idempotency Keys
# ===========================================================================


async def get_idempotency_key(conn, key: str) -> dict | None:
    """
    Get existing idempotency key record.

    Returns cached response if completed, or processing status.
    """
    row = await conn.fetchrow(
        """
        SELECT * FROM idempotency_keys
        WHERE idempotency_key = $1 AND expires_at > NOW()
        """,
        key,
    )

    if not row:
        return None

    return {
        "id": str(row["id"]),
        "idempotency_key": row["idempotency_key"],
        "operation": row["operation"],
        "job_id": row["job_id"],
        "status": row["status"],
        "response_code": row["response_code"],
        "response_body": row["response_body"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "completed_at": row["completed_at"].isoformat() if row["completed_at"] else None,
    }


async def create_idempotency_key(
    conn,
    key: str,
    operation: str,
    job_id: str | None = None,
    tenant_id: str | None = None,
    request_hash: str | None = None,
    request_id: str | None = None,
    ttl_hours: int = 24,
) -> str:
    """
    Create new idempotency key record.

    Returns key ID, or raises if key already exists.
    """
    key_id = uuid.uuid4()
    expires_at = datetime.utcnow() + timedelta(hours=ttl_hours)

    try:
        await conn.execute(
            """
            INSERT INTO idempotency_keys
            (id, idempotency_key, tenant_id, operation, job_id, status,
             expires_at, request_hash, request_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """,
            key_id,
            key,
            uuid.UUID(tenant_id) if tenant_id and len(str(tenant_id)) > 10 else None,
            operation,
            job_id,
            IdempotencyStatus.PROCESSING.value,
            expires_at,
            request_hash,
            request_id,
        )
        logger.info(f"[{request_id}] Created idempotency key: {key}")
        return str(key_id)

    except Exception as e:
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            logger.warning(f"[{request_id}] Idempotency key already exists: {key}")
            raise ValueError(f"Duplicate request with key: {key}")
        raise


async def complete_idempotency_key(
    conn,
    key: str,
    status: IdempotencyStatus,
    response_code: int,
    response_body: dict | None = None,
    request_id: str | None = None,
):
    """Update idempotency key with response."""
    await conn.execute(
        """
        UPDATE idempotency_keys
        SET status = $1,
            response_code = $2,
            response_body = $3,
            completed_at = NOW()
        WHERE idempotency_key = $4
        """,
        status.value,
        response_code,
        json.dumps(response_body) if response_body else None,
        key,
    )
    logger.info(f"[{request_id}] Completed idempotency key: {key} with status {status.value}")


# ===========================================================================
# Document Checksums
# ===========================================================================


async def check_document_duplicate(
    conn,
    checksum: str,
    file_size: int,
    tenant_id: str | None = None,
) -> dict | None:
    """
    Check if document was already processed.

    Returns existing job info if duplicate, None if new.
    """
    query = """
        SELECT * FROM document_checksums
        WHERE file_checksum = $1 AND file_size = $2
    """
    params = [checksum, file_size]

    if tenant_id:
        query += " AND (tenant_id IS NULL OR tenant_id = $3)"
        params.append(uuid.UUID(tenant_id) if len(str(tenant_id)) > 10 else None)

    row = await conn.fetchrow(query, *params)

    if not row:
        return None

    return {
        "id": str(row["id"]),
        "file_checksum": row["file_checksum"],
        "first_job_id": row["first_job_id"],
        "document_id": str(row["document_id"]) if row["document_id"] else None,
        "duplicate_count": row["duplicate_count"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }


async def register_document_checksum(
    conn,
    checksum: str,
    file_size: int,
    job_id: str,
    tenant_id: str | None = None,
    document_id: str | None = None,
    filename: str | None = None,
    content_type: str | None = None,
    request_id: str | None = None,
) -> str:
    """
    Register new document checksum.

    Returns checksum record ID.
    """
    checksum_id = uuid.uuid4()

    await conn.execute(
        """
        INSERT INTO document_checksums
        (id, tenant_id, file_checksum, file_size, filename, content_type,
         first_job_id, document_id)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        ON CONFLICT (file_checksum, tenant_id) DO UPDATE
        SET last_seen_at = NOW(),
            duplicate_count = document_checksums.duplicate_count + 1
        """,
        checksum_id,
        uuid.UUID(tenant_id) if tenant_id and len(str(tenant_id)) > 10 else None,
        checksum,
        file_size,
        filename,
        content_type,
        job_id,
        uuid.UUID(document_id) if document_id else None,
    )

    logger.info(f"[{request_id}] Registered document checksum: {checksum[:16]}...")
    return str(checksum_id)


# ===========================================================================
# Job Processing State
# ===========================================================================


async def get_job_state(conn, job_id: str) -> dict | None:
    """Get current job processing state."""
    row = await conn.fetchrow(
        "SELECT * FROM job_processing_state WHERE job_id = $1",
        job_id,
    )

    if not row:
        return None

    return {
        "id": str(row["id"]),
        "job_id": row["job_id"],
        "current_state": row["current_state"],
        "previous_state": row["previous_state"],
        "checkpoint_data": row["checkpoint_data"],
        "attempts": row["attempts"],
        "max_attempts": row["max_attempts"],
        "last_error": row["last_error"],
        "state_changed_at": row["state_changed_at"].isoformat() if row["state_changed_at"] else None,
    }


async def create_job_state(
    conn,
    job_id: str,
    initial_state: JobState = JobState.UPLOADED,
    tenant_id: str | None = None,
    request_id: str | None = None,
) -> str:
    """Create initial job state."""
    state_id = uuid.uuid4()

    await conn.execute(
        """
        INSERT INTO job_processing_state
        (id, job_id, tenant_id, current_state, request_id)
        VALUES ($1, $2, $3, $4, $5::text)
        ON CONFLICT (job_id) DO NOTHING
        """,
        state_id,
        job_id,
        uuid.UUID(tenant_id) if tenant_id and len(str(tenant_id)) > 10 else None,
        initial_state.value,
        request_id,
    )

    logger.info(f"[{request_id}] Created job state: {job_id} = {initial_state.value}")
    return str(state_id)


async def update_job_state(
    conn,
    job_id: str,
    new_state: JobState,
    checkpoint_data: dict | None = None,
    error: str | None = None,
    request_id: str | None = None,
) -> bool:
    """
    Update job processing state.

    Returns True if updated, False if job not found.
    """
    # Get current state
    current = await get_job_state(conn, job_id)

    if not current:
        logger.warning(f"[{request_id}] Job state not found: {job_id}")
        return False

    await conn.execute(
        """
        UPDATE job_processing_state
        SET current_state = $1,
            previous_state = $2,
            checkpoint_data = COALESCE($3::jsonb, checkpoint_data),
            last_error = $4::text,
            attempts = CASE WHEN $4::text IS NOT NULL THEN attempts + 1 ELSE attempts END,
            state_changed_at = NOW(),
            updated_at = NOW(),
            request_id = $5::text
        WHERE job_id = $6
        """,
        new_state.value,
        current["current_state"],
        json.dumps(checkpoint_data) if checkpoint_data else None,
        error,
        request_id,
        job_id,
    )

    logger.info(f"[{request_id}] Updated job state: {job_id} {current['current_state']} -> {new_state.value}")
    return True


async def can_retry_job(conn, job_id: str) -> bool:
    """Check if job can be retried based on attempt count."""
    state = await get_job_state(conn, job_id)
    if not state:
        return True

    return state["attempts"] < state["max_attempts"]
