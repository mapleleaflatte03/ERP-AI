"""
Pydantic Schemas for ERPX E2E API
Request/Response models for Gateway API
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from domain.enums import AuditAction, InvoiceStatus, ProposalStatus

# ==============================================================================
# INVOICE SCHEMAS
# ==============================================================================


class InvoiceUploadResponse(BaseModel):
    """Response after uploading an invoice"""

    invoice_id: UUID
    tenant_id: str
    file_name: str
    status: InvoiceStatus
    trace_id: str
    message: str
    created_at: datetime

    class Config:
        from_attributes = True


class InvoiceStatusResponse(BaseModel):
    """Invoice status response"""

    invoice_id: UUID
    tenant_id: str
    file_name: str
    status: InvoiceStatus

    # Extracted data (if available)
    invoice_number: str | None = None
    invoice_date: datetime | None = None
    seller_name: str | None = None
    total_amount: float | None = None
    vat_amount: float | None = None

    # Processing info
    ocr_json_path: str | None = None
    trace_id: str | None = None

    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class InvoiceListResponse(BaseModel):
    """List of invoices"""

    invoices: list[InvoiceStatusResponse]
    total: int
    page: int
    page_size: int


# ==============================================================================
# PROPOSAL SCHEMAS
# ==============================================================================


class SuggestedEntry(BaseModel):
    """Single accounting entry suggestion"""

    debit_account: str
    debit_account_name: str | None = None
    credit_account: str
    credit_account_name: str | None = None
    amount: float
    currency: str = "VND"
    description: str | None = None


class EvidenceItem(BaseModel):
    """RAG evidence item"""

    source: str
    text: str
    score: float | None = None


class ProposalResponse(BaseModel):
    """Proposal response with AI suggestions"""

    proposal_id: UUID
    invoice_id: UUID
    tenant_id: str
    status: ProposalStatus

    # AI suggestions (Proposal Zone)
    suggested_entries: list[SuggestedEntry]
    evidence: list[EvidenceItem]
    ai_explanation: str | None = None
    confidence_score: float | None = None

    # Model versioning (MLflow placeholder)
    llm_model_name: str | None = None
    llm_model_version: str | None = None
    embedding_model_name: str | None = None
    embedding_dim: int | None = None
    prompt_version: str | None = None

    # Approval info
    approved_by: str | None = None
    approved_at: datetime | None = None
    rejection_reason: str | None = None

    trace_id: str | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ==============================================================================
# APPROVAL SCHEMAS
# ==============================================================================


class ApprovalRequest(BaseModel):
    """Approval request payload"""

    approved: bool
    approved_by: str
    rejection_reason: str | None = None
    comment: str | None = None


class ApprovalResponse(BaseModel):
    """Approval response"""

    invoice_id: UUID
    proposal_id: UUID
    approved: bool
    approved_by: str
    approved_at: datetime
    new_status: InvoiceStatus
    ledger_entries_created: int = 0
    message: str
    trace_id: str


# ==============================================================================
# LEDGER SCHEMAS
# ==============================================================================


class LedgerEntryResponse(BaseModel):
    """Ledger entry response"""

    id: UUID
    proposal_id: UUID
    entry_type: str
    account_code: str
    account_name: str | None = None
    amount: float
    currency: str
    description: str | None = None
    journal_number: str | None = None
    posting_date: datetime
    approved_by: str
    approved_at: datetime

    class Config:
        from_attributes = True


class LedgerListResponse(BaseModel):
    """List of ledger entries"""

    entries: list[LedgerEntryResponse]
    total: int
    total_debit: float
    total_credit: float


# ==============================================================================
# AUDIT SCHEMAS
# ==============================================================================


class AuditEventResponse(BaseModel):
    """Audit event response"""

    id: UUID
    action: AuditAction
    entity_type: str | None = None
    entity_id: str | None = None
    actor: str | None = None
    old_state: dict[str, Any] | None = None
    new_state: dict[str, Any] | None = None
    details: dict[str, Any] | None = None
    trace_id: str | None = None
    request_id: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class AuditTrailResponse(BaseModel):
    """Audit trail for an entity"""

    entity_type: str
    entity_id: str
    events: list[AuditEventResponse]
    total: int


# ==============================================================================
# HEALTH & METRICS SCHEMAS
# ==============================================================================


class HealthResponse(BaseModel):
    """Health check response"""

    status: str
    version: str
    timestamp: datetime
    components: dict[str, str]


class MetricsResponse(BaseModel):
    """Metrics response"""

    requests_total: int
    requests_by_endpoint: dict[str, int]
    requests_by_tenant: dict[str, int]
    errors_total: int
    avg_response_time_ms: float
    uptime_seconds: float


# ==============================================================================
# ERROR SCHEMAS
# ==============================================================================


class ErrorResponse(BaseModel):
    """Error response"""

    error: str
    detail: str | None = None
    trace_id: str | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
