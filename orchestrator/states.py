"""
ERPX AI Accounting - Workflow State Definitions
===============================================
Defines the state machine states and transitions for the accounting workflow.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class WorkflowStep(str, Enum):
    """Workflow steps (LangGraph nodes)"""

    INGEST = "A_INGEST"
    CLASSIFY = "B_CLASSIFY"
    EXTRACT = "C_EXTRACT"
    VALIDATE = "D_VALIDATE"
    RECONCILE = "E_RECONCILE"
    DECISION = "F_DECISION"
    COMPLETE = "COMPLETE"
    ERROR = "ERROR"


class ValidationStatus(str, Enum):
    """Validation result status"""

    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


@dataclass
class WorkflowState:
    """
    State object passed between workflow nodes.
    Contains all accumulated data from processing steps.
    """

    # Identifiers
    doc_id: str = ""
    tenant_id: str | None = None
    request_id: str | None = None

    # Current state
    current_step: WorkflowStep = WorkflowStep.INGEST
    step_history: list[str] = field(default_factory=list)
    started_at: str | None = None
    completed_at: str | None = None

    # Input data
    raw_input: str | None = None  # OCR text or raw content
    structured_input: dict[str, Any] | None = None  # Pre-extracted fields
    file_metadata: dict[str, Any] | None = None
    bank_transactions: list[dict[str, Any]] | None = None

    # Processing mode
    mode: str = "STRICT"  # STRICT or RELAXED

    # Step A: Ingest results
    normalized_text: str | None = None
    text_blocks: list[str] | None = None

    # Step B: Classification results
    doc_type: str | None = None
    doc_type_confidence: float = 0.0
    classification_evidence: list[str] | None = None

    # Step C: Extraction results
    extracted_fields: dict[str, Any] = field(default_factory=dict)
    extraction_evidence: dict[str, Any] = field(default_factory=dict)

    # Step D: Validation results
    validation_status: ValidationStatus = ValidationStatus.PASS
    validation_errors: list[str] = field(default_factory=list)
    validation_warnings: list[str] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)

    # Step E: Reconciliation results
    reconciliation_matches: list[dict[str, Any]] = field(default_factory=list)
    unmatched_invoices: list[str] = field(default_factory=list)
    unmatched_bank_txns: list[str] = field(default_factory=list)

    # Step F: Final decision
    needs_human_review: bool = False
    review_reasons: list[str] = field(default_factory=list)
    approval_threshold_exceeded: bool = False

    # Output
    final_payload: dict[str, Any] | None = None
    evidence_log: list[dict[str, Any]] = field(default_factory=list)

    # Error handling
    error_message: str | None = None
    error_step: str | None = None

    def record_step(self, step: WorkflowStep, metadata: dict[str, Any] = None):
        """Record a step execution in history"""
        entry = {"step": step.value, "timestamp": datetime.utcnow().isoformat(), "metadata": metadata or {}}
        self.step_history.append(entry)
        self.current_step = step

    def add_evidence(self, field: str, value: Any, source: str, snippet: str = None):
        """Add evidence for a field extraction"""
        self.evidence_log.append(
            {
                "field": field,
                "value": value,
                "source": source,
                "snippet": snippet,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

    def add_warning(self, message: str):
        """Add a validation warning"""
        if message not in self.validation_warnings:
            self.validation_warnings.append(message)

    def add_error(self, message: str):
        """Add a validation error"""
        if message not in self.validation_errors:
            self.validation_errors.append(message)

    def mark_for_review(self, reason: str):
        """Mark document for human review"""
        self.needs_human_review = True
        if reason not in self.review_reasons:
            self.review_reasons.append(reason)

    def to_dict(self) -> dict[str, Any]:
        """Convert state to dictionary"""
        return {
            "doc_id": self.doc_id,
            "tenant_id": self.tenant_id,
            "current_step": self.current_step.value
            if isinstance(self.current_step, WorkflowStep)
            else self.current_step,
            "mode": self.mode,
            "doc_type": self.doc_type,
            "doc_type_confidence": self.doc_type_confidence,
            "extracted_fields": self.extracted_fields,
            "validation_status": self.validation_status.value
            if isinstance(self.validation_status, ValidationStatus)
            else self.validation_status,
            "validation_errors": self.validation_errors,
            "validation_warnings": self.validation_warnings,
            "missing_fields": self.missing_fields,
            "needs_human_review": self.needs_human_review,
            "review_reasons": self.review_reasons,
            "reconciliation_matches": self.reconciliation_matches,
            "step_history": self.step_history,
            "error_message": self.error_message,
        }


@dataclass
class StateTransition:
    """Represents a transition between workflow states"""

    from_step: WorkflowStep
    to_step: WorkflowStep
    condition: str | None = None

    def __str__(self):
        if self.condition:
            return f"{self.from_step.value} --[{self.condition}]--> {self.to_step.value}"
        return f"{self.from_step.value} --> {self.to_step.value}"


# Define the workflow graph transitions
WORKFLOW_TRANSITIONS = [
    # Happy path
    StateTransition(WorkflowStep.INGEST, WorkflowStep.CLASSIFY),
    StateTransition(WorkflowStep.CLASSIFY, WorkflowStep.EXTRACT),
    StateTransition(WorkflowStep.EXTRACT, WorkflowStep.VALIDATE),
    StateTransition(WorkflowStep.VALIDATE, WorkflowStep.RECONCILE, "has_bank_txns"),
    StateTransition(WorkflowStep.VALIDATE, WorkflowStep.DECISION, "no_bank_txns"),
    StateTransition(WorkflowStep.RECONCILE, WorkflowStep.DECISION),
    StateTransition(WorkflowStep.DECISION, WorkflowStep.COMPLETE),
    # Error paths
    StateTransition(WorkflowStep.INGEST, WorkflowStep.ERROR, "ingest_failed"),
    StateTransition(WorkflowStep.CLASSIFY, WorkflowStep.ERROR, "classify_failed"),
    StateTransition(WorkflowStep.EXTRACT, WorkflowStep.ERROR, "extract_failed"),
    StateTransition(WorkflowStep.VALIDATE, WorkflowStep.ERROR, "validation_critical"),
]
