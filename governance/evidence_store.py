"""
ERPX AI Accounting - Evidence Store
===================================
Stores evidence for extracted data (R5 - Evidence First).
"""

import hashlib
import json
import os
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class EvidenceType(str, Enum):
    """Types of evidence"""

    OCR_TEXT = "ocr_text"
    OCR_SNIPPET = "ocr_snippet"
    STRUCTURED_FIELD = "structured_field"
    DATABASE_RECORD = "database_record"
    CALCULATION = "calculation"
    INFERENCE = "inference"
    RECONCILIATION_MATCH = "reconciliation_match"


@dataclass
class Evidence:
    """
    Evidence record for extracted data.

    Implements R5 - Evidence First
    """

    # Identifiers
    evidence_id: str
    timestamp: str

    # Link to document/entity
    doc_id: str
    tenant_id: str

    # What field this evidence supports
    field_name: str
    field_value: Any

    # Evidence details
    evidence_type: str
    source: str  # e.g., "ocr", "structured", "db"

    # The actual evidence
    text_snippet: str | None = None  # For OCR evidence
    source_location: str | None = None  # e.g., "line 5", "page 1"
    structured_path: str | None = None  # e.g., "invoice_data.total"
    calculation_formula: str | None = None  # For calculated fields

    # Confidence
    confidence: float = 1.0

    # Hash for integrity
    content_hash: str | None = None

    # Metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Evidence":
        return cls(**data)


class EvidenceStore:
    """
    Stores and retrieves evidence for extracted data.

    Features:
    - Store evidence for any extracted field
    - Link evidence to documents
    - Query evidence by field or document
    - Verify evidence integrity
    """

    def __init__(self, storage_path: str = None):
        self.storage_path = storage_path or os.getenv("EVIDENCE_STORAGE_PATH", "data/evidence")
        self._lock = threading.Lock()
        self._evidence: dict[str, Evidence] = {}  # evidence_id -> Evidence
        self._doc_index: dict[str, list[str]] = {}  # doc_id -> [evidence_ids]
        self._field_index: dict[str, list[str]] = {}  # field_name -> [evidence_ids]

        # Ensure storage directory exists
        os.makedirs(self.storage_path, exist_ok=True)

    def store(
        self,
        doc_id: str,
        tenant_id: str,
        field_name: str,
        field_value: Any,
        evidence_type: EvidenceType,
        source: str,
        text_snippet: str = None,
        source_location: str = None,
        structured_path: str = None,
        calculation_formula: str = None,
        confidence: float = 1.0,
        metadata: dict = None,
    ) -> str:
        """
        Store evidence for an extracted field.

        Returns:
            Evidence ID
        """
        evidence_id = str(uuid.uuid4())

        # Calculate content hash for integrity
        content = f"{field_name}:{field_value}:{text_snippet or ''}"
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        evidence = Evidence(
            evidence_id=evidence_id,
            timestamp=datetime.utcnow().isoformat() + "Z",
            doc_id=doc_id,
            tenant_id=tenant_id,
            field_name=field_name,
            field_value=field_value,
            evidence_type=evidence_type.value if isinstance(evidence_type, EvidenceType) else evidence_type,
            source=source,
            text_snippet=text_snippet,
            source_location=source_location,
            structured_path=structured_path,
            calculation_formula=calculation_formula,
            confidence=confidence,
            content_hash=content_hash,
            metadata=metadata or {},
        )

        with self._lock:
            self._evidence[evidence_id] = evidence

            # Update indexes
            if doc_id not in self._doc_index:
                self._doc_index[doc_id] = []
            self._doc_index[doc_id].append(evidence_id)

            if field_name not in self._field_index:
                self._field_index[field_name] = []
            self._field_index[field_name].append(evidence_id)

        # Persist
        self._persist_evidence(evidence)

        return evidence_id

    def _persist_evidence(self, evidence: Evidence):
        """Persist evidence to file"""
        filename = os.path.join(self.storage_path, f"{evidence.tenant_id}_{evidence.doc_id}.json")

        # Load existing evidence for this doc
        existing = []
        if os.path.exists(filename):
            with open(filename, encoding="utf-8") as f:
                existing = json.load(f)

        # Append new evidence
        existing.append(evidence.to_dict())

        # Save
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)

    def get(self, evidence_id: str) -> Evidence | None:
        """Get evidence by ID"""
        return self._evidence.get(evidence_id)

    def get_for_document(self, doc_id: str) -> list[Evidence]:
        """Get all evidence for a document"""
        evidence_ids = self._doc_index.get(doc_id, [])
        return [self._evidence[eid] for eid in evidence_ids if eid in self._evidence]

    def get_for_field(self, doc_id: str, field_name: str) -> list[Evidence]:
        """Get evidence for a specific field in a document"""
        doc_evidence = self.get_for_document(doc_id)
        return [e for e in doc_evidence if e.field_name == field_name]

    def verify_integrity(self, evidence_id: str) -> bool:
        """Verify evidence has not been tampered with"""
        evidence = self.get(evidence_id)
        if not evidence:
            return False

        # Recalculate hash
        content = f"{evidence.field_name}:{evidence.field_value}:{evidence.text_snippet or ''}"
        calculated_hash = hashlib.sha256(content.encode()).hexdigest()

        return calculated_hash == evidence.content_hash

    def get_evidence_summary(self, doc_id: str) -> dict[str, Any]:
        """Get a summary of evidence for a document"""
        evidence_list = self.get_for_document(doc_id)

        # Group by field
        by_field = {}
        for e in evidence_list:
            if e.field_name not in by_field:
                by_field[e.field_name] = []
            by_field[e.field_name].append(
                {
                    "value": e.field_value,
                    "source": e.source,
                    "confidence": e.confidence,
                    "snippet": e.text_snippet[:100] if e.text_snippet else None,
                }
            )

        return {
            "doc_id": doc_id,
            "total_evidence": len(evidence_list),
            "fields_with_evidence": len(by_field),
            "by_field": by_field,
        }

    def export_for_audit(self, doc_id: str) -> dict[str, Any]:
        """Export evidence for audit purposes"""
        evidence_list = self.get_for_document(doc_id)

        return {
            "doc_id": doc_id,
            "export_timestamp": datetime.utcnow().isoformat() + "Z",
            "total_evidence": len(evidence_list),
            "evidence": [e.to_dict() for e in evidence_list],
        }

    def store_from_output(self, doc_id: str, tenant_id: str, output: dict[str, Any]) -> list[str]:
        """
        Store evidence from processing output.

        Extracts evidence from the 'evidence' section of output.

        Returns:
            List of created evidence IDs
        """
        evidence_ids = []

        # Get evidence from output
        evidence_data = output.get("evidence", {})

        # Store text snippets
        for snippet in evidence_data.get("key_text_snippets", []):
            eid = self.store(
                doc_id=doc_id,
                tenant_id=tenant_id,
                field_name="_text_evidence",
                field_value=snippet,
                evidence_type=EvidenceType.OCR_SNIPPET,
                source="ocr",
                text_snippet=snippet,
            )
            evidence_ids.append(eid)

        # Store number evidence
        for num_evidence in evidence_data.get("numbers_found", []):
            eid = self.store(
                doc_id=doc_id,
                tenant_id=tenant_id,
                field_name=num_evidence.get("label", "unknown"),
                field_value=num_evidence.get("value"),
                evidence_type=EvidenceType.OCR_TEXT
                if num_evidence.get("source") == "ocr"
                else EvidenceType.STRUCTURED_FIELD,
                source=num_evidence.get("source", "unknown"),
            )
            evidence_ids.append(eid)

        return evidence_ids


# Global evidence store instance
_evidence_store: EvidenceStore | None = None


def get_evidence_store() -> EvidenceStore:
    """Get the global evidence store"""
    global _evidence_store
    if _evidence_store is None:
        _evidence_store = EvidenceStore()
    return _evidence_store


if __name__ == "__main__":
    # Test evidence store
    store = EvidenceStore(storage_path="data/evidence_test")

    # Store evidence
    eid1 = store.store(
        doc_id="DOC-001",
        tenant_id="tenant-001",
        field_name="grand_total",
        field_value=1100000,
        evidence_type=EvidenceType.OCR_SNIPPET,
        source="ocr",
        text_snippet="TOTAL: 1,100,000 VND",
        source_location="line 15",
        confidence=0.95,
    )
    print(f"Created evidence: {eid1}")

    eid2 = store.store(
        doc_id="DOC-001",
        tenant_id="tenant-001",
        field_name="vat_amount",
        field_value=100000,
        evidence_type=EvidenceType.CALCULATION,
        source="calculated",
        calculation_formula="subtotal * vat_rate / 100 = 1000000 * 10 / 100",
        confidence=1.0,
    )
    print(f"Created evidence: {eid2}")

    # Get evidence
    doc_evidence = store.get_for_document("DOC-001")
    print(f"\nDocument evidence ({len(doc_evidence)} items):")
    for e in doc_evidence:
        print(f"  - {e.field_name}: {e.field_value} (source: {e.source})")

    # Verify integrity
    is_valid = store.verify_integrity(eid1)
    print(f"\nEvidence integrity: {is_valid}")

    # Get summary
    summary = store.get_evidence_summary("DOC-001")
    print(f"\nEvidence summary: {summary}")
