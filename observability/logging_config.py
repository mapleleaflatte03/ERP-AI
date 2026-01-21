"""
ERPX AI Accounting - Logging Configuration
==========================================
Structured logging for audit and debugging.
"""

import json
import logging
import os
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler


class StructuredFormatter(logging.Formatter):
    """
    JSON structured log formatter for easy parsing.
    """

    def __init__(self, service_name: str = "erpx-accounting"):
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": self.service_name,
        }

        # Add extra fields
        if hasattr(record, "tenant_id"):
            log_entry["tenant_id"] = record.tenant_id
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        if hasattr(record, "doc_id"):
            log_entry["doc_id"] = record.doc_id
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id

        # Add exception info
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Add any extra attributes
        if hasattr(record, "extra_data"):
            log_entry["data"] = record.extra_data

        return json.dumps(log_entry, ensure_ascii=False)


class HumanReadableFormatter(logging.Formatter):
    """
    Human-readable log formatter for development.
    """

    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def __init__(self, use_colors: bool = True):
        super().__init__()
        self.use_colors = use_colors

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        level = record.levelname

        if self.use_colors and level in self.COLORS:
            level = f"{self.COLORS[level]}{level}{self.RESET}"

        message = record.getMessage()

        # Add context
        context_parts = []
        if hasattr(record, "tenant_id"):
            context_parts.append(f"tenant={record.tenant_id}")
        if hasattr(record, "request_id"):
            context_parts.append(f"req={record.request_id[:8]}")
        if hasattr(record, "doc_id"):
            context_parts.append(f"doc={record.doc_id}")

        context = f" [{' '.join(context_parts)}]" if context_parts else ""

        return f"{timestamp} | {level:8s} | {record.name}{context} | {message}"


class ContextLogger(logging.LoggerAdapter):
    """
    Logger adapter that adds context (tenant, request, etc.)
    """

    def process(self, msg, kwargs):
        extra = kwargs.get("extra", {})
        extra.update(self.extra)
        kwargs["extra"] = extra
        return msg, kwargs


def setup_logging(
    service_name: str = "erpx-accounting", log_level: str = None, log_file: str = None, json_format: bool = None
) -> logging.Logger:
    """
    Setup logging configuration.

    Args:
        service_name: Service name for logs
        log_level: Log level (DEBUG, INFO, WARNING, ERROR)
        log_file: Optional log file path
        json_format: Use JSON format (default: auto based on env)

    Returns:
        Root logger
    """
    # Get config from env
    log_level = log_level or os.getenv("LOG_LEVEL", "INFO")
    log_file = log_file or os.getenv("LOG_FILE")

    if json_format is None:
        # Use JSON in production, human-readable in dev
        json_format = os.getenv("LOG_FORMAT", "json").lower() == "json"

    # Create root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))

    # Remove existing handlers
    root_logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper()))

    if json_format:
        console_handler.setFormatter(StructuredFormatter(service_name))
    else:
        console_handler.setFormatter(HumanReadableFormatter())

    root_logger.addHandler(console_handler)

    # File handler (if configured)
    if log_file:
        os.makedirs(os.path.dirname(log_file) or ".", exist_ok=True)

        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=50 * 1024 * 1024,  # 50MB
            backupCount=5,
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(StructuredFormatter(service_name))
        root_logger.addHandler(file_handler)

    # Suppress noisy loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    return root_logger


def get_logger(name: str, tenant_id: str = None, request_id: str = None, doc_id: str = None) -> logging.Logger:
    """
    Get a logger with optional context.

    Args:
        name: Logger name
        tenant_id: Optional tenant ID for context
        request_id: Optional request ID for tracing
        doc_id: Optional document ID

    Returns:
        Logger instance (with context adapter if context provided)
    """
    logger = logging.getLogger(name)

    if any([tenant_id, request_id, doc_id]):
        extra = {}
        if tenant_id:
            extra["tenant_id"] = tenant_id
        if request_id:
            extra["request_id"] = request_id
        if doc_id:
            extra["doc_id"] = doc_id

        return ContextLogger(logger, extra)

    return logger


# Audit-specific logging
class AuditLogger:
    """
    Specialized logger for audit events.
    Ensures audit logs are always written, even if main logging fails.
    """

    def __init__(self, audit_file: str = None):
        # Default to runtime/logs/audit.log
        from core.paths import get_log_file

        default_audit = str(get_log_file("audit.log"))
        self.audit_file = audit_file or os.getenv("AUDIT_LOG_FILE", default_audit)
        self._setup_audit_logger()

    def _setup_audit_logger(self):
        self.logger = logging.getLogger("erpx.audit")
        self.logger.setLevel(logging.INFO)

        # Don't propagate to root logger
        self.logger.propagate = False

        # Create audit file handler
        os.makedirs(os.path.dirname(self.audit_file) or ".", exist_ok=True)

        handler = TimedRotatingFileHandler(
            self.audit_file,
            when="midnight",
            interval=1,
            backupCount=90,  # Keep 90 days
        )
        handler.setFormatter(StructuredFormatter("erpx-audit"))
        self.logger.addHandler(handler)

    def log(
        self,
        action: str,
        entity_type: str,
        entity_id: str,
        tenant_id: str = None,
        user_id: str = None,
        before_state: dict = None,
        after_state: dict = None,
        evidence: dict = None,
        metadata: dict = None,
    ):
        """Log an audit event"""
        extra = {
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "before_state": before_state,
            "after_state": after_state,
            "evidence": evidence,
            "metadata": metadata,
        }

        # Use LogRecord with extra data
        record = logging.LogRecord(
            name="erpx.audit",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg=f"{action} {entity_type} {entity_id}",
            args=(),
            exc_info=None,
        )
        record.extra_data = extra

        self.logger.handle(record)


# Global audit logger instance
_audit_logger: AuditLogger | None = None


def get_audit_logger() -> AuditLogger:
    """Get the global audit logger"""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger


if __name__ == "__main__":
    # Test logging
    setup_logging(log_level="DEBUG", json_format=False)

    logger = get_logger("erpx.test", tenant_id="tenant-001", request_id="req-12345678")

    logger.debug("Debug message")
    logger.info("Info message")
    logger.warning("Warning message")
    logger.error("Error message")

    # Test audit logging
    audit = get_audit_logger()
    audit.log(
        action="create",
        entity_type="transaction",
        entity_id="TXN-001",
        tenant_id="tenant-001",
        user_id="user-001",
        after_state={"status": "created"},
    )

    print("\n--- Audit log written to runtime/logs/audit.log ---")
