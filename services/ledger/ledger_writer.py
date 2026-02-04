"""
Ledger Writer Service for ERPX E2E
Writes approved proposals to Ledger Zone (ERP Official DB)
"""

import logging
import sys
import uuid
from datetime import datetime

from sqlalchemy.orm import Session

sys.path.insert(0, "/root/erp-ai")

from domain.enums import AuditAction, InvoiceStatus, LedgerEntryType, OutboxEventType, ProposalStatus
from domain.models import Invoice, LedgerEntry, Proposal
from services.audit.audit_logger import AuditLogger
from services.outbox.outbox_repo import OutboxRepository

logger = logging.getLogger("LedgerWriter")


class LedgerWriter:
    """
    Ledger Writer - Writes approved proposals to Ledger Zone
    Creates official accounting entries after approval
    """

    def __init__(self, db: Session):
        self.db = db
        self.audit = AuditLogger(db)
        self.outbox = OutboxRepository(db)

    def post_to_ledger(
        self,
        proposal: Proposal,
        approved_by: str,
        *,
        trace_id: str | None = None,
        request_id: str | None = None,
        invoice: Invoice | None = None,
    ) -> tuple[list[LedgerEntry], str]:
        """
        Post approved proposal to ledger

        Args:
            proposal: The approved proposal
            approved_by: Who approved
            trace_id: E2E trace ID
            request_id: Request ID
            invoice: Optional invoice object to avoid redundant DB query

        Returns:
            Tuple of (list of created ledger entries, journal number)
        """
        if proposal.status != ProposalStatus.APPROVED:
            # Idempotency check: allow if already posted, just return empty (or raise specific error)
            if proposal.status == ProposalStatus.POSTED:
                logger.info(f"Proposal {proposal.id} already posted. Skipping.")
                return [], ""
            raise ValueError(f"Proposal {proposal.id} is not approved (status: {proposal.status})")

        # Check if ledger entries already exist (double-check)
        existing = self.db.query(LedgerEntry).filter(LedgerEntry.proposal_id == proposal.id).first()
        if existing is not None and isinstance(existing, LedgerEntry):
            logger.info(f"Proposal {proposal.id} already has ledger entries. Skipping.")
            return [], existing.journal_number

        # Generate journal number
        journal_number = self._generate_journal_number(proposal.tenant_id)

        # Get suggested entries from proposal
        suggested_entries = proposal.suggested_entries or []

        if not suggested_entries:
            raise ValueError(f"Proposal {proposal.id} has no suggested entries")

        ledger_entries = []
        total_debit = 0.0
        total_credit = 0.0

        for entry in suggested_entries:
            # Create debit entry
            debit_entry = LedgerEntry(
                proposal_id=proposal.id,
                tenant_id=proposal.tenant_id,
                entry_type=LedgerEntryType.DEBIT,
                account_code=entry.get("debit_account"),
                account_name=entry.get("debit_account_name"),
                amount=float(entry.get("amount", 0)),
                currency=entry.get("currency", "VND"),
                description=entry.get("description"),
                journal_number=journal_number,
                posting_date=datetime.utcnow(),
                approved_by=approved_by,
                approved_at=proposal.approved_at,
                source_proposal_id=proposal.id,
                trace_id=trace_id,
            )
            ledger_entries.append(debit_entry)
            total_debit += float(entry.get("amount", 0))

            # Create credit entry
            credit_entry = LedgerEntry(
                proposal_id=proposal.id,
                tenant_id=proposal.tenant_id,
                entry_type=LedgerEntryType.CREDIT,
                account_code=entry.get("credit_account"),
                account_name=entry.get("credit_account_name"),
                amount=float(entry.get("amount", 0)),
                currency=entry.get("currency", "VND"),
                description=entry.get("description"),
                journal_number=journal_number,
                posting_date=datetime.utcnow(),
                approved_by=approved_by,
                approved_at=proposal.approved_at,
                source_proposal_id=proposal.id,
                trace_id=trace_id,
            )
            ledger_entries.append(credit_entry)
            total_credit += float(entry.get("amount", 0))

        # Batch insert all entries
        self.db.add_all(ledger_entries)

        # Update proposal status to POSTED
        proposal.status = ProposalStatus.POSTED
        proposal.updated_at = datetime.utcnow()

        # Update invoice status to POSTED
        if invoice is None:
            # Reuse proposal.invoice if loaded, otherwise query
            # Accessing relationship might trigger lazy load if not detached, which is better than explicit query if session is active
            if hasattr(proposal, "invoice") and proposal.invoice:
                invoice = proposal.invoice
            else:
                invoice = self.db.query(Invoice).filter(Invoice.id == proposal.invoice_id).first()

        if invoice:
            old_status = invoice.status
            invoice.status = InvoiceStatus.POSTED
            invoice.updated_at = datetime.utcnow()

            # Audit status change
            self.audit.log_status_change(
                entity_type="Invoice",
                entity_id=str(invoice.id),
                old_status=old_status.value,
                new_status=InvoiceStatus.POSTED.value,
                actor=approved_by,
                tenant_id=proposal.tenant_id,
                trace_id=trace_id,
                request_id=request_id,
                invoice_id=invoice.id,
            )

        self.db.commit()

        # Audit ledger posting
        self.audit.log(
            action=AuditAction.LEDGER_POST,
            entity_type="Proposal",
            entity_id=str(proposal.id),
            actor=approved_by,
            tenant_id=proposal.tenant_id,
            new_state={
                "journal_number": journal_number,
                "entries_count": len(ledger_entries),
                "total_debit": total_debit,
                "total_credit": total_credit,
            },
            trace_id=trace_id,
            request_id=request_id,
            invoice_id=proposal.invoice_id,
        )

        # Publish LEDGER_POSTED event
        self.outbox.publish(
            event_type=OutboxEventType.LEDGER_POSTED,
            payload={
                "proposal_id": str(proposal.id),
                "invoice_id": str(proposal.invoice_id),
                "tenant_id": proposal.tenant_id,
                "journal_number": journal_number,
                "entries_count": len(ledger_entries),
                "total_amount": total_debit,
                "approved_by": approved_by,
                "posted_at": datetime.utcnow().isoformat(),
                "trace_id": trace_id,
            },
            aggregate_type="Proposal",
            aggregate_id=str(proposal.id),
            tenant_id=proposal.tenant_id,
            trace_id=trace_id,
        )

        logger.info(
            f"LEDGER: Posted {len(ledger_entries)} entries for proposal {proposal.id}, "
            f"journal={journal_number}, debit={total_debit}, credit={total_credit}"
        )

        return ledger_entries, journal_number

    def _generate_journal_number(self, tenant_id: str) -> str:
        """Generate unique journal number"""
        date_str = datetime.utcnow().strftime("%Y%m%d")
        # Count existing journals for today
        count = (
            self.db.query(LedgerEntry)
            .filter(LedgerEntry.tenant_id == tenant_id)
            .filter(LedgerEntry.journal_number.like(f"JV-{date_str}-%"))
            .distinct(LedgerEntry.journal_number)
            .count()
        )
        return f"JV-{date_str}-{count + 1:04d}"

    def get_ledger_entries(
        self,
        tenant_id: str,
        *,
        proposal_id: uuid.UUID | None = None,
        account_code: str | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        limit: int = 100,
    ) -> list[LedgerEntry]:
        """Get ledger entries with filters"""
        query = self.db.query(LedgerEntry).filter(LedgerEntry.tenant_id == tenant_id)

        if proposal_id:
            query = query.filter(LedgerEntry.proposal_id == proposal_id)
        if account_code:
            query = query.filter(LedgerEntry.account_code == account_code)
        if from_date:
            query = query.filter(LedgerEntry.posting_date >= from_date)
        if to_date:
            query = query.filter(LedgerEntry.posting_date <= to_date)

        return query.order_by(LedgerEntry.posting_date.desc()).limit(limit).all()

    def get_journal_entries(
        self,
        tenant_id: str,
        journal_number: str,
    ) -> list[LedgerEntry]:
        """Get all entries for a journal"""
        return (
            self.db.query(LedgerEntry)
            .filter(LedgerEntry.tenant_id == tenant_id)
            .filter(LedgerEntry.journal_number == journal_number)
            .order_by(LedgerEntry.entry_type)
            .all()
        )
