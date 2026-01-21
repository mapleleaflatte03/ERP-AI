"""
ERPX AI Accounting - Audit Store
================================
Stores audit trail for all operations.
Answers: Who, What, When, Why, and What Changed.
"""

import json
import os
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class AuditEventType(str, Enum):
    """Types of audit events"""

    DOCUMENT_INGESTED = "document_ingested"
    DOCUMENT_PROCESSED = "document_processed"
    DOCUMENT_CLASSIFIED = "document_classified"
    FIELDS_EXTRACTED = "fields_extracted"
    VALIDATION_PERFORMED = "validation_performed"
    RECONCILIATION_PERFORMED = "reconciliation_performed"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_REJECTED = "approval_rejected"
    TRANSACTION_CREATED = "transaction_created"
    TRANSACTION_UPDATED = "transaction_updated"
    TRANSACTION_POSTED = "transaction_posted"
    ERROR_OCCURRED = "error_occurred"


@dataclass
class AuditEvent:
    """
    Audit event record.

    Captures: Who, What, When, Why, and Version
    """

    # Identifiers
    event_id: str
    timestamp: str

    # Who
    tenant_id: str
    user_id: str | None = None
    system_component: str | None = None

    # What
    event_type: str = ""
    action: str = ""
    entity_type: str = ""
    entity_id: str = ""

    # Details
    description: str = ""
    before_state: dict[str, Any] | None = None
    after_state: dict[str, Any] | None = None

    # Why (evidence/reason)
    reason: str | None = None
    evidence: dict[str, Any] | None = None

    # Version tracking
    version: int = 1

    # Context
    request_id: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AuditEvent":
        return cls(**data)


class AuditStore:
    """
    Audit store for maintaining audit trail.

    Features:
    - Immutable audit log
    - Full version history
    - Query by entity, user, time range
    - Export for compliance
    """

    def __init__(self, storage_path: str = None):
        self.storage_path = storage_path or os.getenv("AUDIT_STORAGE_PATH", "data/audit")
        self._lock = threading.Lock()
        self._events: list[AuditEvent] = []
        self._entity_versions: dict[str, int] = {}  # entity_id -> current version

        # Ensure storage directory exists
        os.makedirs(self.storage_path, exist_ok=True)

    def log(
        self,
        event_type: AuditEventType,
        tenant_id: str,
        entity_type: str,
        entity_id: str,
        action: str,
        user_id: str = None,
        system_component: str = None,
        description: str = None,
        before_state: dict = None,
        after_state: dict = None,
        reason: str = None,
        evidence: dict = None,
        request_id: str = None,
        ip_address: str = None,
        metadata: dict = None,
    ) -> str:
        """
        Log an audit event.

        Returns:
            Event ID
        """
        event_id = str(uuid.uuid4())

        # Get next version for entity
        entity_key = f"{entity_type}:{entity_id}"
        with self._lock:
            current_version = self._entity_versions.get(entity_key, 0)
            new_version = current_version + 1
            self._entity_versions[entity_key] = new_version

        event = AuditEvent(
            event_id=event_id,
            timestamp=datetime.utcnow().isoformat() + "Z",
            tenant_id=tenant_id,
            user_id=user_id,
            system_component=system_component or "erpx-copilot",
            event_type=event_type.value if isinstance(event_type, AuditEventType) else event_type,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            description=description or f"{action} {entity_type} {entity_id}",
            before_state=before_state,
            after_state=after_state,
            reason=reason,
            evidence=evidence,
            version=new_version,
            request_id=request_id,
            ip_address=ip_address,
            metadata=metadata or {},
        )

        with self._lock:
            self._events.append(event)

        # Persist to file (append-only)
        self._persist_event(event)

        return event_id

    def _persist_event(self, event: AuditEvent):
        """Persist event to file"""
        date_str = datetime.utcnow().strftime("%Y%m%d")
        filename = os.path.join(self.storage_path, f"audit_{date_str}.jsonl")

        with open(filename, "a", encoding="utf-8") as f:
            f.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")

    def get_event(self, event_id: str) -> AuditEvent | None:
        """Get event by ID"""
        for event in self._events:
            if event.event_id == event_id:
                return event
        return None

    def get_entity_history(self, entity_type: str, entity_id: str, limit: int = 100) -> list[AuditEvent]:
        """Get audit history for an entity"""
        events = [e for e in self._events if e.entity_type == entity_type and e.entity_id == entity_id]
        return sorted(events, key=lambda x: x.timestamp, reverse=True)[:limit]

    def get_user_activity(
        self, user_id: str, from_time: str = None, to_time: str = None, limit: int = 100
    ) -> list[AuditEvent]:
        """Get audit events for a user"""
        events = [e for e in self._events if e.user_id == user_id]

        if from_time:
            events = [e for e in events if e.timestamp >= from_time]
        if to_time:
            events = [e for e in events if e.timestamp <= to_time]

        return sorted(events, key=lambda x: x.timestamp, reverse=True)[:limit]

    def get_tenant_events(
        self,
        tenant_id: str,
        event_type: AuditEventType = None,
        from_time: str = None,
        to_time: str = None,
        limit: int = 1000,
    ) -> list[AuditEvent]:
        """Get audit events for a tenant"""
        events = [e for e in self._events if e.tenant_id == tenant_id]

        if event_type:
            type_str = event_type.value if isinstance(event_type, AuditEventType) else event_type
            events = [e for e in events if e.event_type == type_str]
        if from_time:
            events = [e for e in events if e.timestamp >= from_time]
        if to_time:
            events = [e for e in events if e.timestamp <= to_time]

        return sorted(events, key=lambda x: x.timestamp, reverse=True)[:limit]

    def search(
        self,
        query: str = None,
        tenant_id: str = None,
        entity_type: str = None,
        event_type: str = None,
        user_id: str = None,
        from_time: str = None,
        to_time: str = None,
        limit: int = 100,
    ) -> list[AuditEvent]:
        """Search audit events"""
        events = self._events.copy()

        if tenant_id:
            events = [e for e in events if e.tenant_id == tenant_id]
        if entity_type:
            events = [e for e in events if e.entity_type == entity_type]
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        if user_id:
            events = [e for e in events if e.user_id == user_id]
        if from_time:
            events = [e for e in events if e.timestamp >= from_time]
        if to_time:
            events = [e for e in events if e.timestamp <= to_time]
        if query:
            query_lower = query.lower()
            events = [
                e
                for e in events
                if query_lower in (e.description or "").lower() or query_lower in (e.entity_id or "").lower()
            ]

        return sorted(events, key=lambda x: x.timestamp, reverse=True)[:limit]

    def export_for_compliance(self, tenant_id: str, from_time: str, to_time: str, output_path: str = None) -> str:
        """
        Export audit log for compliance purposes.

        Returns:
            Path to exported file
        """
        events = self.get_tenant_events(tenant_id=tenant_id, from_time=from_time, to_time=to_time, limit=100000)

        output_path = output_path or os.path.join(
            self.storage_path, f"export_{tenant_id}_{from_time[:10]}_{to_time[:10]}.json"
        )

        export_data = {
            "export_timestamp": datetime.utcnow().isoformat() + "Z",
            "tenant_id": tenant_id,
            "from_time": from_time,
            "to_time": to_time,
            "total_events": len(events),
            "events": [e.to_dict() for e in events],
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)

        return output_path

    def get_statistics(self, tenant_id: str = None) -> dict[str, Any]:
        """Get audit statistics"""
        events = self._events
        if tenant_id:
            events = [e for e in events if e.tenant_id == tenant_id]

        # Count by event type
        by_type = {}
        for e in events:
            by_type[e.event_type] = by_type.get(e.event_type, 0) + 1

        # Count by entity type
        by_entity = {}
        for e in events:
            by_entity[e.entity_type] = by_entity.get(e.entity_type, 0) + 1

        return {
            "total_events": len(events),
            "by_event_type": by_type,
            "by_entity_type": by_entity,
            "unique_entities": len(set(e.entity_id for e in events)),
            "unique_users": len(set(e.user_id for e in events if e.user_id)),
        }


# Global audit store instance
_audit_store: AuditStore | None = None


def get_audit_store() -> AuditStore:
    """Get the global audit store"""
    global _audit_store
    if _audit_store is None:
        _audit_store = AuditStore()
    return _audit_store


if __name__ == "__main__":
    # Test audit store
    store = AuditStore(storage_path="data/audit_test")

    # Log some events
    event_id = store.log(
        event_type=AuditEventType.DOCUMENT_PROCESSED,
        tenant_id="tenant-001",
        entity_type="document",
        entity_id="DOC-001",
        action="process",
        user_id="user-001",
        description="Processed invoice document",
        after_state={"status": "processed", "doc_type": "vat_invoice"},
        evidence={"ocr_confidence": 0.95},
    )
    print(f"Created event: {event_id}")

    event_id = store.log(
        event_type=AuditEventType.APPROVAL_REQUESTED,
        tenant_id="tenant-001",
        entity_type="document",
        entity_id="DOC-001",
        action="request_approval",
        user_id="system",
        reason="Missing invoice_serial field",
        before_state={"status": "processed"},
        after_state={"status": "pending_approval"},
    )
    print(f"Created event: {event_id}")

    # Get history
    history = store.get_entity_history("document", "DOC-001")
    print(f"\nEntity history ({len(history)} events):")
    for event in history:
        print(f"  - {event.event_type}: {event.description} (v{event.version})")

    # Get statistics
    stats = store.get_statistics()
    print(f"\nStatistics: {stats}")
