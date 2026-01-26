"""
ERPX AI Accounting - Core Module
================================
Shared configurations, schemas, and utilities.
DO Agent qwen3-32b ONLY - NO LOCAL LLM
"""

import os
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

# =============================================================================
# Environment Configuration
# =============================================================================


@dataclass
class Config:
    """Application configuration from environment"""

    # LLM - DO Agent ONLY
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "do_agent")
    DO_AGENT_URL: str = os.getenv("DO_AGENT_URL", "https://gdfyu2bkvuq4idxkb6x2xkpe.agents.do-ai.run")
    DO_AGENT_KEY: str = os.getenv("DO_AGENT_KEY", "")
    DO_AGENT_MODEL: str = os.getenv("DO_AGENT_MODEL", "qwen3-32b")

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://erpx:erpx_secret@localhost:5432/erpx")

    # Storage
    MINIO_ENDPOINT: str = os.getenv("MINIO_ENDPOINT", "localhost:9000")
    MINIO_ACCESS_KEY: str = os.getenv("MINIO_ACCESS_KEY", "erpx_minio")
    MINIO_SECRET_KEY: str = os.getenv("MINIO_SECRET_KEY", "erpx_minio_secret")
    MINIO_BUCKET: str = os.getenv("MINIO_BUCKET", "erpx-documents")
    MINIO_SECURE: bool = os.getenv("MINIO_SECURE", "false").lower() == "true"

    # Vector DB
    QDRANT_URL: str = os.getenv("QDRANT_URL", "http://localhost:6333")
    QDRANT_TOP_K: int = int(os.getenv("QDRANT_TOP_K", "5"))

    # Workflow
    TEMPORAL_ADDRESS: str = os.getenv("TEMPORAL_ADDRESS", "temporal:7233")
    TEMPORAL_NAMESPACE: str = os.getenv("TEMPORAL_NAMESPACE", "default")
    TEMPORAL_TASK_QUEUE: str = os.getenv("TEMPORAL_TASK_QUEUE", "erpx-document-queue")

    # Policy
    OPA_URL: str = os.getenv("OPA_URL", "http://localhost:8181")

    # Observability
    OTEL_ENDPOINT: str = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317")

    # Feature Flags (PR14: Durable Ingestion)
    ENABLE_MINIO: bool = os.getenv("ENABLE_MINIO", "1") == "1"
    ENABLE_QDRANT: bool = os.getenv("ENABLE_QDRANT", "1") == "1"
    
    # Feature Flags (PR15: Observability)
    ENABLE_OTEL: bool = os.getenv("ENABLE_OTEL", "1") == "1"
    OTEL_SERVICE_NAME: str = os.getenv("OTEL_SERVICE_NAME", "erpx-api")
    
    # Feature Flags (PR16: Temporal Background Agent)
    ENABLE_TEMPORAL: bool = os.getenv("ENABLE_TEMPORAL", "0") == "1"

    # Guardrails
    MIN_CONFIDENCE: float = float(os.getenv("MIN_CONFIDENCE", "0.6"))
    HUMAN_REVIEW_THRESHOLD: float = float(os.getenv("HUMAN_REVIEW_THRESHOLD", "0.8"))
    MAX_FILE_SIZE_MB: int = int(os.getenv("MAX_FILE_SIZE_MB", "50"))

    # Telegram
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")

    # Email
    SMTP_HOST: str = os.getenv("SMTP_HOST", "localhost")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "1025"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM_EMAIL: str = os.getenv("SMTP_FROM_EMAIL", "noreply@erpx.ai")

    # API
    API_BASE_URL: str = os.getenv("API_BASE_URL", "http://localhost:8000")

    def validate(self):
        """Validate configuration - FAIL FAST if invalid"""
        if self.LLM_PROVIDER != "do_agent":
            raise ValueError(f"LLM_PROVIDER must be 'do_agent', got '{self.LLM_PROVIDER}'. NO LOCAL LLM ALLOWED!")
        if not self.DO_AGENT_KEY:
            raise ValueError("DO_AGENT_KEY is required. NO LOCAL LLM FALLBACK!")
        if not self.DO_AGENT_URL:
            raise ValueError("DO_AGENT_URL is required.")


config = Config()

# =============================================================================
# Enums
# =============================================================================


class JobStatus(str, Enum):
    """Job processing status"""

    PENDING = "pending"
    PROCESSING = "processing"
    EXTRACTING = "extracting"
    CLASSIFYING = "classifying"
    PROPOSING = "proposing"
    VALIDATING = "validating"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    POSTED = "posted"
    FAILED = "failed"


class DocumentType(str, Enum):
    """Document types"""

    PURCHASE_INVOICE = "purchase_invoice"
    SALES_INVOICE = "sales_invoice"
    RECEIPT = "receipt"
    PAYMENT_VOUCHER = "payment_voucher"
    BANK_STATEMENT = "bank_statement"
    EXPENSE_REPORT = "expense_report"
    CONTRACT = "contract"
    UNKNOWN = "unknown"


class ApprovalAction(str, Enum):
    """Approval actions"""

    APPROVE = "approve"
    REJECT = "reject"
    REQUEST_REVIEW = "request_review"


# =============================================================================
# Pydantic Schemas
# =============================================================================


class JournalLine(BaseModel):
    """Single journal entry line"""

    account_code: str = Field(..., description="Account code from chart of accounts")
    account_name: str = Field(..., description="Account name")
    debit: float = Field(default=0, ge=0, description="Debit amount")
    credit: float = Field(default=0, ge=0, description="Credit amount")
    description: str | None = None

    def model_post_init(self, __context):
        if self.debit > 0 and self.credit > 0:
            raise ValueError("Line cannot have both debit and credit")


class JournalProposal(BaseModel):
    """Journal entry proposal"""

    job_id: str
    doc_type: DocumentType
    description: str
    reference: str | None = None
    vendor_name: str | None = None
    invoice_number: str | None = None
    invoice_date: str | None = None
    total_amount: float = Field(ge=0)
    currency: str = Field(default="VND")
    vat_amount: float | None = Field(default=0, ge=0)
    entries: list[JournalLine] = Field(..., min_length=2)
    confidence: float = Field(ge=0, le=1)
    reasoning: str | None = None

    def is_balanced(self) -> bool:
        """Check if debit equals credit"""
        total_debit = sum(e.debit for e in self.entries)
        total_credit = sum(e.credit for e in self.entries)
        return abs(total_debit - total_credit) < 0.01

    def total_debit(self) -> float:
        return sum(e.debit for e in self.entries)

    def total_credit(self) -> float:
        return sum(e.credit for e in self.entries)


class ExtractedInvoice(BaseModel):
    """Extracted invoice data"""

    job_id: str
    raw_text: str
    vendor_name: str | None = None
    vendor_tax_id: str | None = None
    invoice_number: str | None = None
    invoice_date: str | None = None
    total_amount: float | None = None
    vat_amount: float | None = None
    currency: str = "VND"
    line_items: list[dict] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    extraction_method: str = "ocr"


class JobRecord(BaseModel):
    """Job record schema"""

    job_id: str
    company_id: str = "default"
    user_id: str | None = None
    status: JobStatus = JobStatus.PENDING
    document_type: DocumentType | None = None
    filename: str
    content_type: str
    file_size: int
    minio_bucket: str
    minio_key: str
    extracted_data: dict | None = None
    journal_proposal: dict | None = None
    validation_result: dict | None = None
    approval_state: str | None = None
    approved_by: str | None = None
    approved_at: datetime | None = None
    ledger_posted: bool = False
    ledger_entry_id: str | None = None
    error_message: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class LLMCallLog(BaseModel):
    """LLM call log for observability"""

    request_id: str
    job_id: str | None = None
    llm_provider: str = "do_agent"
    model: str = "qwen3-32b"
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    latency_ms: float
    status: str  # success, error
    error_message: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


# =============================================================================
# Constants
# =============================================================================

ALLOWED_FILE_TYPES = {
    "application/pdf": [".pdf"],
    "image/png": [".png"],
    "image/jpeg": [".jpg", ".jpeg"],
    "image/jpg": [".jpg"],
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
    "application/vnd.ms-excel": [".xls"],
}

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".xlsx", ".xls"}

# Vietnamese Chart of Accounts (TT200/TT133)
CHART_OF_ACCOUNTS = {
    # Assets
    "111": "Tiền mặt",
    "112": "Tiền gửi ngân hàng",
    "131": "Phải thu của khách hàng",
    "133": "Thuế GTGT được khấu trừ",
    "141": "Tạm ứng",
    "152": "Nguyên liệu, vật liệu",
    "153": "Công cụ, dụng cụ",
    "154": "Chi phí SXKD dở dang",
    "155": "Thành phẩm",
    "156": "Hàng hóa",
    "211": "TSCĐ hữu hình",
    "214": "Hao mòn TSCĐ",
    # Liabilities
    "331": "Phải trả người bán",
    "333": "Thuế và các khoản phải nộp NN",
    "3331": "Thuế GTGT phải nộp",
    "334": "Phải trả người lao động",
    "338": "Phải trả, phải nộp khác",
    "341": "Vay và nợ thuê tài chính",
    # Equity
    "411": "Vốn đầu tư của chủ sở hữu",
    "421": "Lợi nhuận sau thuế chưa phân phối",
    # Revenue
    "511": "Doanh thu bán hàng và cung cấp dịch vụ",
    "515": "Doanh thu hoạt động tài chính",
    # Expenses
    "621": "Chi phí nguyên liệu, vật liệu trực tiếp",
    "622": "Chi phí nhân công trực tiếp",
    "627": "Chi phí sản xuất chung",
    "632": "Giá vốn hàng bán",
    "635": "Chi phí tài chính",
    "641": "Chi phí bán hàng",
    "642": "Chi phí quản lý doanh nghiệp",
    "811": "Chi phí khác",
    "821": "Chi phí thuế thu nhập doanh nghiệp",
    "911": "Xác định kết quả kinh doanh",
}

__all__ = [
    "config",
    "Config",
    "JobStatus",
    "DocumentType",
    "ApprovalAction",
    "JournalLine",
    "JournalProposal",
    "ExtractedInvoice",
    "JobRecord",
    "LLMCallLog",
    "ALLOWED_FILE_TYPES",
    "ALLOWED_EXTENSIONS",
    "CHART_OF_ACCOUNTS",
]
