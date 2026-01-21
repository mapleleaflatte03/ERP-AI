"""
ERPX AI Accounting - Approval Inbox
====================================
Manages approval workflow for documents requiring human review (R6 - Approval Gate).
"""

import json
import os
import threading
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class ApprovalStatus(str, Enum):
    """Approval request status"""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    ESCALATED = "escalated"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class ApprovalPriority(str, Enum):
    """Priority levels for approval requests"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class ApprovalReason(str, Enum):
    """Reasons for requiring approval"""

    AMOUNT_THRESHOLD = "amount_threshold"
    NEW_VENDOR = "new_vendor"
    NEW_ACCOUNT = "new_account"
    UNUSUAL_TRANSACTION = "unusual_transaction"
    POLICY_VIOLATION = "policy_violation"
    LOW_CONFIDENCE = "low_confidence"
    MISSING_EVIDENCE = "missing_evidence"
    VAT_ANOMALY = "vat_anomaly"
    DATE_ANOMALY = "date_anomaly"
    MANUAL_REQUEST = "manual_request"


@dataclass
class ApprovalRequest:
    """
    Approval request record.

    Implements R6 - Approval Gate
    """

    # Identifiers
    request_id: str
    doc_id: str
    tenant_id: str

    # Request details
    created_at: str
    created_by: str  # System or user who created the request

    # Status
    status: str = ApprovalStatus.PENDING.value

    # Why approval is needed
    reasons: list[str] = field(default_factory=list)

    # Priority
    priority: str = ApprovalPriority.MEDIUM.value

    # Context
    document_type: str | None = None
    amount: float | None = None
    currency: str = "VND"
    vendor: str | None = None
    proposed_coding: dict[str, Any] | None = None

    # Evidence summary
    evidence_summary: str | None = None

    # Approval workflow
    assigned_to: str | None = None
    escalation_path: list[str] = field(default_factory=list)

    # Resolution
    resolved_at: str | None = None
    resolved_by: str | None = None
    resolution_notes: str | None = None
    approved_coding: dict[str, Any] | None = None

    # Metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ApprovalRequest":
        return cls(**data)


class ApprovalInbox:
    """
    Manages approval requests and workflow.

    Features:
    - Create approval requests
    - Assign to approvers
    - Approve/reject requests
    - Escalation handling
    - Audit trail
    """

    def __init__(self, storage_path: str = None, on_approved: Callable = None, on_rejected: Callable = None):
        self.storage_path = storage_path or os.getenv("APPROVAL_STORAGE_PATH", "data/approvals")
        self._lock = threading.Lock()

        # In-memory storage
        self._requests: dict[str, ApprovalRequest] = {}  # request_id -> ApprovalRequest
        self._doc_index: dict[str, str] = {}  # doc_id -> request_id
        self._assignee_index: dict[str, list[str]] = {}  # assignee -> [request_ids]

        # Callbacks
        self.on_approved = on_approved
        self.on_rejected = on_rejected

        # Ensure storage directory exists
        os.makedirs(self.storage_path, exist_ok=True)

    def create_request(
        self,
        doc_id: str,
        tenant_id: str,
        created_by: str = "system",
        reasons: list[ApprovalReason] = None,
        priority: ApprovalPriority = ApprovalPriority.MEDIUM,
        document_type: str = None,
        amount: float = None,
        currency: str = "VND",
        vendor: str = None,
        proposed_coding: dict[str, Any] = None,
        evidence_summary: str = None,
        assigned_to: str = None,
        escalation_path: list[str] = None,
        metadata: dict = None,
    ) -> str:
        """
        Create a new approval request.

        Returns:
            Request ID
        """
        request_id = f"APR-{str(uuid.uuid4())[:8].upper()}"

        # Convert reasons to strings
        reason_strs = [r.value if isinstance(r, ApprovalReason) else r for r in (reasons or [])]

        request = ApprovalRequest(
            request_id=request_id,
            doc_id=doc_id,
            tenant_id=tenant_id,
            created_at=datetime.utcnow().isoformat() + "Z",
            created_by=created_by,
            reasons=reason_strs,
            priority=priority.value if isinstance(priority, ApprovalPriority) else priority,
            document_type=document_type,
            amount=amount,
            currency=currency,
            vendor=vendor,
            proposed_coding=proposed_coding,
            evidence_summary=evidence_summary,
            assigned_to=assigned_to,
            escalation_path=escalation_path or [],
            metadata=metadata or {},
        )

        with self._lock:
            self._requests[request_id] = request
            self._doc_index[doc_id] = request_id

            if assigned_to:
                if assigned_to not in self._assignee_index:
                    self._assignee_index[assigned_to] = []
                self._assignee_index[assigned_to].append(request_id)

        # Persist
        self._persist_request(request)

        return request_id

    def _persist_request(self, request: ApprovalRequest):
        """Persist request to file"""
        filename = os.path.join(self.storage_path, f"{request.request_id}.json")

        with open(filename, "w", encoding="utf-8") as f:
            json.dump(request.to_dict(), f, ensure_ascii=False, indent=2)

    def get(self, request_id: str) -> ApprovalRequest | None:
        """Get request by ID"""
        return self._requests.get(request_id)

    def get_for_document(self, doc_id: str) -> ApprovalRequest | None:
        """Get approval request for a document"""
        request_id = self._doc_index.get(doc_id)
        if request_id:
            return self._requests.get(request_id)
        return None

    def get_pending(
        self, tenant_id: str = None, assigned_to: str = None, priority: ApprovalPriority = None
    ) -> list[ApprovalRequest]:
        """Get pending approval requests with optional filters"""
        pending = [r for r in self._requests.values() if r.status == ApprovalStatus.PENDING.value]

        if tenant_id:
            pending = [r for r in pending if r.tenant_id == tenant_id]

        if assigned_to:
            pending = [r for r in pending if r.assigned_to == assigned_to]

        if priority:
            priority_val = priority.value if isinstance(priority, ApprovalPriority) else priority
            pending = [r for r in pending if r.priority == priority_val]

        # Sort by priority and creation time
        priority_order = {
            ApprovalPriority.URGENT.value: 0,
            ApprovalPriority.HIGH.value: 1,
            ApprovalPriority.MEDIUM.value: 2,
            ApprovalPriority.LOW.value: 3,
        }

        pending.sort(key=lambda r: (priority_order.get(r.priority, 99), r.created_at))

        return pending

    def approve(
        self, request_id: str, approved_by: str, notes: str = None, approved_coding: dict[str, Any] = None
    ) -> bool:
        """
        Approve a request.

        Args:
            request_id: The request to approve
            approved_by: User approving
            notes: Optional notes
            approved_coding: Optional modified coding

        Returns:
            True if successful
        """
        request = self.get(request_id)
        if not request or request.status != ApprovalStatus.PENDING.value:
            return False

        with self._lock:
            request.status = ApprovalStatus.APPROVED.value
            request.resolved_at = datetime.utcnow().isoformat() + "Z"
            request.resolved_by = approved_by
            request.resolution_notes = notes
            request.approved_coding = approved_coding or request.proposed_coding

        # Persist
        self._persist_request(request)

        # Callback
        if self.on_approved:
            self.on_approved(request)

        return True

    def reject(self, request_id: str, rejected_by: str, notes: str = None) -> bool:
        """
        Reject a request.

        Args:
            request_id: The request to reject
            rejected_by: User rejecting
            notes: Reason for rejection

        Returns:
            True if successful
        """
        request = self.get(request_id)
        if not request or request.status != ApprovalStatus.PENDING.value:
            return False

        with self._lock:
            request.status = ApprovalStatus.REJECTED.value
            request.resolved_at = datetime.utcnow().isoformat() + "Z"
            request.resolved_by = rejected_by
            request.resolution_notes = notes

        # Persist
        self._persist_request(request)

        # Callback
        if self.on_rejected:
            self.on_rejected(request)

        return True

    def escalate(self, request_id: str, escalated_by: str, escalate_to: str, notes: str = None) -> bool:
        """
        Escalate a request to a higher approver.

        Args:
            request_id: The request to escalate
            escalated_by: User escalating
            escalate_to: New assignee
            notes: Escalation reason

        Returns:
            True if successful
        """
        request = self.get(request_id)
        if not request or request.status != ApprovalStatus.PENDING.value:
            return False

        with self._lock:
            # Update assignee
            old_assignee = request.assigned_to
            request.assigned_to = escalate_to
            request.status = ApprovalStatus.ESCALATED.value

            # Update escalation history
            if "escalation_history" not in request.metadata:
                request.metadata["escalation_history"] = []
            request.metadata["escalation_history"].append(
                {
                    "from": old_assignee,
                    "to": escalate_to,
                    "by": escalated_by,
                    "at": datetime.utcnow().isoformat() + "Z",
                    "notes": notes,
                }
            )

            # Reset to pending for new assignee
            request.status = ApprovalStatus.PENDING.value

            # Update indexes
            if old_assignee and old_assignee in self._assignee_index:
                self._assignee_index[old_assignee].remove(request_id)

            if escalate_to not in self._assignee_index:
                self._assignee_index[escalate_to] = []
            self._assignee_index[escalate_to].append(request_id)

        # Persist
        self._persist_request(request)

        return True

    def assign(self, request_id: str, assign_to: str, assigned_by: str = "system") -> bool:
        """Assign a request to an approver"""
        request = self.get(request_id)
        if not request:
            return False

        with self._lock:
            old_assignee = request.assigned_to
            request.assigned_to = assign_to

            # Update indexes
            if old_assignee and old_assignee in self._assignee_index:
                if request_id in self._assignee_index[old_assignee]:
                    self._assignee_index[old_assignee].remove(request_id)

            if assign_to not in self._assignee_index:
                self._assignee_index[assign_to] = []
            self._assignee_index[assign_to].append(request_id)

        # Persist
        self._persist_request(request)

        return True

    def get_statistics(self, tenant_id: str = None) -> dict[str, Any]:
        """Get approval statistics"""
        requests = list(self._requests.values())

        if tenant_id:
            requests = [r for r in requests if r.tenant_id == tenant_id]

        by_status = {}
        for r in requests:
            if r.status not in by_status:
                by_status[r.status] = 0
            by_status[r.status] += 1

        by_priority = {}
        for r in requests:
            if r.priority not in by_priority:
                by_priority[r.priority] = 0
            by_priority[r.priority] += 1

        by_reason = {}
        for r in requests:
            for reason in r.reasons:
                if reason not in by_reason:
                    by_reason[reason] = 0
                by_reason[reason] += 1

        return {"total": len(requests), "by_status": by_status, "by_priority": by_priority, "by_reason": by_reason}


# Global approval inbox instance
_approval_inbox: ApprovalInbox | None = None


def get_approval_inbox() -> ApprovalInbox:
    """Get the global approval inbox"""
    global _approval_inbox
    if _approval_inbox is None:
        _approval_inbox = ApprovalInbox()
    return _approval_inbox


if __name__ == "__main__":
    # Test approval inbox
    inbox = ApprovalInbox(storage_path="data/approvals_test")

    # Create request
    req_id = inbox.create_request(
        doc_id="DOC-001",
        tenant_id="tenant-001",
        reasons=[ApprovalReason.AMOUNT_THRESHOLD, ApprovalReason.NEW_VENDOR],
        priority=ApprovalPriority.HIGH,
        document_type="invoice",
        amount=150_000_000,
        vendor="ABC Corp",
        proposed_coding={"debit_account": "331", "credit_account": "111"},
        evidence_summary="Invoice from new vendor with large amount",
        assigned_to="kế toán trưởng",
    )
    print(f"Created request: {req_id}")

    # Get pending
    pending = inbox.get_pending()
    print(f"\nPending requests: {len(pending)}")
    for r in pending:
        print(f"  - {r.request_id}: {r.document_type}, {r.amount:,.0f} VND")

    # Approve
    inbox.approve(
        request_id=req_id, approved_by="nguyen.van.a@company.com", notes="Confirmed with vendor, OK to process"
    )
    print(f"\nApproved request: {req_id}")

    # Get statistics
    stats = inbox.get_statistics()
    print(f"\nStatistics: {stats}")
