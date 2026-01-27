"""
ERPX AI Accounting - Event Bus / Outbox
=======================================
PR-11: Transactional outbox pattern for reliable event delivery.

Event Types:
- job.created, job.completed, job.failed
- proposal.approved, proposal.rejected
- ledger.posted
"""

import json
import logging
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

logger = logging.getLogger("erpx.outbox")


class EventType(str, Enum):
    """Supported event types."""

    JOB_CREATED = "job.created"
    JOB_COMPLETED = "job.completed"
    JOB_FAILED = "job.failed"
    PROPOSAL_APPROVED = "proposal.approved"
    PROPOSAL_REJECTED = "proposal.rejected"
    LEDGER_POSTED = "ledger.posted"


class AggregateType(str, Enum):
    """Aggregate types."""

    JOB = "job"
    PROPOSAL = "proposal"
    APPROVAL = "approval"
    LEDGER = "ledger"


class EventStatus(str, Enum):
    """Event delivery status."""

    PENDING = "pending"
    PROCESSING = "processing"
    DELIVERED = "delivered"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"


class DeliveryType(str, Enum):
    """Subscription delivery types."""

    WEBHOOK = "webhook"
    TEMPORAL = "temporal"
    INTERNAL = "internal"


# ===========================================================================
# Event Publishing
# ===========================================================================


async def publish_event(
    conn,
    event_type: EventType,
    aggregate_type: AggregateType,
    aggregate_id: str,
    payload: dict,
    tenant_id: str | None = None,
    request_id: str | None = None,
    scheduled_at: datetime | None = None,
) -> str:
    """
    Publish event to outbox.

    Should be called within the same transaction as the business operation.
    PR19: Idempotent - duplicate events for ledger.posted are ignored.

    Args:
        conn: asyncpg connection (should be in transaction)
        event_type: Type of event
        aggregate_type: Type of entity that emitted the event
        aggregate_id: ID of the entity
        payload: Event payload
        tenant_id: Tenant ID
        request_id: Request ID for tracing
        scheduled_at: When to deliver (default: now)

    Returns:
        Event ID
    """
    event_id = uuid.uuid4()
    schedule = scheduled_at or datetime.utcnow()

    # PR19: Check if event already exists (idempotency for ledger.posted)
    if event_type == EventType.LEDGER_POSTED:
        existing = await conn.fetchrow(
            """
            SELECT id FROM outbox_events 
            WHERE aggregate_type = $1 AND aggregate_id = $2 AND event_type = $3
            """,
            aggregate_type.value,
            aggregate_id,
            event_type.value,
        )
        if existing:
            logger.info(
                f"[{request_id}] [PR19] Event {event_type.value} for {aggregate_type.value}:{aggregate_id} already exists (idempotent)"
            )
            return str(existing["id"])

    try:
        await conn.execute(
            """
            INSERT INTO outbox_events
            (id, event_type, aggregate_type, aggregate_id, payload, 
             tenant_id, request_id, scheduled_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7::text, $8)
            """,
            event_id,
            event_type.value,
            aggregate_type.value,
            aggregate_id,
            json.dumps(payload),
            uuid.UUID(tenant_id) if tenant_id and len(str(tenant_id)) > 10 else None,
            request_id,
            schedule,
        )
    except Exception as e:
        # PR19: Handle unique constraint violation (race condition)
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            logger.info(f"[{request_id}] [PR19] Event constraint violation (idempotent)")
            existing = await conn.fetchrow(
                """
                SELECT id FROM outbox_events 
                WHERE aggregate_type = $1 AND aggregate_id = $2 AND event_type = $3
                """,
                aggregate_type.value,
                aggregate_id,
                event_type.value,
            )
            if existing:
                return str(existing["id"])
        raise

    logger.info(f"[{request_id}] Published event {event_type.value} for {aggregate_type.value}:{aggregate_id}")
    return str(event_id)


async def get_pending_events(
    conn,
    limit: int = 100,
    max_attempts: int = 5,
) -> list[dict]:
    """
    Get pending events for delivery.

    Used by the outbox worker to fetch events to process.
    """
    rows = await conn.fetch(
        """
        SELECT * FROM outbox_events
        WHERE status IN ('pending', 'failed')
        AND scheduled_at <= NOW()
        AND attempts < $1
        ORDER BY scheduled_at ASC
        LIMIT $2
        FOR UPDATE SKIP LOCKED
        """,
        max_attempts,
        limit,
    )

    return [
        {
            "id": str(row["id"]),
            "event_type": row["event_type"],
            "aggregate_type": row["aggregate_type"],
            "aggregate_id": row["aggregate_id"],
            "payload": row["payload"] if isinstance(row["payload"], dict) else json.loads(row["payload"] or "{}"),
            "tenant_id": str(row["tenant_id"]) if row["tenant_id"] else None,
            "status": row["status"],
            "attempts": row["attempts"],
            "request_id": row["request_id"],
        }
        for row in rows
    ]


async def mark_event_processing(conn, event_id: str, request_id: str | None = None):
    """Mark event as being processed."""
    await conn.execute(
        """
        UPDATE outbox_events
        SET status = 'processing',
            last_attempt_at = NOW(),
            attempts = attempts + 1
        WHERE id = $1
        """,
        uuid.UUID(event_id),
    )
    logger.debug(f"[{request_id}] Event {event_id} marked as processing")


async def mark_event_delivered(conn, event_id: str, request_id: str | None = None):
    """Mark event as successfully delivered."""
    await conn.execute(
        """
        UPDATE outbox_events
        SET status = 'delivered',
            delivered_at = NOW()
        WHERE id = $1
        """,
        uuid.UUID(event_id),
    )
    logger.info(f"[{request_id}] Event {event_id} delivered")


async def mark_event_failed(
    conn,
    event_id: str,
    error: str,
    request_id: str | None = None,
):
    """Mark event as failed (will retry)."""
    await conn.execute(
        """
        UPDATE outbox_events
        SET status = 'failed',
            last_error = $1
        WHERE id = $2
        """,
        error,
        uuid.UUID(event_id),
    )
    logger.warning(f"[{request_id}] Event {event_id} failed: {error}")


async def move_to_dead_letter(
    conn,
    event_id: str,
    failure_reason: str,
    request_id: str | None = None,
):
    """Move event to dead letter queue after max retries."""
    # Get event details
    event = await conn.fetchrow(
        "SELECT * FROM outbox_events WHERE id = $1",
        uuid.UUID(event_id),
    )

    if not event:
        logger.error(f"[{request_id}] Event not found: {event_id}")
        return

    # Insert into dead letter queue
    await conn.execute(
        """
        INSERT INTO dead_letter_events
        (original_event_id, event_type, aggregate_type, aggregate_id, 
         payload, failure_reason, total_attempts, tenant_id)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        """,
        uuid.UUID(event_id),
        event["event_type"],
        event["aggregate_type"],
        event["aggregate_id"],
        event["payload"],
        failure_reason,
        event["attempts"],
        event["tenant_id"],
    )

    # Update original event
    await conn.execute(
        "UPDATE outbox_events SET status = 'dead_letter' WHERE id = $1",
        uuid.UUID(event_id),
    )

    logger.error(f"[{request_id}] Event {event_id} moved to dead letter: {failure_reason}")


# ===========================================================================
# Event Subscriptions
# ===========================================================================


async def get_subscriptions_for_event(conn, event_type: str) -> list[dict]:
    """Get active subscriptions for an event type."""
    rows = await conn.fetch(
        """
        SELECT * FROM event_subscriptions
        WHERE is_active = TRUE
        AND $1 = ANY(event_types)
        """,
        event_type,
    )

    return [
        {
            "id": str(row["id"]),
            "name": row["name"],
            "delivery_type": row["delivery_type"],
            "delivery_config": row["delivery_config"]
            if isinstance(row["delivery_config"], dict)
            else json.loads(row["delivery_config"] or "{}"),
            "rate_limit_per_minute": row["rate_limit_per_minute"],
        }
        for row in rows
    ]


async def log_delivery_attempt(
    conn,
    event_id: str,
    subscription_id: str | None,
    attempt_number: int,
    status: str,
    response_code: int | None = None,
    response_body: str | None = None,
    response_time_ms: int | None = None,
    error_message: str | None = None,
):
    """Log event delivery attempt."""
    await conn.execute(
        """
        INSERT INTO event_deliveries
        (event_id, subscription_id, attempt_number, status, 
         response_code, response_body, response_time_ms, error_message)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        """,
        uuid.UUID(event_id),
        uuid.UUID(subscription_id) if subscription_id else None,
        attempt_number,
        status,
        response_code,
        response_body[:4000] if response_body else None,
        response_time_ms,
        error_message,
    )


async def log_delivery_attempts_batch(conn, attempts: list[dict]):
    """
    Batch log event delivery attempts.

    Args:
        conn: Database connection
        attempts: List of dicts containing:
            - event_id
            - subscription_id
            - attempt_number
            - status
            - response_code (optional)
            - response_body (optional)
            - response_time_ms (optional)
            - error_message (optional)
    """
    if not attempts:
        return

    # Unpack data for bulk insert
    event_ids = []
    sub_ids = []
    nums = []
    statuses = []
    codes = []
    bodies = []
    times = []
    errors = []

    for a in attempts:
        eid = a["event_id"]
        event_ids.append(eid if isinstance(eid, uuid.UUID) else uuid.UUID(str(eid)))

        sid = a.get("subscription_id")
        if sid:
            sub_ids.append(sid if isinstance(sid, uuid.UUID) else uuid.UUID(str(sid)))
        else:
            sub_ids.append(None)

        nums.append(a["attempt_number"])
        statuses.append(a["status"])
        codes.append(a.get("response_code"))

        body = a.get("response_body")
        bodies.append(body[:4000] if body else None)

        times.append(a.get("response_time_ms"))
        errors.append(a.get("error_message"))

    await conn.execute(
        """
        INSERT INTO event_deliveries
        (event_id, subscription_id, attempt_number, status,
         response_code, response_body, response_time_ms, error_message)
        SELECT * FROM UNNEST(
            $1::uuid[],
            $2::uuid[],
            $3::int[],
            $4::text[],
            $5::int[],
            $6::text[],
            $7::int[],
            $8::text[]
        )
        """,
        event_ids,
        sub_ids,
        nums,
        statuses,
        codes,
        bodies,
        times,
        errors,
    )


# ===========================================================================
# Convenience Functions for Common Events
# ===========================================================================


async def emit_job_created(
    conn,
    job_id: str,
    tenant_id: str | None = None,
    file_info: dict | None = None,
    request_id: str | None = None,
) -> str:
    """Emit job.created event."""
    return await publish_event(
        conn,
        EventType.JOB_CREATED,
        AggregateType.JOB,
        job_id,
        {
            "job_id": job_id,
            "tenant_id": tenant_id,
            "file_info": file_info or {},
            "timestamp": datetime.utcnow().isoformat(),
        },
        tenant_id=tenant_id,
        request_id=request_id,
    )


async def emit_job_completed(
    conn,
    job_id: str,
    tenant_id: str | None = None,
    proposal_id: str | None = None,
    confidence: float | None = None,
    request_id: str | None = None,
) -> str:
    """Emit job.completed event."""
    return await publish_event(
        conn,
        EventType.JOB_COMPLETED,
        AggregateType.JOB,
        job_id,
        {
            "job_id": job_id,
            "tenant_id": tenant_id,
            "proposal_id": proposal_id,
            "confidence": confidence,
            "timestamp": datetime.utcnow().isoformat(),
        },
        tenant_id=tenant_id,
        request_id=request_id,
    )


async def emit_job_failed(
    conn,
    job_id: str,
    error: str,
    tenant_id: str | None = None,
    request_id: str | None = None,
) -> str:
    """Emit job.failed event."""
    return await publish_event(
        conn,
        EventType.JOB_FAILED,
        AggregateType.JOB,
        job_id,
        {
            "job_id": job_id,
            "tenant_id": tenant_id,
            "error": error,
            "timestamp": datetime.utcnow().isoformat(),
        },
        tenant_id=tenant_id,
        request_id=request_id,
    )


async def emit_proposal_approved(
    conn,
    approval_id: str,
    proposal_id: str,
    approver: str,
    tenant_id: str | None = None,
    request_id: str | None = None,
) -> str:
    """Emit proposal.approved event."""
    return await publish_event(
        conn,
        EventType.PROPOSAL_APPROVED,
        AggregateType.APPROVAL,
        approval_id,
        {
            "approval_id": approval_id,
            "proposal_id": proposal_id,
            "approver": approver,
            "tenant_id": tenant_id,
            "timestamp": datetime.utcnow().isoformat(),
        },
        tenant_id=tenant_id,
        request_id=request_id,
    )


async def emit_ledger_posted(
    conn,
    ledger_id: str,
    proposal_id: str,
    entry_number: str,
    tenant_id: str | None = None,
    request_id: str | None = None,
) -> str:
    """Emit ledger.posted event."""
    return await publish_event(
        conn,
        EventType.LEDGER_POSTED,
        AggregateType.LEDGER,
        ledger_id,
        {
            "ledger_id": ledger_id,
            "proposal_id": proposal_id,
            "entry_number": entry_number,
            "tenant_id": tenant_id,
            "timestamp": datetime.utcnow().isoformat(),
        },
        tenant_id=tenant_id,
        request_id=request_id,
    )


# ===========================================================================
# Outbox Stats
# ===========================================================================


async def get_outbox_stats(conn) -> dict:
    """Get outbox event statistics."""
    row = await conn.fetchrow(
        """
        SELECT 
            COUNT(*) FILTER (WHERE status = 'pending') as pending,
            COUNT(*) FILTER (WHERE status = 'processing') as processing,
            COUNT(*) FILTER (WHERE status = 'delivered') as delivered,
            COUNT(*) FILTER (WHERE status = 'failed') as failed,
            COUNT(*) FILTER (WHERE status = 'dead_letter') as dead_letter,
            COUNT(*) as total
        FROM outbox_events
        """
    )

    dlq_count = await conn.fetchval("SELECT COUNT(*) FROM dead_letter_events WHERE status = 'unresolved'")

    return {
        "pending": row["pending"],
        "processing": row["processing"],
        "delivered": row["delivered"],
        "failed": row["failed"],
        "dead_letter": row["dead_letter"],
        "total": row["total"],
        "dlq_unresolved": dlq_count,
    }
