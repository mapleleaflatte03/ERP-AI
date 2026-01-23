"""
ERPX AI - Finalize Activities (PR17)
====================================
Activities for finalizing job after manual approval/rejection.
These run after the workflow receives approval signal.
"""

import logging
import os
import time
import uuid
from typing import Any

from temporalio import activity

logger = logging.getLogger("erpx.activities.pr17")


@activity.defn
async def finalize_posting_activity(job_id: str) -> str:
    """
    Finalize posting after manual approval.
    
    This activity:
    1. Loads the proposal from DB
    2. Posts to ledger + outbox (idempotent)
    3. Updates job state to completed
    4. Updates audit decision
    
    Returns "completed" on success.
    """
    import asyncpg
    
    from src.audit.store import append_audit_event, update_audit_decision
    from src.datazones import DataZone, JobState, track_zone_entry, update_job_state
    from src.observability import record_counter
    from src.outbox import AggregateType, EventType, publish_event
    
    request_id = job_id
    activity.logger.info(f"[{job_id}] finalize_posting_activity starting")
    
    conn = None
    try:
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
        
        # Get document info
        doc_row = await conn.fetchrow(
            "SELECT tenant_id FROM documents WHERE job_id = $1", job_id
        )
        if not doc_row:
            raise ValueError(f"Document not found for job_id: {job_id}")
        
        tenant_uuid = doc_row["tenant_id"]
        
        # Check if ledger already posted (idempotent)
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
            activity.logger.info(f"[{job_id}] Ledger already posted, skipping")
            # Just update state to completed
            await update_job_state(conn, job_id, JobState.COMPLETED, request_id=request_id)
            await conn.close()
            return "completed"
        
        # Get proposal for posting
        proposal_row = await conn.fetchrow(
            """
            SELECT jp.*, ei.vendor_name, ei.invoice_number, ei.total_amount, ei.currency,
                   ei.invoice_date, ei.tax_amount, ei.subtotal
            FROM journal_proposals jp
            JOIN extracted_invoices ei ON jp.invoice_id = ei.id
            JOIN documents d ON ei.document_id = d.id
            WHERE d.job_id = $1
            ORDER BY jp.created_at DESC
            LIMIT 1
            """,
            job_id,
        )
        
        if not proposal_row:
            raise ValueError(f"No proposal found for job_id: {job_id}")
        
        proposal_id = proposal_row["id"]
        
        # Build proposal dict for persist
        proposal = {
            "vendor": proposal_row["vendor_name"],
            "invoice_no": proposal_row["invoice_number"],
            "total_amount": float(proposal_row["total_amount"]) if proposal_row["total_amount"] else 0,
            "currency": proposal_row["currency"] or "VND",
            "invoice_date": str(proposal_row["invoice_date"]) if proposal_row["invoice_date"] else None,
            "tax_amount": float(proposal_row["tax_amount"]) if proposal_row["tax_amount"] else 0,
            "subtotal": float(proposal_row["subtotal"]) if proposal_row["subtotal"] else 0,
            "doc_type": "invoice",
        }
        
        activity.logger.info(f"[{job_id}] Posting to ledger after manual approval")
        
        # Update audit decision
        await update_audit_decision(conn, job_id, "approved_manual", "Manual approval by user", request_id)
        
        await append_audit_event(
            conn, job_id, str(tenant_uuid), "manual_approved",
            {"reason": "Human approval via API"},
            "user", request_id,
        )
        
        # Update job state to posting
        await update_job_state(conn, job_id, JobState.POSTING, request_id=request_id)
        
        # Persist to ledger
        from src.api.main import persist_to_db_with_conn
        
        file_info = {"tenant_id": str(tenant_uuid)}
        persist_result = await persist_to_db_with_conn(
            conn, job_id, file_info, proposal, str(tenant_uuid), request_id
        )
        
        # Track zone
        await track_zone_entry(
            conn, job_id=job_id, zone=DataZone.POSTED, tenant_id=str(tenant_uuid),
            document_id=job_id, proposal_id=str(proposal_id),
            ledger_entry_id=persist_result.get("ledger_id"), request_id=request_id,
        )
        
        # Publish outbox event
        await publish_event(
            conn, event_type=EventType.LEDGER_POSTED, aggregate_type=AggregateType.LEDGER,
            aggregate_id=persist_result.get("ledger_id", job_id),
            payload={
                "job_id": job_id, "proposal_id": str(proposal_id),
                "ledger_entry_id": persist_result.get("ledger_id"),
                "invoice_no": proposal.get("invoice_no"), "vendor": proposal.get("vendor"),
                "total_amount": proposal.get("total_amount"), "currency": proposal.get("currency"),
                "approval_type": "manual",
            },
            tenant_id=str(tenant_uuid), request_id=request_id,
        )
        
        await record_counter(conn, "ledger_posted_total", 1.0, {"tenant": str(tenant_uuid)})
        await record_counter(conn, "manual_approved_total", 1.0, {"tenant": str(tenant_uuid)})
        
        await append_audit_event(
            conn, job_id, str(tenant_uuid), "posted_to_ledger",
            {"ledger_id": persist_result.get("ledger_id"), "entry_number": persist_result.get("entry_number")},
            "worker", request_id,
        )
        
        # Complete
        await update_job_state(conn, job_id, JobState.COMPLETED, request_id=request_id)
        
        await append_audit_event(
            conn, job_id, str(tenant_uuid), "completed",
            {"approval_type": "manual"},
            "worker", request_id,
        )
        
        activity.logger.info(f"[{job_id}] finalize_posting_activity completed")
        await conn.close()
        return "completed"
        
    except Exception as e:
        activity.logger.error(f"[{job_id}] finalize_posting_activity failed: {e}")
        if conn:
            await conn.close()
        raise


@activity.defn
async def finalize_rejection_activity(job_id: str) -> str:
    """
    Finalize rejection after manual rejection.
    
    This activity:
    1. Updates job state to rejected
    2. Updates audit decision
    
    Returns "rejected" on completion.
    """
    import asyncpg
    
    from src.audit.store import append_audit_event, update_audit_decision
    from src.datazones import JobState, update_job_state
    from src.observability import record_counter
    
    request_id = job_id
    activity.logger.info(f"[{job_id}] finalize_rejection_activity starting")
    
    conn = None
    try:
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
        
        # Get document info
        doc_row = await conn.fetchrow(
            "SELECT tenant_id FROM documents WHERE job_id = $1", job_id
        )
        if not doc_row:
            raise ValueError(f"Document not found for job_id: {job_id}")
        
        tenant_uuid = doc_row["tenant_id"]
        
        # Update audit decision
        await update_audit_decision(conn, job_id, "rejected", "Manual rejection by user", request_id)
        
        await append_audit_event(
            conn, job_id, str(tenant_uuid), "manual_rejected",
            {"reason": "Human rejection via API"},
            "user", request_id,
        )
        
        await record_counter(conn, "manual_rejected_total", 1.0, {"tenant": str(tenant_uuid)})
        
        # Update job state to rejected
        await update_job_state(conn, job_id, JobState.FAILED, error="Rejected by user", request_id=request_id)
        
        await append_audit_event(
            conn, job_id, str(tenant_uuid), "rejected",
            {"approval_type": "manual"},
            "worker", request_id,
        )
        
        activity.logger.info(f"[{job_id}] finalize_rejection_activity completed")
        await conn.close()
        return "rejected"
        
    except Exception as e:
        activity.logger.error(f"[{job_id}] finalize_rejection_activity failed: {e}")
        if conn:
            await conn.close()
        raise
