"""
SQLAlchemy Models for ERPX E2E
Defines: Invoice, Proposal, LedgerEntry, OutboxEvent, AuditEvent
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy import (
    Enum as SQLEnum,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

from domain.enums import AuditAction, InvoiceStatus, LedgerEntryType, OutboxEventType, OutboxStatus, ProposalStatus

Base = declarative_base()


class Invoice(Base):
    """
    Invoice entity - represents uploaded documents in RAW/Staging Zone
    """

    __tablename__ = "e2e_invoices"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String(100), nullable=False, index=True)

    # File info (RAW/Staging Zone)
    file_name = Column(String(500), nullable=False)
    file_path = Column(String(1000), nullable=False)
    file_type = Column(String(50))
    file_size = Column(BigInteger)

    # Processing status
    status = Column(SQLEnum(InvoiceStatus), default=InvoiceStatus.UPLOADED, index=True)

    # OCR output path
    ocr_json_path = Column(String(1000))

    # Extracted data (from OCR)
    invoice_number = Column(String(100))
    invoice_date = Column(DateTime)
    seller_name = Column(String(500))
    seller_tax_code = Column(String(50))
    buyer_name = Column(String(500))
    buyer_tax_code = Column(String(50))
    total_amount = Column(Float)
    vat_amount = Column(Float)
    currency = Column(String(10), default="VND")

    # Tracing
    trace_id = Column(String(100), index=True)  # For E2E observability

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    proposals = relationship("Proposal", back_populates="invoice")
    audit_events = relationship("AuditEvent", back_populates="invoice")

    __table_args__ = (
        Index("idx_e2e_inv_tenant_status", "tenant_id", "status"),
        Index("idx_e2e_inv_trace", "trace_id"),
    )


class Proposal(Base):
    """
    Proposal entity - AI-generated accounting suggestions (Proposal Zone)
    """

    __tablename__ = "e2e_proposals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_id = Column(UUID(as_uuid=True), ForeignKey("e2e_invoices.id"), nullable=False, index=True)
    tenant_id = Column(String(100), nullable=False, index=True)

    # Proposal content (Proposal Zone)
    suggested_entries = Column(JSON)  # List of {debit_account, credit_account, amount, description}
    evidence = Column(JSON)  # RAG sources, confidence scores
    ai_explanation = Column(Text)

    # Model versioning (MLflow tracking placeholder)
    llm_model_name = Column(String(200))
    llm_model_version = Column(String(100))
    embedding_model_name = Column(String(200))
    embedding_dim = Column(Integer)
    prompt_version = Column(String(100))

    # Confidence
    confidence_score = Column(Float)

    # Status
    status = Column(SQLEnum(ProposalStatus), default=ProposalStatus.PENDING, index=True)

    # Approval info
    approved_by = Column(String(200))
    approved_at = Column(DateTime)
    rejection_reason = Column(Text)

    # Artifact path
    artifact_json_path = Column(String(1000))

    # Tracing
    trace_id = Column(String(100), index=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    invoice = relationship("Invoice", back_populates="proposals")
    ledger_entries = relationship("LedgerEntry", back_populates="proposal")

    __table_args__ = (Index("idx_e2e_prop_tenant_status", "tenant_id", "status"),)


class LedgerEntry(Base):
    """
    Ledger Entry - Official accounting entries (Ledger Zone / ERP Official DB)
    Posted after approval
    """

    __tablename__ = "e2e_ledger_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    proposal_id = Column(UUID(as_uuid=True), ForeignKey("e2e_proposals.id"), nullable=False, index=True)
    tenant_id = Column(String(100), nullable=False, index=True)

    # Entry details (Ledger Zone)
    entry_type = Column(SQLEnum(LedgerEntryType), nullable=False)
    account_code = Column(String(20), nullable=False, index=True)
    account_name = Column(String(200))
    amount = Column(Float, nullable=False)
    currency = Column(String(10), default="VND")
    description = Column(Text)

    # Journal info
    journal_number = Column(String(100), index=True)
    posting_date = Column(DateTime, default=datetime.utcnow)

    # Approval tracking
    approved_by = Column(String(200), nullable=False)
    approved_at = Column(DateTime, nullable=False)
    source_proposal_id = Column(UUID(as_uuid=True))  # Redundant for querying

    # Tracing
    trace_id = Column(String(100), index=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    proposal = relationship("Proposal", back_populates="ledger_entries")

    __table_args__ = (
        Index("idx_e2e_ledger_tenant_date", "tenant_id", "posting_date"),
        Index("idx_e2e_ledger_account", "account_code"),
    )


class OutboxEvent(Base):
    """
    Outbox Event - Event Bus / Outbox pattern implementation
    """

    __tablename__ = "e2e_outbox_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Event info
    event_type = Column(SQLEnum(OutboxEventType), nullable=False, index=True)
    aggregate_type = Column(String(100))  # e.g., "Invoice", "Proposal"
    aggregate_id = Column(String(100), index=True)  # e.g., invoice_id

    # Payload
    payload = Column(JSON, nullable=False)

    # Processing status
    status = Column(SQLEnum(OutboxStatus), default=OutboxStatus.PENDING, index=True)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    error_message = Column(Text)

    # Tenant
    tenant_id = Column(String(100), index=True)

    # Tracing
    trace_id = Column(String(100), index=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    processed_at = Column(DateTime)

    __table_args__ = (Index("idx_e2e_outbox_status_created", "status", "created_at"),)


class AuditEvent(Base):
    """
    Audit Event - Audit & Evidence Store
    Records all state transitions with who/what/when/why
    """

    __tablename__ = "e2e_audit_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # What happened
    action = Column(SQLEnum(AuditAction), nullable=False, index=True)
    entity_type = Column(String(100))  # Invoice, Proposal, LedgerEntry
    entity_id = Column(String(100), index=True)

    # Who
    actor = Column(String(200))  # user_id or "system"
    tenant_id = Column(String(100), index=True)

    # Details
    old_state = Column(JSON)
    new_state = Column(JSON)
    details = Column(JSON)  # Additional context

    # Evidence
    evidence = Column(JSON)  # Model outputs, confidence, sources

    # Versioning
    model_version = Column(String(100))
    prompt_version = Column(String(100))

    # Tracing
    trace_id = Column(String(100), index=True)
    request_id = Column(String(100), index=True)

    # Error info (if action is ERROR)
    error_message = Column(Text)
    error_traceback = Column(Text)

    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Foreign key (optional, for direct invoice audit trail)
    invoice_id = Column(UUID(as_uuid=True), ForeignKey("e2e_invoices.id"), nullable=True)

    # Relationships
    invoice = relationship("Invoice", back_populates="audit_events")

    __table_args__ = (
        Index("idx_e2e_audit_entity", "entity_type", "entity_id"),
        Index("idx_e2e_audit_trace", "trace_id"),
        Index("idx_e2e_audit_tenant_time", "tenant_id", "created_at"),
    )


# Tenant & API Key table for Gateway RBAC
class TenantApiKey(Base):
    """
    API Key for tenant authentication (RBAC/Quota)
    """

    __tablename__ = "e2e_tenant_api_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String(100), nullable=False, index=True)
    api_key_hash = Column(String(256), nullable=False, unique=True)  # SHA256 hash
    name = Column(String(200))

    # Quota
    daily_quota = Column(Integer, default=1000)
    requests_today = Column(Integer, default=0)
    quota_reset_at = Column(DateTime)

    # Status
    is_active = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used_at = Column(DateTime)

    __table_args__ = (Index("idx_e2e_apikey_tenant", "tenant_id"),)
