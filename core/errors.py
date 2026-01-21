"""
ERPX AI Accounting - Error Taxonomy
===================================
Centralized error definitions for consistent error handling.
Does NOT change HTTP response schema - only provides taxonomy.
"""

from typing import Any, Dict, Optional


class ERPXError(Exception):
    """
    Base exception for all ERPX errors.

    Attributes:
        message: Human-readable error message
        code: Machine-readable error code
        details: Additional error details (dict)
    """

    def __init__(
        self,
        message: str,
        code: str = "ERPX_ERROR",
        details: Optional[Dict[str, Any]] = None,
    ):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for API responses."""
        return {
            "error": self.code,
            "message": self.message,
            "details": self.details,
        }


# =============================================================================
# Configuration Errors
# =============================================================================


class ConfigError(ERPXError):
    """Configuration error - missing or invalid config."""

    def __init__(self, message: str, key: str = None, details: Dict = None):
        super().__init__(message, "CONFIG_ERROR", details)
        self.key = key


# =============================================================================
# Validation Errors
# =============================================================================


class ValidationError(ERPXError):
    """Input validation failed."""

    def __init__(self, message: str, field: str = None, details: Dict = None):
        super().__init__(message, "VALIDATION_ERROR", details)
        self.field = field


class ExtractionError(ERPXError):
    """Field extraction failed."""

    def __init__(self, message: str, field: str = None, details: Dict = None):
        super().__init__(message, "EXTRACTION_ERROR", details)
        self.field = field


# =============================================================================
# External Service Errors
# =============================================================================


class ExternalServiceError(ERPXError):
    """External service call failed."""

    def __init__(
        self,
        message: str,
        service: str = None,
        details: Dict = None,
    ):
        super().__init__(message, "EXTERNAL_SERVICE_ERROR", details)
        self.service = service


class DatabaseError(ERPXError):
    """Database operation failed."""

    def __init__(self, message: str, operation: str = None, details: Dict = None):
        super().__init__(message, "DATABASE_ERROR", details)
        self.operation = operation


class StorageError(ERPXError):
    """Storage operation failed (MinIO/S3)."""

    def __init__(self, message: str, operation: str = None, details: Dict = None):
        super().__init__(message, "STORAGE_ERROR", details)
        self.operation = operation


class LLMError(ERPXError):
    """LLM service error."""

    def __init__(self, message: str, provider: str = None, details: Dict = None):
        super().__init__(message, "LLM_ERROR", details)
        self.provider = provider


class LLMTimeoutError(LLMError):
    """LLM request timed out."""

    def __init__(self, message: str, timeout_ms: int = None, details: Dict = None):
        super().__init__(message, "LLM_TIMEOUT", details)
        self.timeout_ms = timeout_ms


# =============================================================================
# Workflow Errors
# =============================================================================


class WorkflowError(ERPXError):
    """Workflow state machine error."""

    def __init__(self, message: str, state: str = None, details: Dict = None):
        super().__init__(message, "WORKFLOW_ERROR", details)
        self.state = state


class TemporalError(WorkflowError):
    """Temporal workflow error."""

    def __init__(self, message: str, workflow_id: str = None, details: Dict = None):
        super().__init__(message, "TEMPORAL_ERROR", details)
        self.workflow_id = workflow_id


# =============================================================================
# Business Logic Errors
# =============================================================================


class ReconciliationError(ERPXError):
    """Bank reconciliation failed."""

    def __init__(self, message: str, details: Dict = None):
        super().__init__(message, "RECONCILIATION_ERROR", details)


class GuardrailsViolation(ERPXError):
    """Guardrails policy violation."""

    def __init__(self, message: str, rule: str = None, details: Dict = None):
        super().__init__(message, "GUARDRAILS_VIOLATION", details)
        self.rule = rule


class HallucinationDetected(GuardrailsViolation):
    """R2 - Hallucination detected."""

    def __init__(self, message: str, field: str = None, details: Dict = None):
        super().__init__(message, "R2_NO_HALLUCINATION", details)
        self.field = field


class ApprovalRequired(ERPXError):
    """R6 - Human approval required."""

    def __init__(self, message: str, reason: str = None, details: Dict = None):
        super().__init__(message, "APPROVAL_REQUIRED", details)
        self.reason = reason


# =============================================================================
# Auth/Tenant Errors
# =============================================================================


class AuthError(ERPXError):
    """Authentication error."""

    def __init__(self, message: str, details: Dict = None):
        super().__init__(message, "AUTH_ERROR", details)


class TenantNotFound(ERPXError):
    """Tenant not found."""

    def __init__(self, tenant_id: str):
        super().__init__(f"Tenant not found: {tenant_id}", "TENANT_NOT_FOUND")
        self.tenant_id = tenant_id


class QuotaExceeded(ERPXError):
    """API quota exceeded."""

    def __init__(self, tenant_id: str, limit: int, current: int):
        super().__init__(
            f"Quota exceeded for tenant {tenant_id}: {current}/{limit}",
            "QUOTA_EXCEEDED",
        )
        self.tenant_id = tenant_id
        self.limit = limit
        self.current = current


# =============================================================================
# Backward Compatibility Aliases
# =============================================================================

# Alias for existing code that uses ERPXBaseException
ERPXBaseException = ERPXError


__all__ = [
    # Base
    "ERPXError",
    "ERPXBaseException",  # alias
    # Config
    "ConfigError",
    # Validation
    "ValidationError",
    "ExtractionError",
    # External Services
    "ExternalServiceError",
    "DatabaseError",
    "StorageError",
    "LLMError",
    "LLMTimeoutError",
    # Workflow
    "WorkflowError",
    "TemporalError",
    # Business Logic
    "ReconciliationError",
    "GuardrailsViolation",
    "HallucinationDetected",
    "ApprovalRequired",
    # Auth/Tenant
    "AuthError",
    "TenantNotFound",
    "QuotaExceeded",
]


if __name__ == "__main__":
    # Test
    print("Testing ERPX Errors...")

    try:
        raise ValidationError("Invalid amount", field="amount")
    except ERPXError as e:
        print(f"✓ Caught: {e.code} - {e.message}")
        print(f"  Dict: {e.to_dict()}")

    try:
        raise WorkflowError("Invalid state transition", state="pending")
    except ERPXError as e:
        print(f"✓ Caught: {e.code} - {e.message}")

    print("\n✓ Error taxonomy test complete")
