"""
Outbox Event Types for ERPX E2E
Defines payload structures for each event type
"""

from pydantic import BaseModel


class InvoiceUploadedPayload(BaseModel):
    """Payload for INVOICE_UPLOADED event"""

    invoice_id: str
    tenant_id: str
    file_name: str
    file_path: str
    file_type: str | None = None
    trace_id: str


class PipelineStartedPayload(BaseModel):
    """Payload for PIPELINE_STARTED event"""

    invoice_id: str
    tenant_id: str
    trace_id: str
    started_at: str


class PipelineCompletedPayload(BaseModel):
    """Payload for PIPELINE_COMPLETED event"""

    invoice_id: str
    tenant_id: str
    proposal_id: str
    trace_id: str
    ocr_json_path: str | None = None
    coding_json_path: str | None = None
    completed_at: str


class PipelineFailedPayload(BaseModel):
    """Payload for PIPELINE_FAILED event"""

    invoice_id: str
    tenant_id: str
    trace_id: str
    error_message: str
    error_step: str | None = None
    failed_at: str


class ProposalCreatedPayload(BaseModel):
    """Payload for PROPOSAL_CREATED event"""

    proposal_id: str
    invoice_id: str
    tenant_id: str
    suggested_entries_count: int
    confidence_score: float | None = None
    trace_id: str


class ProposalApprovedPayload(BaseModel):
    """Payload for PROPOSAL_APPROVED event"""

    proposal_id: str
    invoice_id: str
    tenant_id: str
    approved_by: str
    approved_at: str
    trace_id: str


class ProposalRejectedPayload(BaseModel):
    """Payload for PROPOSAL_REJECTED event"""

    proposal_id: str
    invoice_id: str
    tenant_id: str
    rejected_by: str
    rejection_reason: str | None = None
    rejected_at: str
    trace_id: str


class LedgerPostedPayload(BaseModel):
    """Payload for LEDGER_POSTED event"""

    proposal_id: str
    invoice_id: str
    tenant_id: str
    journal_number: str
    entries_count: int
    total_amount: float
    approved_by: str
    posted_at: str
    trace_id: str
