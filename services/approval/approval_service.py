"""
Approval Service for ERPX E2E
Handles approval workflow for proposals
"""

import logging
import sys
import uuid
from datetime import datetime

from sqlalchemy.orm import Session

sys.path.insert(0, "/root/erp-ai")

from domain.enums import AuditAction, InvoiceStatus, OutboxEventType, ProposalStatus
from domain.models import Invoice, Proposal
from services.audit.audit_logger import AuditLogger
from services.ledger.ledger_writer import LedgerWriter
from services.outbox.outbox_repo import OutboxRepository

logger = logging.getLogger("ApprovalService")


class ApprovalService:
    """
    Approval Service - Handles approval workflow
    Implements Approval Inbox pattern
    """

    def __init__(self, db: Session):
        self.db = db
        self.audit = AuditLogger(db)
        self.outbox = OutboxRepository(db)
        self.ledger_writer = LedgerWriter(db)

    def approve(
        self,
        invoice_id: uuid.UUID,
        approved_by: str,
        *,
        comment: str | None = None,
        trace_id: str | None = None,
        request_id: str | None = None,
    ) -> tuple[Proposal, int]:
        """
        Approve a proposal and post to ledger

        Args:
            invoice_id: Invoice ID to approve
            approved_by: User who is approving
            comment: Optional approval comment
            trace_id: E2E trace ID
            request_id: Request ID

        Returns:
            Tuple of (approved proposal, number of ledger entries created)
        """
        # Get invoice
        invoice = self.db.query(Invoice).filter(Invoice.id == invoice_id).first()
        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found")

        # Get latest pending proposal
        proposal = (
            self.db.query(Proposal)
            .filter(Proposal.invoice_id == invoice_id)
            .filter(Proposal.status == ProposalStatus.PENDING)
            .order_by(Proposal.created_at.desc())
            .first()
        )

        if not proposal:
            raise ValueError(f"No pending proposal found for invoice {invoice_id}")

        # Update proposal status
        old_proposal_status = proposal.status
        proposal.status = ProposalStatus.APPROVED
        proposal.approved_by = approved_by
        proposal.approved_at = datetime.utcnow()
        proposal.updated_at = datetime.utcnow()

        # Update invoice status
        old_invoice_status = invoice.status
        invoice.status = InvoiceStatus.APPROVED
        invoice.updated_at = datetime.utcnow()

        self.db.commit()

        # Audit approval
        self.audit.log(
            action=AuditAction.APPROVAL_APPROVE,
            entity_type="Proposal",
            entity_id=str(proposal.id),
            actor=approved_by,
            tenant_id=invoice.tenant_id,
            old_state={"status": old_proposal_status.value},
            new_state={"status": ProposalStatus.APPROVED.value, "approved_by": approved_by},
            details={"comment": comment} if comment else None,
            trace_id=trace_id,
            request_id=request_id,
            invoice_id=invoice.id,
        )

        # Publish PROPOSAL_APPROVED event
        self.outbox.publish(
            event_type=OutboxEventType.PROPOSAL_APPROVED,
            payload={
                "proposal_id": str(proposal.id),
                "invoice_id": str(invoice.id),
                "tenant_id": invoice.tenant_id,
                "approved_by": approved_by,
                "approved_at": proposal.approved_at.isoformat(),
                "trace_id": trace_id,
            },
            aggregate_type="Proposal",
            aggregate_id=str(proposal.id),
            tenant_id=invoice.tenant_id,
            trace_id=trace_id,
        )

        # Post to ledger
        ledger_entries, journal_number = self.ledger_writer.post_to_ledger(
            proposal=proposal,
            approved_by=approved_by,
            trace_id=trace_id,
            request_id=request_id,
        )

        logger.info(
            f"APPROVAL: Approved proposal {proposal.id} for invoice {invoice_id}, "
            f"posted {len(ledger_entries)} ledger entries, journal={journal_number}"
        )

        return proposal, len(ledger_entries)

    def reject(
        self,
        invoice_id: uuid.UUID,
        rejected_by: str,
        rejection_reason: str,
        *,
        trace_id: str | None = None,
        request_id: str | None = None,
    ) -> Proposal:
        """
        Reject a proposal

        Args:
            invoice_id: Invoice ID to reject
            rejected_by: User who is rejecting
            rejection_reason: Reason for rejection
            trace_id: E2E trace ID
            request_id: Request ID

        Returns:
            Rejected proposal
        """
        # Get invoice
        invoice = self.db.query(Invoice).filter(Invoice.id == invoice_id).first()
        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found")

        # Get latest pending proposal
        proposal = (
            self.db.query(Proposal)
            .filter(Proposal.invoice_id == invoice_id)
            .filter(Proposal.status == ProposalStatus.PENDING)
            .order_by(Proposal.created_at.desc())
            .first()
        )

        if not proposal:
            raise ValueError(f"No pending proposal found for invoice {invoice_id}")

        # Update proposal status
        old_proposal_status = proposal.status
        proposal.status = ProposalStatus.REJECTED
        proposal.approved_by = rejected_by  # Store who rejected
        proposal.approved_at = datetime.utcnow()
        proposal.rejection_reason = rejection_reason
        proposal.updated_at = datetime.utcnow()

        # Update invoice status
        old_invoice_status = invoice.status
        invoice.status = InvoiceStatus.REJECTED
        invoice.updated_at = datetime.utcnow()

        self.db.commit()

        # Audit rejection
        self.audit.log(
            action=AuditAction.APPROVAL_REJECT,
            entity_type="Proposal",
            entity_id=str(proposal.id),
            actor=rejected_by,
            tenant_id=invoice.tenant_id,
            old_state={"status": old_proposal_status.value},
            new_state={
                "status": ProposalStatus.REJECTED.value,
                "rejected_by": rejected_by,
                "rejection_reason": rejection_reason,
            },
            trace_id=trace_id,
            request_id=request_id,
            invoice_id=invoice.id,
        )

        # Publish PROPOSAL_REJECTED event
        self.outbox.publish(
            event_type=OutboxEventType.PROPOSAL_REJECTED,
            payload={
                "proposal_id": str(proposal.id),
                "invoice_id": str(invoice.id),
                "tenant_id": invoice.tenant_id,
                "rejected_by": rejected_by,
                "rejection_reason": rejection_reason,
                "rejected_at": proposal.approved_at.isoformat(),
                "trace_id": trace_id,
            },
            aggregate_type="Proposal",
            aggregate_id=str(proposal.id),
            tenant_id=invoice.tenant_id,
            trace_id=trace_id,
        )

        logger.info(f"APPROVAL: Rejected proposal {proposal.id} for invoice {invoice_id}: {rejection_reason}")

        return proposal

    def get_pending_approvals(
        self,
        tenant_id: str,
        limit: int = 100,
    ) -> list:
        """Get pending proposals for approval (Approval Inbox)"""
        return (
            self.db.query(Proposal)
            .filter(Proposal.tenant_id == tenant_id)
            .filter(Proposal.status == ProposalStatus.PENDING)
            .order_by(Proposal.created_at.asc())
            .limit(limit)
            .all()
        )
