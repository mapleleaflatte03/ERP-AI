"""
ERPX AI - Database Models
========================
SQLAlchemy models for all business entities.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class DocumentStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    EXTRACTED = "extracted"
    PROPOSED = "proposed"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    POSTED = "posted"
    FAILED = "failed"


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ApprovalAction(str, enum.Enum):
    APPROVE = "approve"
    REJECT = "reject"
    REQUEST_CHANGES = "request_changes"


class Document(Base):
    __tablename__ = "documents"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename = Column(String(500), nullable=False)
    original_filename = Column(String(500), nullable=False)
    content_type = Column(String(100), nullable=False)
    file_size = Column(Integer, nullable=False)
    file_hash = Column(String(64), nullable=False)
    bucket = Column(String(100), default="erpx-documents")
    object_key = Column(String(500), nullable=False)
    uploaded_by = Column(String(100))
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    source = Column(String(50), default="api")
    status = Column(Enum(DocumentStatus), default=DocumentStatus.UPLOADED)
    job_runs = relationship("JobRun", back_populates="document")
    extracted_invoice = relationship("ExtractedInvoice", back_populates="document", uselist=False)


class JobRun(Base):
    __tablename__ = "job_runs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False)
    workflow_id = Column(String(200), unique=True)
    run_id = Column(String(200))
    status = Column(Enum(JobStatus), default=JobStatus.PENDING)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    result = Column(JSONB)
    error = Column(Text)
    retry_count = Column(Integer, default=0)
    created_by = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    document = relationship("Document", back_populates="job_runs")


class ExtractedInvoice(Base):
    __tablename__ = "extracted_invoices"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), unique=True)
    job_id = Column(UUID(as_uuid=True), ForeignKey("job_runs.id"))
    invoice_number = Column(String(100))
    invoice_date = Column(DateTime)
    due_date = Column(DateTime)
    vendor_name = Column(String(500))
    vendor_tax_id = Column(String(50))
    vendor_address = Column(Text)
    subtotal = Column(Numeric(18, 2))
    tax_amount = Column(Numeric(18, 2))
    total_amount = Column(Numeric(18, 2))
    currency = Column(String(3), default="VND")
    line_items = Column(JSONB)
    raw_text = Column(Text)
    extraction_confidence = Column(Float, default=0.0)
    extraction_method = Column(String(50))
    extracted_at = Column(DateTime, default=datetime.utcnow)
    document = relationship("Document", back_populates="extracted_invoice")
    journal_proposal = relationship("JournalProposal", back_populates="extracted_invoice", uselist=False)


class JournalProposal(Base):
    __tablename__ = "journal_proposals"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    extracted_invoice_id = Column(UUID(as_uuid=True), ForeignKey("extracted_invoices.id"), unique=True)
    job_id = Column(UUID(as_uuid=True), ForeignKey("job_runs.id"))
    status = Column(String(50), default="pending")
    confidence = Column(Float, default=0.0)
    reasoning = Column(Text)
    rag_context = Column(JSONB)
    opa_result = Column(JSONB)
    is_balanced = Column(Boolean, default=False)
    risk_level = Column(String(20))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    extracted_invoice = relationship("ExtractedInvoice", back_populates="journal_proposal")
    entries = relationship("JournalProposalEntry", back_populates="proposal")
    approvals = relationship("Approval", back_populates="proposal")


class JournalProposalEntry(Base):
    __tablename__ = "journal_proposal_entries"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    proposal_id = Column(UUID(as_uuid=True), ForeignKey("journal_proposals.id"))
    line_number = Column(Integer, nullable=False)
    account_code = Column(String(20), nullable=False)
    account_name = Column(String(200))
    debit_amount = Column(Numeric(18, 2), default=0)
    credit_amount = Column(Numeric(18, 2), default=0)
    description = Column(String(500))
    proposal = relationship("JournalProposal", back_populates="entries")


class Approval(Base):
    __tablename__ = "approvals"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    proposal_id = Column(UUID(as_uuid=True), ForeignKey("journal_proposals.id"))
    action = Column(Enum(ApprovalAction), nullable=False)
    notes = Column(Text)
    approver_id = Column(String(100), nullable=False)
    approver_name = Column(String(200))
    approver_role = Column(String(50))
    approved_at = Column(DateTime, default=datetime.utcnow)
    proposal = relationship("JournalProposal", back_populates="approvals")


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    proposal_id = Column(UUID(as_uuid=True), ForeignKey("journal_proposals.id"))
    approval_id = Column(UUID(as_uuid=True), ForeignKey("approvals.id"))
    entry_number = Column(String(50), unique=True, nullable=False)
    transaction_date = Column(DateTime, nullable=False)
    posting_date = Column(DateTime, default=datetime.utcnow)
    reference = Column(String(200))
    description = Column(Text)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"))
    posted_by = Column(String(100))
    lines = relationship("LedgerLine", back_populates="entry")


class LedgerLine(Base):
    __tablename__ = "ledger_lines"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entry_id = Column(UUID(as_uuid=True), ForeignKey("ledger_entries.id"))
    line_number = Column(Integer, nullable=False)
    account_code = Column(String(20), nullable=False)
    account_name = Column(String(200))
    debit_amount = Column(Numeric(18, 2), default=0)
    credit_amount = Column(Numeric(18, 2), default=0)
    description = Column(String(500))
    entry = relationship("LedgerEntry", back_populates="lines")


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type = Column(String(100), nullable=False)
    event_action = Column(String(50), nullable=False)
    entity_type = Column(String(100))
    entity_id = Column(String(100))
    user_id = Column(String(100))
    user_name = Column(String(200))
    user_role = Column(String(50))
    old_value = Column(JSONB)
    new_value = Column(JSONB)
    metadata = Column(JSONB)
    ip_address = Column(String(50))
    user_agent = Column(String(500))
    trace_id = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)


class KnowledgeBaseEntry(Base):
    __tablename__ = "knowledge_base_entries"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_url = Column(String(1000))
    source_type = Column(String(50))
    title = Column(String(500))
    content_hash = Column(String(64), unique=True)
    collection_name = Column(String(100))
    point_ids = Column(JSONB)
    ingested_at = Column(DateTime, default=datetime.utcnow)
    chunk_count = Column(Integer, default=0)
