"""
ERPX AI Accounting - Approval Inbox Service
============================================
PR-8: Approval workflow for journal proposals.

Workflow:
1. Proposal created -> approval pending
2. User approves -> trigger ledger posting
3. User rejects -> mark rejected, no posting
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Any

logger = logging.getLogger("erpx.approval")


async def list_pending_approvals(
    conn,
    tenant_id: str | None = None,
    status: str = "pending",
    limit: int = 50,
) -> list[dict]:
    """
    List approvals with given status.

    Args:
        conn: asyncpg connection
        tenant_id: Filter by tenant (optional)
        status: Filter by status (pending/approved/rejected)
        limit: Max results

    Returns:
        List of approval records with proposal context
    """
    query = """
        SELECT 
            a.id,
            a.proposal_id,
            a.job_id,
            a.tenant_id,
            a.status,
            a.action,
            a.approver_name,
            a.comment,
            a.comments,
            a.created_at,
            a.updated_at,
            jp.ai_confidence,
            jp.ai_model,
            jp.risk_level,
            ei.vendor_name,
            ei.invoice_number,
            ei.total_amount,
            ei.currency
        FROM approvals a
        LEFT JOIN journal_proposals jp ON a.proposal_id = jp.id
        LEFT JOIN extracted_invoices ei ON jp.invoice_id = ei.id
        WHERE (a.action = $1 OR a.status = $1)
    """
    params = [status]

    if tenant_id:
        query += " AND a.tenant_id = $2"
        params.append(uuid.UUID(tenant_id) if isinstance(tenant_id, str) and len(tenant_id) > 10 else tenant_id)

    query += " ORDER BY a.created_at DESC LIMIT $" + str(len(params) + 1)
    params.append(limit)

    rows = await conn.fetch(query, *params)

    return [
        {
            "id": str(row["id"]),
            "proposal_id": str(row["proposal_id"]) if row["proposal_id"] else None,
            "job_id": str(row["job_id"]) if row["job_id"] else None,
            "tenant_id": str(row["tenant_id"]) if row["tenant_id"] else None,
            "status": row["status"] or row["action"],
            "approver_name": row["approver_name"],
            "comment": row["comment"] or row["comments"],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
            "ai_confidence": float(row["ai_confidence"]) if row["ai_confidence"] else None,
            "ai_model": row["ai_model"],
            "risk_level": row["risk_level"],
            "vendor_name": row["vendor_name"],
            "invoice_number": row["invoice_number"],
            "total_amount": float(row["total_amount"]) if row["total_amount"] else None,
            "currency": row["currency"],
        }
        for row in rows
    ]


async def get_approval_by_id(conn, approval_id: str) -> dict | None:
    """Get single approval by ID."""
    row = await conn.fetchrow(
        """
        SELECT 
            a.*,
            jp.document_id,
            jp.ai_confidence,
            jp.ai_model,
            jp.risk_level,
            ei.vendor_name,
            ei.invoice_number,
            ei.total_amount,
            ei.currency
        FROM approvals a
        LEFT JOIN journal_proposals jp ON a.proposal_id = jp.id
        LEFT JOIN extracted_invoices ei ON jp.invoice_id = ei.id
        WHERE a.id = $1
        """,
        uuid.UUID(approval_id),
    )

    if not row:
        return None

    return {
        "id": str(row["id"]),
        "proposal_id": str(row["proposal_id"]) if row["proposal_id"] else None,
        "job_id": str(row["job_id"]) if row.get("job_id") else None,
        "tenant_id": str(row["tenant_id"]) if row["tenant_id"] else None,
        "status": row.get("status") or row.get("action"),
        "approver_name": row["approver_name"],
        "comment": row.get("comment") or row.get("comments"),
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "document_id": str(row["document_id"]) if row.get("document_id") else None,
        "ai_confidence": float(row["ai_confidence"]) if row["ai_confidence"] else None,
        "ai_model": row["ai_model"],
        "risk_level": row["risk_level"],
        "vendor_name": row["vendor_name"],
        "invoice_number": row["invoice_number"],
        "total_amount": float(row["total_amount"]) if row["total_amount"] else None,
        "currency": row["currency"],
    }


async def approve_proposal(
    conn,
    approval_id: str,
    approver: str,
    comment: str | None = None,
    request_id: str | None = None,
) -> dict:
    """
    Approve a proposal and trigger ledger posting.

    Args:
        conn: asyncpg connection
        approval_id: Approval UUID
        approver: Approver name/ID
        comment: Approval comment
        request_id: Request ID for tracing

    Returns:
        Updated approval record
    """
    # Get current approval
    approval = await get_approval_by_id(conn, approval_id)
    if not approval:
        raise ValueError(f"Approval not found: {approval_id}")

    current_status = approval.get("status")
    if current_status not in ["pending", None]:
        raise ValueError(f"Cannot approve: current status is {current_status}")

    # Update approval
    await conn.execute(
        """
        UPDATE approvals
        SET status = 'approved', 
            action = 'approved',
            approver_name = $1, 
            comment = $2,
            approved_at = NOW(),
            updated_at = NOW()
        WHERE id = $3
        """,
        approver,
        comment,
        uuid.UUID(approval_id),
    )

    # Update journal_proposals status
    if approval.get("proposal_id"):
        await conn.execute(
            "UPDATE journal_proposals SET status = 'approved', updated_at = NOW() WHERE id = $1",
            uuid.UUID(approval["proposal_id"]),
        )

    # Trigger ledger posting if not already posted
    proposal_id = approval.get("proposal_id")
    if proposal_id:
        await post_to_ledger(conn, proposal_id, approval_id, approver, request_id)

    logger.info(f"[{request_id}] Approval {approval_id} approved by {approver}")

    return {
        "approval_id": approval_id,
        "status": "approved",
        "approver": approver,
        "comment": comment,
        "ledger_posted": True,
    }


async def reject_proposal(
    conn,
    approval_id: str,
    approver: str,
    comment: str | None = None,
    request_id: str | None = None,
) -> dict:
    """
    Reject a proposal.

    Args:
        conn: asyncpg connection
        approval_id: Approval UUID
        approver: Rejector name/ID
        comment: Rejection reason
        request_id: Request ID for tracing

    Returns:
        Updated approval record
    """
    approval = await get_approval_by_id(conn, approval_id)
    if not approval:
        raise ValueError(f"Approval not found: {approval_id}")

    current_status = approval.get("status")
    if current_status not in ["pending", None]:
        raise ValueError(f"Cannot reject: current status is {current_status}")

    # Update approval
    await conn.execute(
        """
        UPDATE approvals
        SET status = 'rejected', 
            action = 'rejected',
            approver_name = $1, 
            comment = $2,
            approved_at = NOW(),
            updated_at = NOW()
        WHERE id = $3
        """,
        approver,
        comment,
        uuid.UUID(approval_id),
    )

    # Update journal_proposals status
    if approval.get("proposal_id"):
        await conn.execute(
            "UPDATE journal_proposals SET status = 'rejected', updated_at = NOW() WHERE id = $1",
            uuid.UUID(approval["proposal_id"]),
        )

    logger.info(f"[{request_id}] Approval {approval_id} rejected by {approver}")

    return {
        "approval_id": approval_id,
        "status": "rejected",
        "approver": approver,
        "comment": comment,
    }


async def post_to_ledger(
    conn,
    proposal_id: str,
    approval_id: str,
    posted_by: str,
    request_id: str | None = None,
) -> str | None:
    """
    Post approved proposal to ledger.

    Returns:
        Ledger entry ID if created, None if already exists
    """
    # Check if already posted
    existing = await conn.fetchrow(
        "SELECT id FROM ledger_entries WHERE proposal_id = $1",
        uuid.UUID(proposal_id),
    )
    if existing:
        logger.info(f"[{request_id}] Ledger entry already exists for proposal {proposal_id}")
        return str(existing["id"])

    # Get proposal details
    proposal = await conn.fetchrow(
        """
        SELECT jp.*, ei.vendor_name, ei.invoice_number, ei.total_amount, ei.currency
        FROM journal_proposals jp
        LEFT JOIN extracted_invoices ei ON jp.invoice_id = ei.id
        WHERE jp.id = $1
        """,
        uuid.UUID(proposal_id),
    )

    if not proposal:
        logger.error(f"[{request_id}] Proposal not found: {proposal_id}")
        return None

    # Create ledger entry
    ledger_id = uuid.uuid4()
    entry_number = f"JE-{datetime.now().strftime('%Y%m%d')}-{str(ledger_id)[:4].upper()}"

    await conn.execute(
        """
        INSERT INTO ledger_entries
        (id, proposal_id, approval_id, tenant_id, entry_date, entry_number, 
         description, posted_by_name)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        ON CONFLICT DO NOTHING
        """,
        ledger_id,
        uuid.UUID(proposal_id),
        uuid.UUID(approval_id),
        proposal["tenant_id"],
        datetime.now().date(),
        entry_number,
        f"Invoice {proposal['invoice_number'] or 'N/A'} - {proposal['vendor_name'] or 'Unknown'}",
        posted_by,
    )

    # Get proposal entries
    entries = await conn.fetch(
        "SELECT * FROM journal_proposal_entries WHERE proposal_id = $1 ORDER BY line_order",
        uuid.UUID(proposal_id),
    )

    # Create ledger lines
    ledger_lines_data = [
        (
            uuid.uuid4(),
            ledger_id,
            entry["account_code"],
            entry["account_name"],
            entry["debit_amount"],
            entry["credit_amount"],
            entry["line_order"],
        )
        for entry in entries
    ]

    if ledger_lines_data:
        await conn.executemany(
            """
            INSERT INTO ledger_lines
            (id, ledger_entry_id, account_code, account_name, debit_amount, credit_amount, line_order)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT DO NOTHING
            """,
            ledger_lines_data,
        )

    logger.info(f"[{request_id}] Created ledger entry {entry_number} for proposal {proposal_id}")
    return str(ledger_id)


async def create_pending_approval(
    conn,
    proposal_id: str,
    tenant_id: str,
    job_id: str | None = None,
    request_id: str | None = None,
) -> str:
    """
    Create a pending approval for a proposal.

    Returns:
        Created approval ID
    """
    approval_id = uuid.uuid4()

    await conn.execute(
        """
        INSERT INTO approvals
        (id, proposal_id, tenant_id, job_id, action, status, approver_name, comments)
        VALUES ($1, $2, $3, $4, 'pending', 'pending', NULL, NULL)
        ON CONFLICT DO NOTHING
        """,
        approval_id,
        uuid.UUID(proposal_id),
        uuid.UUID(tenant_id) if tenant_id and len(tenant_id) > 10 else None,
        uuid.UUID(job_id) if job_id else None,
    )

    logger.info(f"[{request_id}] Created pending approval {approval_id} for proposal {proposal_id}")
    return str(approval_id)
