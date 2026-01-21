"""
ERPX AI Accounting - Centralized Logging
========================================
Safe logging setup with request_id injection.
Prevents "--- Logging error ---" crashes.
"""

import logging
import sys
from contextvars import ContextVar
from typing import Optional

from core.config import get_settings

# Context variable for request_id (thread-safe)
_request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

# Type alias for token
from contextvars import Token

RequestIdToken = Token[str]


def set_request_id(request_id: str) -> RequestIdToken:
    """
    Set request_id for current context.

    Returns:
        Token that can be used to reset to previous value.
    """
    return _request_id_var.set(request_id or "-")


def reset_request_id(token: RequestIdToken) -> None:
    """
    Reset request_id to previous value using token.

    This properly restores the context for async safety.
    """
    _request_id_var.reset(token)


def get_request_id() -> str:
    """Get request_id from current context, default '-'."""
    return _request_id_var.get()


class RequestIdFilter(logging.Filter):
    """
    Logging filter that injects request_id into every log record.
    Falls back to "-" if no request context is available.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        # Always inject request_id, never crash
        if not hasattr(record, "request_id") or record.request_id is None:
            record.request_id = get_request_id()
        return True


class SafeFormatter(logging.Formatter):
    """
    Formatter that safely handles missing fields.
    Prevents KeyError crashes when fields are missing.
    """

    def format(self, record: logging.LogRecord) -> str:
        # Ensure request_id exists - prevent KeyError
        if not hasattr(record, "request_id") or record.request_id is None:
            record.request_id = "-"
        return super().format(record)


class JSONFormatter(logging.Formatter):
    """
    JSON log formatter for structured logging.
    Only used when JSON_LOGS=true.
    """

    def format(self, record: logging.LogRecord) -> str:
        import json
        from datetime import datetime

        # Ensure request_id exists
        request_id = getattr(record, "request_id", "-") or "-"

        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id,
        }

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Add extra fields if present
        for key in ("tenant_id", "doc_id", "user_id", "job_id"):
            if hasattr(record, key):
                log_entry[key] = getattr(record, key)

        return json.dumps(log_entry, ensure_ascii=False)


# Track if logging has been setup
_logging_initialized = False


def setup_logging(
    level: Optional[str] = None,
    json_format: Optional[bool] = None,
) -> logging.Logger:
    """
    Setup logging with request_id support.

    Safe to call multiple times - only initializes once.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR). Default from config.
        json_format: Use JSON format. Default from config.

    Returns:
        The root ERPX logger.
    """
    global _logging_initialized

    if _logging_initialized:
        return logging.getLogger("erpx")

    # Get settings
    settings = get_settings()

    # Determine log level
    if level is None:
        level = settings.LOG_LEVEL
    # Handle both int (logging.INFO) and str ("INFO")
    if isinstance(level, int):
        log_level = level
    else:
        log_level = getattr(logging, str(level).upper(), logging.INFO)

    # Determine format
    if json_format is None:
        json_format = settings.JSON_LOGS

    # Create formatter
    if json_format:
        formatter = JSONFormatter()
    else:
        formatter = SafeFormatter(
            fmt="%(asctime)s - %(name)s - %(levelname)s - [%(request_id)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    # Create filter
    request_id_filter = RequestIdFilter()

    # Configure root handler
    root_handler = logging.StreamHandler(sys.stdout)
    root_handler.setFormatter(formatter)
    root_handler.addFilter(request_id_filter)
    root_handler.setLevel(log_level)

    # Configure ERPX logger
    erpx_logger = logging.getLogger("erpx")
    erpx_logger.setLevel(log_level)
    erpx_logger.handlers = []  # Clear existing handlers
    erpx_logger.addHandler(root_handler)
    erpx_logger.propagate = False

    # Configure uvicorn access logger (for API)
    uvicorn_access = logging.getLogger("uvicorn.access")
    uvicorn_access.handlers = []
    uvicorn_access.addHandler(root_handler)
    uvicorn_access.propagate = False

    # Suppress noisy loggers
    for noisy in ("urllib3", "httpx", "httpcore", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _logging_initialized = True
    return erpx_logger


def get_logger(name: str = "erpx") -> logging.Logger:
    """
    Get a logger with the given name.

    Automatically prefixes with 'erpx.' if not already prefixed.
    Safe to call before setup_logging() - will work with default config.

    Args:
        name: Logger name. Will be prefixed with 'erpx.' if needed.

    Returns:
        Logger instance.
    """
    # Ensure logging is initialized
    if not _logging_initialized:
        setup_logging()

    # Auto-prefix if not already
    if not name.startswith("erpx"):
        name = f"erpx.{name}"

    return logging.getLogger(name)


# Convenience: export RequestIdFilter and SafeFormatter for backward compatibility
__all__ = [
    "setup_logging",
    "get_logger",
    "get_request_id",
    "set_request_id",
    "RequestIdFilter",
    "SafeFormatter",
    "JSONFormatter",
]


if __name__ == "__main__":
    # Test
    setup_logging(level="DEBUG")
    log = get_logger("test")

    log.info("Test message without request_id")

    set_request_id("req-12345")
    log.info("Test message with request_id")

    log.warning("Warning message")
    log.error("Error message")

    print("\n✓ Logging test complete")
