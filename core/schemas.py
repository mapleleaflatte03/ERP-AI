"""
ERPX AI Accounting - Output Schema (FIXED - R7)
===============================================
This schema is LOCKED and must not be changed.
All document processing outputs MUST conform to this schema.
"""

import re
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class DocType(str, Enum):
    """Document type classification"""

    RECEIPT = "receipt"
    VAT_INVOICE = "vat_invoice"
    BANK_SLIP = "bank_slip"
    OTHER = "other"


class InvoiceType(str, Enum):
    """Invoice type classification"""

    RECEIPT = "receipt"
    VAT_INVOICE = "vat_invoice"
    CREDIT_NOTE = "credit_note"
    DEBIT_NOTE = "debit_note"
    OTHER = "other"


class EvidenceSource(str, Enum):
    """Source of extracted data"""

    OCR = "ocr"
    STRUCTURED = "structured"
    DB = "db"
    INFERRED = "inferred"


# =============================================================================
# ASOFT-T Payload Sub-Models
# =============================================================================


class ChungTu(BaseModel):
    """Document header information (Chứng từ)"""

    posting_date: str | None = Field(None, description="Posting date dd/mm/yyyy")
    doc_date: str | None = Field(None, description="Document date dd/mm/yyyy")
    customer_or_vendor: str | None = Field(None, description="Customer or vendor name")
    description: str | None = Field(None, description="Document description")
    currency: str | None = Field("VND", description="Currency code")

    @field_validator("posting_date", "doc_date", mode="before")
    @classmethod
    def validate_date_format(cls, v):
        if v is None:
            return None
        if isinstance(v, str) and v:
            # Allow dd/mm/yyyy or yyyy-mm-dd formats
            patterns = [
                r"^\d{2}/\d{2}/\d{4}$",  # dd/mm/yyyy
                r"^\d{4}-\d{2}-\d{2}$",  # yyyy-mm-dd
            ]
            if not any(re.match(p, v) for p in patterns):
                # Try to keep as-is if it looks like a date
                pass
        return v


class HoaDon(BaseModel):
    """Invoice information (Hóa đơn)"""

    invoice_serial: str | None = Field(None, description="Invoice serial (ký hiệu HĐ)")
    invoice_no: str | None = Field(None, description="Invoice number (số HĐ)")
    invoice_date: str | None = Field(None, description="Invoice date dd/mm/yyyy")
    invoice_type: str | None = Field(None, description="Invoice type")
    tax_id: str | None = Field(None, description="Tax ID / MST")


class Thue(BaseModel):
    """Tax information (Thuế)"""

    vat_rate: float | None = Field(None, description="VAT rate percentage")
    vat_amount: float | None = Field(None, description="VAT amount")
    tax_account: str | None = Field(None, description="Tax account code")
    tax_group: str | None = Field(None, description="Tax group code")


class LineItem(BaseModel):
    """Invoice line item (Chi tiết dòng)"""

    line_no: int = Field(..., description="Line number")
    item_code: str | None = Field(None, description="Item code")
    description: str | None = Field(None, description="Line description")
    quantity: float | None = Field(None, description="Quantity")
    unit_price: float | None = Field(None, description="Unit price")
    amount: float | None = Field(None, description="Line amount")
    vat_rate: float | None = Field(None, description="Line VAT rate")
    vat_amount: float | None = Field(None, description="Line VAT amount")


class ChiTiet(BaseModel):
    """Detail section (Chi tiết)"""

    items: list[LineItem] = Field(default_factory=list, description="Line items")
    subtotal: float | None = Field(None, description="Subtotal before VAT")
    grand_total: float | None = Field(None, description="Grand total including VAT")


class ASOFPayload(BaseModel):
    """ASOFT-T Compatible Payload"""

    doc_type: str = Field(..., description="Document type")
    chung_tu: ChungTu = Field(default_factory=ChungTu)
    hoa_don: HoaDon = Field(default_factory=HoaDon)
    thue: Thue = Field(default_factory=Thue)
    chi_tiet: ChiTiet = Field(default_factory=ChiTiet)


# =============================================================================
# Reconciliation Models
# =============================================================================


class ReconciliationMatch(BaseModel):
    """A single reconciliation match"""

    invoice_id: str = Field(..., description="Invoice/document ID")
    txn_id: str = Field(..., description="Bank transaction ID")
    match_score: float = Field(..., ge=0, le=1, description="Match confidence 0-1")
    reason: str = Field(..., description="Match reason explanation")
    amount_diff: float = Field(0.0, description="Amount difference")


class ReconciliationResult(BaseModel):
    """Bank reconciliation results"""

    matched: list[ReconciliationMatch] = Field(default_factory=list)
    unmatched_invoices: list[str] = Field(default_factory=list)
    unmatched_bank_txns: list[str] = Field(default_factory=list)


# =============================================================================
# Evidence Models
# =============================================================================


class NumberEvidence(BaseModel):
    """Evidence for an extracted number"""

    label: str = Field(..., description="Field label")
    value: Any = Field(..., description="Extracted value")
    source: str = Field(..., description="Source: ocr|structured|db")


class Evidence(BaseModel):
    """Evidence container for audit trail"""

    key_text_snippets: list[str] = Field(default_factory=list)
    numbers_found: list[NumberEvidence] = Field(default_factory=list)


# =============================================================================
# MAIN OUTPUT SCHEMA (FIXED - R7)
# =============================================================================


class AccountingCodingOutput(BaseModel):
    """
    FIXED OUTPUT SCHEMA - DO NOT MODIFY
    ====================================
    This is the standard output for all document processing.
    Complies with MASTER PROMPT Rule R7.
    """

    asof_payload: ASOFPayload = Field(..., description="ASOFT-T compatible payload")
    reconciliation_result: ReconciliationResult = Field(default_factory=ReconciliationResult)
    needs_human_review: bool = Field(False, description="Requires human approval")
    missing_fields: list[str] = Field(default_factory=list, description="Missing required fields")
    warnings: list[str] = Field(default_factory=list, description="Processing warnings")
    evidence: Evidence = Field(default_factory=Evidence, description="Audit evidence")
    source_file: str | None = Field(None, description="Source file path")
    doc_id: str | None = Field(None, description="Document ID")

    # Metadata
    processed_at: str | None = Field(None, description="Processing timestamp")
    processing_mode: str | None = Field(None, description="STRICT or RELAXED")
    workflow_trace: list[str] | None = Field(default_factory=list, description="Workflow steps executed")

    class Config:
        json_schema_extra = {
            "example": {
                "asof_payload": {
                    "doc_type": "vat_invoice",
                    "chung_tu": {
                        "posting_date": "20/01/2026",
                        "doc_date": "20/01/2026",
                        "customer_or_vendor": "ABC Corp",
                        "description": "Office supplies",
                        "currency": "VND",
                    },
                    "hoa_don": {
                        "invoice_serial": "1C26TAA",
                        "invoice_no": "0000123",
                        "invoice_date": "20/01/2026",
                        "invoice_type": "vat_invoice",
                        "tax_id": "0102030405",
                    },
                    "thue": {"vat_rate": 10.0, "vat_amount": 100000, "tax_account": "13311", "tax_group": "V10"},
                    "chi_tiet": {"items": [], "subtotal": 1000000, "grand_total": 1100000},
                },
                "reconciliation_result": {"matched": [], "unmatched_invoices": [], "unmatched_bank_txns": []},
                "needs_human_review": False,
                "missing_fields": [],
                "warnings": [],
                "evidence": {"key_text_snippets": ["Serial: 1C26TAA"], "numbers_found": []},
                "source_file": "invoice_001.json",
                "doc_id": "INV-2026-0001",
            }
        }


# =============================================================================
# API Request/Response Models
# =============================================================================


class CodingRequest(BaseModel):
    """Request for POST /v1/accounting/coding"""

    ocr_text: str | None = Field(None, description="Raw OCR text")
    structured_fields: dict | None = Field(None, description="Pre-extracted structured fields")
    file_path: str | None = Field(None, description="Path to document file")
    file_base64: str | None = Field(None, description="Base64 encoded file content")
    mode: Literal["STRICT", "RELAXED"] = Field("STRICT", description="Processing mode")
    doc_id: str | None = Field(None, description="Optional document ID")
    tenant_id: str | None = Field(None, description="Tenant ID for multi-tenancy")

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v):
        return v.upper()


class BankTransaction(BaseModel):
    """Bank transaction for reconciliation"""

    txn_id: str = Field(..., description="Transaction ID")
    txn_date: str = Field(..., description="Transaction date")
    amount: float = Field(..., description="Transaction amount")
    memo: str | None = Field(None, description="Transaction memo/description")
    account_no: str | None = Field(None, description="Bank account number")


class ReconcileRequest(BaseModel):
    """Request for POST /v1/accounting/reconcile"""

    invoices: list[dict] = Field(..., description="List of invoice payloads")
    bank_txns: list[BankTransaction] = Field(..., description="List of bank transactions")
    tolerance_percent: float = Field(0.5, description="Amount tolerance %")
    tolerance_amount: float = Field(50000, description="Amount tolerance VND")
    date_window_days: int = Field(7, description="Date matching window")
    tenant_id: str | None = Field(None, description="Tenant ID")


class HealthResponse(BaseModel):
    """Response for GET /health"""

    status: str = Field("ok", description="Service status")
    version: str = Field(..., description="API version")
    timestamp: str = Field(..., description="Current timestamp")
    components: dict = Field(default_factory=dict, description="Component health status")


class APIResponse(BaseModel):
    """Standard API response wrapper"""

    success: bool = Field(..., description="Request success status")
    data: Any | None = Field(None, description="Response data")
    error: str | None = Field(None, description="Error message if any")
    request_id: str | None = Field(None, description="Request tracking ID")
    processing_time_ms: float | None = Field(None, description="Processing time in ms")


# =============================================================================
# Approval Workflow Models
# =============================================================================


class ApprovalStatus(str, Enum):
    """Approval status"""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    AUTO_APPROVED = "auto_approved"


class ApprovalRequest(BaseModel):
    """Approval request for human review"""

    approval_id: str = Field(..., description="Unique approval request ID")
    doc_id: str = Field(..., description="Document ID")
    payload: AccountingCodingOutput = Field(..., description="Processing output")
    created_at: str = Field(..., description="Creation timestamp")
    status: ApprovalStatus = Field(ApprovalStatus.PENDING)
    assigned_to: str | None = Field(None, description="Assigned reviewer")
    reviewed_at: str | None = Field(None, description="Review timestamp")
    reviewer_notes: str | None = Field(None, description="Reviewer notes")


class ApprovalDecision(BaseModel):
    """Approval decision input"""

    approval_id: str = Field(..., description="Approval request ID")
    decision: Literal["approve", "reject"] = Field(..., description="Decision")
    notes: str | None = Field(None, description="Decision notes")
    corrections: dict | None = Field(None, description="Field corrections if any")


# =============================================================================
# Audit Models
# =============================================================================


class AuditEntry(BaseModel):
    """Audit trail entry"""

    audit_id: str = Field(..., description="Unique audit ID")
    timestamp: str = Field(..., description="Event timestamp")
    event_type: str = Field(..., description="Event type")
    doc_id: str | None = Field(None, description="Related document ID")
    user_id: str | None = Field(None, description="User who triggered event")
    tenant_id: str | None = Field(None, description="Tenant ID")
    action: str = Field(..., description="Action performed")
    before_state: dict | None = Field(None, description="State before action")
    after_state: dict | None = Field(None, description="State after action")
    evidence: dict | None = Field(None, description="Supporting evidence")
    metadata: dict | None = Field(None, description="Additional metadata")
