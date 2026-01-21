"""
Logging Configuration for ERPX API
==================================
Re-exports from core.logging for backward compatibility.
"""

# Re-export from central logging module
from core.logging import (
    JSONFormatter,
    RequestIdFilter,
    SafeFormatter,
    get_logger,
    get_request_id,
    reset_request_id,
    set_request_id,
    setup_logging,
)

__all__ = [
    "setup_logging",
    "get_logger",
    "get_request_id",
    "set_request_id",
    "reset_request_id",
    "RequestIdFilter",
    "SafeFormatter",
    "JSONFormatter",
]
