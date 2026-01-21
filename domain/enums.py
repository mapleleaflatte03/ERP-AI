"""
Domain Enums for ERPX E2E
Defines statuses and state machine transitions
"""

from enum import Enum


class InvoiceStatus(str, Enum):
    """Invoice processing status"""

    UPLOADED = "UPLOADED"  # File uploaded, waiting for processing
    PROCESSING = "PROCESSING"  # OCR/Embedding/Coding in progress
    PROPOSED = "PROPOSED"  # AI suggestions ready
    APPROVED = "APPROVED"  # Human approved
    REJECTED = "REJECTED"  # Human rejected
    POSTED = "POSTED"  # Written to ledger
    FAILED = "FAILED"  # Processing failed


class ProposalStatus(str, Enum):
    """Proposal status"""

    PENDING = "PENDING"  # Waiting for review
    APPROVED = "APPROVED"  # Approved by reviewer
    REJECTED = "REJECTED"  # Rejected by reviewer
    POSTED = "POSTED"  # Posted to ledger


class OutboxEventType(str, Enum):
    """Outbox event types for event-driven architecture"""

    INVOICE_UPLOADED = "INVOICE_UPLOADED"
    PIPELINE_STARTED = "PIPELINE_STARTED"
    PIPELINE_COMPLETED = "PIPELINE_COMPLETED"
    PIPELINE_FAILED = "PIPELINE_FAILED"
    PROPOSAL_CREATED = "PROPOSAL_CREATED"
    PROPOSAL_APPROVED = "PROPOSAL_APPROVED"
    PROPOSAL_REJECTED = "PROPOSAL_REJECTED"
    LEDGER_POSTED = "LEDGER_POSTED"


class OutboxStatus(str, Enum):
    """Outbox event processing status"""

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class AuditAction(str, Enum):
    """Audit log action types"""

    INVOICE_UPLOAD = "INVOICE_UPLOAD"
    PIPELINE_START = "PIPELINE_START"
    OCR_COMPLETE = "OCR_COMPLETE"
    EMBED_COMPLETE = "EMBED_COMPLETE"
    CODING_COMPLETE = "CODING_COMPLETE"
    PROPOSAL_CREATE = "PROPOSAL_CREATE"
    APPROVAL_REQUEST = "APPROVAL_REQUEST"
    APPROVAL_APPROVE = "APPROVAL_APPROVE"
    APPROVAL_REJECT = "APPROVAL_REJECT"
    LEDGER_POST = "LEDGER_POST"
    STATUS_CHANGE = "STATUS_CHANGE"
    ERROR = "ERROR"


class LedgerEntryType(str, Enum):
    """Ledger entry types"""

    DEBIT = "DEBIT"
    CREDIT = "CREDIT"
