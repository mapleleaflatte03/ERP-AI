"""
ERPX AI Accounting - Central Configuration
==========================================
Load environment variables with safe defaults.
Does NOT crash if env vars are missing - uses defaults matching current behavior.
"""

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Optional

# Import paths helper from PR-4
from core.paths import get_artifacts_dir, get_logs_dir, get_project_root, get_reports_dir


def _get_bool(key: str, default: bool = False) -> bool:
    """Safely parse boolean from environment."""
    val = os.environ.get(key, str(default)).lower()
    return val in ("true", "1", "yes", "on")


def _get_int(key: str, default: int) -> int:
    """Safely parse int from environment."""
    try:
        return int(os.environ.get(key, str(default)))
    except (ValueError, TypeError):
        return default


def _get_float(key: str, default: float) -> float:
    """Safely parse float from environment."""
    try:
        return float(os.environ.get(key, str(default)))
    except (ValueError, TypeError):
        return default


@dataclass
class Settings:
    """
    Central configuration for ERPX AI Accounting.

    All values have safe defaults matching current behavior.
    Does NOT crash if env vars are missing.
    """

    # ==========================================================================
    # Environment
    # ==========================================================================
    ENV: str = field(default_factory=lambda: os.getenv("ENV", "production"))
    DEBUG: bool = field(default_factory=lambda: _get_bool("DEBUG", False))

    # ==========================================================================
    # Logging
    # ==========================================================================
    LOG_LEVEL: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    JSON_LOGS: bool = field(default_factory=lambda: _get_bool("JSON_LOGS", False))

    # Runtime directories (PR-4 paths)
    ERPX_LOGS_DIR: Path = field(default_factory=lambda: Path(os.getenv("ERPX_LOGS_DIR", str(get_logs_dir()))))
    ERPX_ARTIFACTS_DIR: Path = field(
        default_factory=lambda: Path(os.getenv("ERPX_ARTIFACTS_DIR", str(get_artifacts_dir())))
    )
    ERPX_REPORTS_DIR: Path = field(default_factory=lambda: Path(os.getenv("ERPX_REPORTS_DIR", str(get_reports_dir()))))

    # ==========================================================================
    # API
    # ==========================================================================
    API_HOST: str = field(default_factory=lambda: os.getenv("API_HOST", "0.0.0.0"))
    API_PORT: int = field(default_factory=lambda: _get_int("API_PORT", 8000))
    API_BASE_URL: str = field(default_factory=lambda: os.getenv("API_BASE_URL", "http://localhost:8000"))

    # ==========================================================================
    # LLM - DO Agent (qwen3-32b ONLY)
    # ==========================================================================
    LLM_PROVIDER: str = field(default_factory=lambda: os.getenv("LLM_PROVIDER", "do_agent"))
    DO_AGENT_URL: str = field(
        default_factory=lambda: os.getenv("DO_AGENT_URL", "https://gdfyu2bkvuq4idxkb6x2xkpe.agents.do-ai.run")
    )
    DO_AGENT_KEY: str = field(default_factory=lambda: os.getenv("DO_AGENT_KEY", ""))
    DO_AGENT_MODEL: str = field(default_factory=lambda: os.getenv("DO_AGENT_MODEL", "qwen3-32b"))
    DO_AGENT_TIMEOUT: int = field(default_factory=lambda: _get_int("DO_AGENT_TIMEOUT", 60))

    # ==========================================================================
    # Database
    # ==========================================================================
    DATABASE_URL: str = field(
        default_factory=lambda: os.getenv("DATABASE_URL", "postgresql://erpx:erpx_secret@localhost:5432/erpx")
    )

    # ==========================================================================
    # Storage (MinIO)
    # ==========================================================================
    MINIO_ENDPOINT: str = field(default_factory=lambda: os.getenv("MINIO_ENDPOINT", "localhost:9000"))
    MINIO_ACCESS_KEY: str = field(default_factory=lambda: os.getenv("MINIO_ACCESS_KEY", "erpx_minio"))
    MINIO_SECRET_KEY: str = field(default_factory=lambda: os.getenv("MINIO_SECRET_KEY", "erpx_minio_secret"))
    MINIO_BUCKET: str = field(default_factory=lambda: os.getenv("MINIO_BUCKET", "erpx-documents"))
    MINIO_SECURE: bool = field(default_factory=lambda: _get_bool("MINIO_SECURE", False))

    # ==========================================================================
    # Vector DB (Qdrant)
    # ==========================================================================
    QDRANT_URL: str = field(default_factory=lambda: os.getenv("QDRANT_URL", "http://localhost:6333"))
    QDRANT_TOP_K: int = field(default_factory=lambda: _get_int("QDRANT_TOP_K", 5))
    # Note: QDRANT_DIM=1024 is hardcoded per rules - do NOT change

    # ==========================================================================
    # Workflow (Temporal)
    # ==========================================================================
    TEMPORAL_ADDRESS: str = field(default_factory=lambda: os.getenv("TEMPORAL_ADDRESS", "localhost:7233"))
    # Note: namespace=default, workflow=erpx-document-processing - do NOT change

    # ==========================================================================
    # Policy (OPA)
    # ==========================================================================
    OPA_URL: str = field(default_factory=lambda: os.getenv("OPA_URL", "http://localhost:8181"))

    # ==========================================================================
    # Observability
    # ==========================================================================
    OTEL_ENDPOINT: str = field(
        default_factory=lambda: os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
    )

    # ==========================================================================
    # Guardrails
    # ==========================================================================
    MIN_CONFIDENCE: float = field(default_factory=lambda: _get_float("MIN_CONFIDENCE", 0.6))
    HUMAN_REVIEW_THRESHOLD: float = field(default_factory=lambda: _get_float("HUMAN_REVIEW_THRESHOLD", 0.8))
    MAX_FILE_SIZE_MB: int = field(default_factory=lambda: _get_int("MAX_FILE_SIZE_MB", 50))
    MAX_TEXT_LENGTH: int = field(default_factory=lambda: _get_int("MAX_TEXT_LENGTH", 50000))
    MAX_JOURNAL_ENTRIES: int = field(default_factory=lambda: _get_int("MAX_JOURNAL_ENTRIES", 20))
    MAX_AMOUNT: float = field(default_factory=lambda: _get_float("MAX_AMOUNT", 1_000_000_000))
    PII_DETECTION_ENABLED: bool = field(default_factory=lambda: _get_bool("PII_DETECTION_ENABLED", True))

    # ==========================================================================
    # Telegram
    # ==========================================================================
    TELEGRAM_BOT_TOKEN: str = field(default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN", ""))

    def validate_soft(self) -> list[str]:
        """
        Soft validation - returns list of warnings instead of raising.
        Use this for startup checks without crashing.
        """
        warnings = []

        if self.LLM_PROVIDER != "do_agent":
            warnings.append(f"LLM_PROVIDER should be 'do_agent', got '{self.LLM_PROVIDER}'")

        if not self.DO_AGENT_KEY:
            warnings.append("DO_AGENT_KEY is not set - LLM calls will fail")

        if not self.DO_AGENT_URL:
            warnings.append("DO_AGENT_URL is not set")

        return warnings

    def validate_hard(self):
        """
        Hard validation - raises ValueError if critical config is missing.
        Use this when LLM is actually needed.
        """
        if self.LLM_PROVIDER != "do_agent":
            raise ValueError(f"LLM_PROVIDER must be 'do_agent', got '{self.LLM_PROVIDER}'")
        if not self.DO_AGENT_KEY:
            raise ValueError("DO_AGENT_KEY is required")
        if not self.DO_AGENT_URL:
            raise ValueError("DO_AGENT_URL is required")


# Singleton instance - cached
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """
    Get the singleton Settings instance.
    Thread-safe, cached after first call.
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings() -> Settings:
    """
    Force reload settings from environment.
    Useful for testing.
    """
    global _settings
    _settings = Settings()
    return _settings


# Convenience alias
settings = get_settings()


if __name__ == "__main__":
    # Test/demo
    s = get_settings()
    print(f"ENV: {s.ENV}")
    print(f"LOG_LEVEL: {s.LOG_LEVEL}")
    print(f"JSON_LOGS: {s.JSON_LOGS}")
    print(f"API_HOST: {s.API_HOST}:{s.API_PORT}")
    print(f"DATABASE_URL: {s.DATABASE_URL[:30]}...")
    print(f"TEMPORAL_ADDRESS: {s.TEMPORAL_ADDRESS}")
    print(f"QDRANT_URL: {s.QDRANT_URL}")
    print(f"ERPX_LOGS_DIR: {s.ERPX_LOGS_DIR}")

    warnings = s.validate_soft()
    if warnings:
        print(f"\nWarnings: {warnings}")
    else:
        print("\n✓ Config validated (soft)")
