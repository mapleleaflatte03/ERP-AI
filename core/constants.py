"""
ERPX AI Accounting - System Constants
=====================================
"""

# API Version
API_VERSION = "1.0.0"
API_PREFIX = "/v1"

# Processing Modes
MODE_STRICT = "STRICT"
MODE_RELAXED = "RELAXED"

# Document Types
DOC_TYPE_RECEIPT = "receipt"
DOC_TYPE_VAT_INVOICE = "vat_invoice"
DOC_TYPE_BANK_SLIP = "bank_slip"
DOC_TYPE_OTHER = "other"

# Reconciliation Settings (R5 - Reconciliation Rules)
RECONCILIATION_AMOUNT_TOLERANCE_PERCENT = 0.5  # ±0.5%
RECONCILIATION_AMOUNT_TOLERANCE_VND = 50000  # ±50,000 VND
RECONCILIATION_DATE_WINDOW_DAYS = 7  # ±7 days

# VAT Rates (Vietnam)
VAT_RATES_VN = [0, 5, 8, 10]  # 0%, 5%, 8%, 10%
DEFAULT_VAT_RATE = 10

# Currency Codes
CURRENCY_VND = "VND"
CURRENCY_USD = "USD"
DEFAULT_CURRENCY = CURRENCY_VND

# Required Fields for VAT Invoice (STRICT mode)
VAT_INVOICE_REQUIRED_FIELDS = ["invoice_serial", "invoice_no", "invoice_date", "tax_id", "tax_account", "tax_group"]

# Required Fields for Receipt (RELAXED)
RECEIPT_REQUIRED_FIELDS = ["grand_total"]

# Approval Thresholds
APPROVAL_THRESHOLD_AUTO = 10_000_000  # Auto-approve under 10M VND
APPROVAL_THRESHOLD_MANAGER = 100_000_000  # Manager approval under 100M
# Above 100M requires director approval

# Database Tables
TABLE_TRANSACTIONS = "accounting_transactions"
TABLE_AUDIT_LOG = "audit_log"
TABLE_APPROVALS = "approval_queue"
TABLE_RECONCILIATION = "reconciliation_history"

# Qdrant Collections
QDRANT_COLLECTION_LAWS = "vn_accounting_laws"
QDRANT_COLLECTION_SOP = "company_sop"
QDRANT_COLLECTION_PATTERNS = "historical_patterns"

# MinIO Buckets
MINIO_BUCKET_RAW = "raw-documents"
MINIO_BUCKET_PROCESSED = "processed-documents"
MINIO_BUCKET_ARCHIVE = "archive-documents"

# Evidence Source Types
EVIDENCE_SOURCE_OCR = "ocr"
EVIDENCE_SOURCE_STRUCTURED = "structured"
EVIDENCE_SOURCE_DB = "db"
EVIDENCE_SOURCE_INFERRED = "inferred"

# Workflow States
WORKFLOW_STATE_INGEST = "ingest"
WORKFLOW_STATE_CLASSIFY = "classify"
WORKFLOW_STATE_EXTRACT = "extract"
WORKFLOW_STATE_VALIDATE = "validate"
WORKFLOW_STATE_RECONCILE = "reconcile"
WORKFLOW_STATE_DECISION = "decision"
WORKFLOW_STATE_COMPLETE = "complete"
WORKFLOW_STATE_ERROR = "error"

# Logging
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# OpenTelemetry
OTEL_SERVICE_NAME = "erpx-ai-accounting"
OTEL_TRACE_SAMPLE_RATE = 1.0

# MLflow
MLFLOW_EXPERIMENT_NAME = "erpx-accounting-copilot"
MLFLOW_TRACKING_URI = "http://localhost:5000"

# Rate Limiting (per tenant)
RATE_LIMIT_REQUESTS_PER_MINUTE = 100
RATE_LIMIT_REQUESTS_PER_DAY = 10000

# File Size Limits
MAX_FILE_SIZE_MB = 50
MAX_BATCH_SIZE = 100


# Document Type Enum
from enum import Enum


class DocumentType(str, Enum):
    """Document type classification"""

    INVOICE = "invoice"
    RECEIPT = "receipt"
    BANK_STATEMENT = "bank_statement"
    EXPENSE_REPORT = "expense_report"
    JOURNAL_ENTRY = "journal_entry"
    PURCHASE_ORDER = "purchase_order"
    PAYMENT_VOUCHER = "payment_voucher"
    CREDIT_NOTE = "credit_note"
    DEBIT_NOTE = "debit_note"


# VAT Rates
VAT_RATES = [0, 5, 8, 10]

# Reconciliation
RECONCILIATION_DATE_TOLERANCE_DAYS = 7
