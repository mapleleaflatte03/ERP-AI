"""
ERPX AI Accounting - PostgreSQL Mock Data Layer
================================================
Mock implementation of PostgreSQL database for:
- Accounting transactions
- Audit logs
- Approval queue
- Reconciliation history
"""

import os
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any


@dataclass
class Transaction:
    """Accounting transaction record"""

    id: str
    tenant_id: str
    doc_id: str
    doc_type: str
    posting_date: str
    doc_date: str
    vendor_id: str | None
    vendor_name: str | None
    description: str | None
    currency: str
    amount: float
    vat_amount: float | None
    status: str  # draft, pending, approved, posted
    created_at: str
    updated_at: str
    created_by: str | None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AuditLogEntry:
    """Audit log entry"""

    id: str
    timestamp: str
    tenant_id: str
    user_id: str | None
    action: str
    entity_type: str
    entity_id: str
    before_state: dict[str, Any] | None
    after_state: dict[str, Any] | None
    evidence: dict[str, Any] | None
    ip_address: str | None
    user_agent: str | None


@dataclass
class ApprovalQueueItem:
    """Approval queue item"""

    id: str
    tenant_id: str
    doc_id: str
    doc_type: str
    payload: dict[str, Any]
    status: str  # pending, approved, rejected
    created_at: str
    assigned_to: str | None
    reviewed_at: str | None
    reviewer_notes: str | None
    review_reasons: list[str] = field(default_factory=list)


class PostgresMock:
    """
    Mock PostgreSQL database.
    In production, replace with psycopg2/asyncpg connection.
    """

    def __init__(self, db_url: str = None):
        self.db_url = db_url or os.getenv("DATABASE_URL", "mock://localhost/erpx")
        self._lock = threading.Lock()

        # In-memory storage
        self._transactions: dict[str, Transaction] = {}
        self._audit_log: list[AuditLogEntry] = []
        self._approval_queue: dict[str, ApprovalQueueItem] = {}
        self._reconciliation_history: list[dict[str, Any]] = []

        # Initialize with mock data
        self._init_mock_data()

    def _init_mock_data(self):
        """Initialize mock data for testing"""
        # Sample transactions
        for i in range(10):
            txn_id = f"TXN-{i + 1:04d}"
            self._transactions[txn_id] = Transaction(
                id=txn_id,
                tenant_id="tenant-001",
                doc_id=f"INV-{i + 1:04d}",
                doc_type="vat_invoice",
                posting_date=(datetime.now() - timedelta(days=i)).strftime("%d/%m/%Y"),
                doc_date=(datetime.now() - timedelta(days=i)).strftime("%d/%m/%Y"),
                vendor_id=f"V{i + 1:03d}",
                vendor_name=f"Vendor {i + 1}",
                description=f"Purchase order {i + 1}",
                currency="VND",
                amount=1000000 * (i + 1),
                vat_amount=100000 * (i + 1),
                status="posted" if i < 5 else "pending",
                created_at=datetime.utcnow().isoformat(),
                updated_at=datetime.utcnow().isoformat(),
                created_by="system",
            )

    # =========================================================================
    # TRANSACTION OPERATIONS
    # =========================================================================

    def insert_transaction(self, txn: Transaction) -> str:
        """Insert a new transaction"""
        with self._lock:
            if not txn.id:
                txn.id = str(uuid.uuid4())
            txn.created_at = datetime.utcnow().isoformat()
            txn.updated_at = txn.created_at
            self._transactions[txn.id] = txn
            return txn.id

    def get_transaction(self, txn_id: str) -> Transaction | None:
        """Get transaction by ID"""
        return self._transactions.get(txn_id)

    def list_transactions(
        self,
        tenant_id: str = None,
        status: str = None,
        from_date: str = None,
        to_date: str = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Transaction]:
        """List transactions with filters"""
        results = list(self._transactions.values())

        if tenant_id:
            results = [t for t in results if t.tenant_id == tenant_id]
        if status:
            results = [t for t in results if t.status == status]

        return results[offset : offset + limit]

    def update_transaction(self, txn_id: str, updates: dict[str, Any]) -> bool:
        """Update a transaction"""
        with self._lock:
            if txn_id not in self._transactions:
                return False

            txn = self._transactions[txn_id]
            for key, value in updates.items():
                if hasattr(txn, key):
                    setattr(txn, key, value)
            txn.updated_at = datetime.utcnow().isoformat()
            return True

    # =========================================================================
    # AUDIT LOG OPERATIONS
    # =========================================================================

    def log_audit(
        self,
        tenant_id: str,
        action: str,
        entity_type: str,
        entity_id: str,
        user_id: str = None,
        before_state: dict = None,
        after_state: dict = None,
        evidence: dict = None,
    ) -> str:
        """Log an audit entry"""
        entry = AuditLogEntry(
            id=str(uuid.uuid4()),
            timestamp=datetime.utcnow().isoformat(),
            tenant_id=tenant_id,
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            before_state=before_state,
            after_state=after_state,
            evidence=evidence,
            ip_address=None,
            user_agent=None,
        )

        with self._lock:
            self._audit_log.append(entry)

        return entry.id

    def get_audit_log(
        self, tenant_id: str = None, entity_id: str = None, action: str = None, limit: int = 100
    ) -> list[AuditLogEntry]:
        """Get audit log entries"""
        results = self._audit_log.copy()

        if tenant_id:
            results = [e for e in results if e.tenant_id == tenant_id]
        if entity_id:
            results = [e for e in results if e.entity_id == entity_id]
        if action:
            results = [e for e in results if e.action == action]

        return sorted(results, key=lambda x: x.timestamp, reverse=True)[:limit]

    # =========================================================================
    # APPROVAL QUEUE OPERATIONS
    # =========================================================================

    def create_approval(
        self, tenant_id: str, doc_id: str, doc_type: str, payload: dict[str, Any], review_reasons: list[str] = None
    ) -> str:
        """Create an approval request"""
        approval_id = str(uuid.uuid4())

        item = ApprovalQueueItem(
            id=approval_id,
            tenant_id=tenant_id,
            doc_id=doc_id,
            doc_type=doc_type,
            payload=payload,
            status="pending",
            created_at=datetime.utcnow().isoformat(),
            assigned_to=None,
            reviewed_at=None,
            reviewer_notes=None,
            review_reasons=review_reasons or [],
        )

        with self._lock:
            self._approval_queue[approval_id] = item

        return approval_id

    def get_approval(self, approval_id: str) -> ApprovalQueueItem | None:
        """Get approval by ID"""
        return self._approval_queue.get(approval_id)

    def list_approvals(
        self, tenant_id: str = None, status: str = None, assigned_to: str = None, limit: int = 50
    ) -> list[ApprovalQueueItem]:
        """List approval requests"""
        results = list(self._approval_queue.values())

        if tenant_id:
            results = [a for a in results if a.tenant_id == tenant_id]
        if status:
            results = [a for a in results if a.status == status]
        if assigned_to:
            results = [a for a in results if a.assigned_to == assigned_to]

        return sorted(results, key=lambda x: x.created_at, reverse=True)[:limit]

    def decide_approval(self, approval_id: str, decision: str, reviewer: str, notes: str = None) -> bool:
        """Make approval decision"""
        with self._lock:
            if approval_id not in self._approval_queue:
                return False

            item = self._approval_queue[approval_id]
            item.status = "approved" if decision == "approve" else "rejected"
            item.reviewed_at = datetime.utcnow().isoformat()
            item.assigned_to = reviewer
            item.reviewer_notes = notes
            return True

    # =========================================================================
    # RECONCILIATION HISTORY
    # =========================================================================

    def save_reconciliation(
        self,
        tenant_id: str,
        invoice_id: str,
        bank_txn_id: str,
        match_score: float,
        amount_diff: float,
        matched_by: str = "system",
    ) -> str:
        """Save reconciliation record"""
        record_id = str(uuid.uuid4())

        record = {
            "id": record_id,
            "tenant_id": tenant_id,
            "invoice_id": invoice_id,
            "bank_txn_id": bank_txn_id,
            "match_score": match_score,
            "amount_diff": amount_diff,
            "matched_at": datetime.utcnow().isoformat(),
            "matched_by": matched_by,
        }

        with self._lock:
            self._reconciliation_history.append(record)

        return record_id

    def get_reconciliation_history(
        self, tenant_id: str = None, invoice_id: str = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Get reconciliation history"""
        results = self._reconciliation_history.copy()

        if tenant_id:
            results = [r for r in results if r.get("tenant_id") == tenant_id]
        if invoice_id:
            results = [r for r in results if r.get("invoice_id") == invoice_id]

        return sorted(results, key=lambda x: x.get("matched_at", ""), reverse=True)[:limit]


class TransactionRepository:
    """
    Repository pattern wrapper for transaction operations.
    Provides cleaner interface for business logic.
    """

    def __init__(self, db: PostgresMock = None):
        self.db = db or PostgresMock()

    def create(self, tenant_id: str, doc_id: str, doc_type: str, amount: float, **kwargs) -> str:
        """Create a new transaction"""
        txn = Transaction(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            doc_id=doc_id,
            doc_type=doc_type,
            posting_date=kwargs.get("posting_date", datetime.now().strftime("%d/%m/%Y")),
            doc_date=kwargs.get("doc_date", datetime.now().strftime("%d/%m/%Y")),
            vendor_id=kwargs.get("vendor_id"),
            vendor_name=kwargs.get("vendor_name"),
            description=kwargs.get("description"),
            currency=kwargs.get("currency", "VND"),
            amount=amount,
            vat_amount=kwargs.get("vat_amount"),
            status=kwargs.get("status", "draft"),
            created_at=datetime.utcnow().isoformat(),
            updated_at=datetime.utcnow().isoformat(),
            created_by=kwargs.get("created_by"),
        )

        return self.db.insert_transaction(txn)

    def get_by_id(self, txn_id: str) -> Transaction | None:
        """Get transaction by ID"""
        return self.db.get_transaction(txn_id)

    def list_pending(self, tenant_id: str, limit: int = 100) -> list[Transaction]:
        """List pending transactions"""
        return self.db.list_transactions(tenant_id=tenant_id, status="pending", limit=limit)

    def approve(self, txn_id: str, approved_by: str) -> bool:
        """Approve a transaction"""
        return self.db.update_transaction(txn_id, {"status": "approved", "updated_by": approved_by})

    def post_to_ledger(self, txn_id: str, posted_by: str) -> bool:
        """Post transaction to ledger"""
        return self.db.update_transaction(txn_id, {"status": "posted", "updated_by": posted_by})


# =============================================================================
# SQL SCHEMA (for reference / future migration)
# =============================================================================

POSTGRES_SCHEMA = """
-- ERPX AI Accounting - PostgreSQL Schema
-- ======================================

-- Tenants
CREATE TABLE IF NOT EXISTS tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    settings JSONB DEFAULT '{}',
    quota_limit INTEGER DEFAULT 10000,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Accounting Transactions
CREATE TABLE IF NOT EXISTS accounting_transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    doc_id VARCHAR(100) NOT NULL,
    doc_type VARCHAR(50) NOT NULL,
    posting_date DATE NOT NULL,
    doc_date DATE,
    vendor_id VARCHAR(100),
    vendor_name VARCHAR(255),
    description TEXT,
    currency VARCHAR(3) DEFAULT 'VND',
    amount DECIMAL(18, 2) NOT NULL,
    vat_amount DECIMAL(18, 2),
    status VARCHAR(20) DEFAULT 'draft',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by VARCHAR(100),
    metadata JSONB DEFAULT '{}',
    
    CONSTRAINT unique_tenant_doc UNIQUE (tenant_id, doc_id)
);

CREATE INDEX idx_txn_tenant ON accounting_transactions(tenant_id);
CREATE INDEX idx_txn_status ON accounting_transactions(status);
CREATE INDEX idx_txn_posting_date ON accounting_transactions(posting_date);

-- Audit Log
CREATE TABLE IF NOT EXISTS audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    user_id VARCHAR(100),
    action VARCHAR(100) NOT NULL,
    entity_type VARCHAR(100) NOT NULL,
    entity_id VARCHAR(100) NOT NULL,
    before_state JSONB,
    after_state JSONB,
    evidence JSONB,
    ip_address INET,
    user_agent TEXT
);

CREATE INDEX idx_audit_tenant ON audit_log(tenant_id);
CREATE INDEX idx_audit_entity ON audit_log(entity_type, entity_id);
CREATE INDEX idx_audit_timestamp ON audit_log(timestamp);

-- Approval Queue
CREATE TABLE IF NOT EXISTS approval_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    doc_id VARCHAR(100) NOT NULL,
    doc_type VARCHAR(50) NOT NULL,
    payload JSONB NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    assigned_to VARCHAR(100),
    reviewed_at TIMESTAMPTZ,
    reviewer_notes TEXT,
    review_reasons TEXT[]
);

CREATE INDEX idx_approval_tenant ON approval_queue(tenant_id);
CREATE INDEX idx_approval_status ON approval_queue(status);

-- Reconciliation History
CREATE TABLE IF NOT EXISTS reconciliation_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    invoice_id VARCHAR(100) NOT NULL,
    bank_txn_id VARCHAR(100) NOT NULL,
    match_score DECIMAL(5, 4),
    amount_diff DECIMAL(18, 2),
    matched_at TIMESTAMPTZ DEFAULT NOW(),
    matched_by VARCHAR(100)
);

CREATE INDEX idx_recon_tenant ON reconciliation_history(tenant_id);
CREATE INDEX idx_recon_invoice ON reconciliation_history(invoice_id);

-- Ledger Zone (for posted transactions)
CREATE TABLE IF NOT EXISTS ledger_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    transaction_id UUID NOT NULL REFERENCES accounting_transactions(id),
    account_code VARCHAR(20) NOT NULL,
    debit_amount DECIMAL(18, 2) DEFAULT 0,
    credit_amount DECIMAL(18, 2) DEFAULT 0,
    posting_date DATE NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_ledger_tenant ON ledger_entries(tenant_id);
CREATE INDEX idx_ledger_account ON ledger_entries(account_code);
CREATE INDEX idx_ledger_posting_date ON ledger_entries(posting_date);
"""


if __name__ == "__main__":
    # Test mock database
    db = PostgresMock()

    # List transactions
    print("Transactions:")
    for txn in db.list_transactions(limit=5):
        print(f"  {txn.id}: {txn.doc_id} - {txn.amount} VND - {txn.status}")

    # Create approval
    approval_id = db.create_approval(
        tenant_id="tenant-001",
        doc_id="INV-TEST",
        doc_type="vat_invoice",
        payload={"test": True},
        review_reasons=["Missing invoice_serial"],
    )
    print(f"\nCreated approval: {approval_id}")

    # Log audit
    audit_id = db.log_audit(
        tenant_id="tenant-001",
        action="create",
        entity_type="transaction",
        entity_id="TXN-0001",
        user_id="admin",
        after_state={"status": "created"},
    )
    print(f"Logged audit: {audit_id}")

    print("\n-- PostgreSQL Schema --")
    print(POSTGRES_SCHEMA[:500] + "...")
