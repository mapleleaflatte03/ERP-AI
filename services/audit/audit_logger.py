"""
Audit Logger Service for ERPX E2E
Records all state transitions with who/what/when/why
"""

import json
import logging
import sys
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

sys.path.insert(0, "/root/erp-ai")

from domain.enums import AuditAction
from domain.models import AuditEvent

logger = logging.getLogger("AuditLogger")


class AuditLogger:
    """
    Audit & Evidence Store implementation
    Records all state transitions for compliance and traceability
    """

    def __init__(self, db: Session):
        self.db = db

    def log(
        self,
        action: AuditAction,
        entity_type: str,
        entity_id: str,
        *,
        actor: str = "system",
        tenant_id: str | None = None,
        old_state: dict[str, Any] | None = None,
        new_state: dict[str, Any] | None = None,
        details: dict[str, Any] | None = None,
        evidence: dict[str, Any] | None = None,
        model_version: str | None = None,
        prompt_version: str | None = None,
        trace_id: str | None = None,
        request_id: str | None = None,
        invoice_id: uuid.UUID | None = None,
        error_message: str | None = None,
        error_traceback: str | None = None,
    ) -> AuditEvent:
        """
        Log an audit event

        Args:
            action: The action being performed
            entity_type: Type of entity (Invoice, Proposal, LedgerEntry)
            entity_id: ID of the entity
            actor: Who performed the action (user_id or "system")
            tenant_id: Tenant identifier
            old_state: Previous state (for state changes)
            new_state: New state (for state changes)
            details: Additional context
            evidence: Model outputs, confidence scores, sources
            model_version: LLM/ML model version
            prompt_version: Prompt template version
            trace_id: E2E trace ID
            request_id: Request ID
            invoice_id: Related invoice ID
            error_message: Error message if action is ERROR
            error_traceback: Error traceback if action is ERROR

        Returns:
            Created AuditEvent
        """
        audit_event = AuditEvent(
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id),
            actor=actor,
            tenant_id=tenant_id,
            old_state=old_state,
            new_state=new_state,
            details=details,
            evidence=evidence,
            model_version=model_version,
            prompt_version=prompt_version,
            trace_id=trace_id,
            request_id=request_id,
            invoice_id=invoice_id,
            error_message=error_message,
            error_traceback=error_traceback,
        )

        self.db.add(audit_event)
        self.db.commit()
        self.db.refresh(audit_event)

        # Also log to structured logger for observability
        log_data = {
            "audit_id": str(audit_event.id),
            "action": action.value,
            "entity_type": entity_type,
            "entity_id": str(entity_id),
            "actor": actor,
            "tenant_id": tenant_id,
            "trace_id": trace_id,
            "request_id": request_id,
            "timestamp": datetime.utcnow().isoformat(),
        }

        if error_message:
            log_data["error"] = error_message
            logger.error(f"AUDIT: {json.dumps(log_data)}")
        else:
            logger.info(f"AUDIT: {json.dumps(log_data)}")

        return audit_event

    def log_status_change(
        self,
        entity_type: str,
        entity_id: str,
        old_status: str,
        new_status: str,
        *,
        actor: str = "system",
        tenant_id: str | None = None,
        trace_id: str | None = None,
        request_id: str | None = None,
        invoice_id: uuid.UUID | None = None,
        details: dict[str, Any] | None = None,
    ) -> AuditEvent:
        """Log a status change event"""
        return self.log(
            action=AuditAction.STATUS_CHANGE,
            entity_type=entity_type,
            entity_id=entity_id,
            actor=actor,
            tenant_id=tenant_id,
            old_state={"status": old_status},
            new_state={"status": new_status},
            details=details,
            trace_id=trace_id,
            request_id=request_id,
            invoice_id=invoice_id,
        )

    def log_error(
        self,
        entity_type: str,
        entity_id: str,
        error_message: str,
        error_traceback: str | None = None,
        *,
        actor: str = "system",
        tenant_id: str | None = None,
        trace_id: str | None = None,
        request_id: str | None = None,
        invoice_id: uuid.UUID | None = None,
        details: dict[str, Any] | None = None,
    ) -> AuditEvent:
        """Log an error event"""
        return self.log(
            action=AuditAction.ERROR,
            entity_type=entity_type,
            entity_id=entity_id,
            actor=actor,
            tenant_id=tenant_id,
            error_message=error_message,
            error_traceback=error_traceback,
            details=details,
            trace_id=trace_id,
            request_id=request_id,
            invoice_id=invoice_id,
        )

    def get_audit_trail(
        self,
        entity_type: str,
        entity_id: str,
        limit: int = 100,
    ) -> list:
        """Get audit trail for an entity"""
        return (
            self.db.query(AuditEvent)
            .filter(AuditEvent.entity_type == entity_type)
            .filter(AuditEvent.entity_id == str(entity_id))
            .order_by(AuditEvent.created_at.desc())
            .limit(limit)
            .all()
        )

    def get_invoice_audit_trail(
        self,
        invoice_id: uuid.UUID,
        limit: int = 100,
    ) -> list:
        """Get full audit trail for an invoice (including related entities)"""
        return (
            self.db.query(AuditEvent)
            .filter(AuditEvent.invoice_id == invoice_id)
            .order_by(AuditEvent.created_at.asc())
            .limit(limit)
            .all()
        )
