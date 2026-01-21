"""
ERPX AI Accounting - Custom Exceptions (Deprecated)
====================================================
This module is DEPRECATED. Import from core.errors instead.
Kept for backward compatibility.
"""

# Re-export everything from core.errors for backward compatibility
from core.errors import (
    ApprovalRequired,
    AuthError,
    ConfigError,
    DatabaseError,
    ERPXBaseException,
    ERPXError,
    ExternalServiceError,
    ExtractionError,
    GuardrailsViolation,
    HallucinationDetected,
    LLMError,
    LLMTimeoutError,
    QuotaExceeded,
    ReconciliationError,
    StorageError,
    TemporalError,
    TenantNotFound,
    ValidationError,
    WorkflowError,
)

__all__ = [
    "ERPXError",
    "ERPXBaseException",
    "ConfigError",
    "ValidationError",
    "ExtractionError",
    "ExternalServiceError",
    "DatabaseError",
    "StorageError",
    "LLMError",
    "LLMTimeoutError",
    "WorkflowError",
    "TemporalError",
    "ReconciliationError",
    "GuardrailsViolation",
    "HallucinationDetected",
    "ApprovalRequired",
    "AuthError",
    "TenantNotFound",
    "QuotaExceeded",
]
