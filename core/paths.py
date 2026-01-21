"""
ERPX AI Accounting - Path Configuration
=======================================
Central path helper for runtime directories.
Ensures consistent paths and auto-creates folders.
"""

import os
from pathlib import Path

# Base project root (detect from this file's location)
_PROJECT_ROOT = Path(__file__).parent.parent.resolve()


def get_project_root() -> Path:
    """Get the project root directory."""
    return _PROJECT_ROOT


def get_runtime_dir() -> Path:
    """
    Get runtime directory for temporary/output files.
    Creates the directory if it doesn't exist.
    """
    runtime_dir = _PROJECT_ROOT / "runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    return runtime_dir


def get_artifacts_dir() -> Path:
    """
    Get artifacts directory for runtime artifacts.
    Creates the directory if it doesn't exist.
    """
    artifacts_dir = get_runtime_dir() / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    return artifacts_dir


def get_logs_dir() -> Path:
    """
    Get logs directory for application logs.
    Creates the directory if it doesn't exist.

    Note: Uses runtime/logs/ for new logs.
    Legacy logs/ folder at root is preserved for backward compatibility.
    """
    logs_dir = get_runtime_dir() / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir


def get_reports_dir() -> Path:
    """
    Get reports directory for generated reports.
    Creates the directory if it doesn't exist.

    Note: Uses reports/ at project root (business-critical path).
    """
    reports_dir = _PROJECT_ROOT / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    return reports_dir


def get_data_dir() -> Path:
    """
    Get data directory for business data.
    Creates the directory if it doesn't exist.
    """
    data_dir = _PROJECT_ROOT / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_uploads_dir() -> Path:
    """
    Get uploads directory for incoming files.
    Creates the directory if it doesn't exist.
    """
    uploads_dir = get_data_dir() / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    return uploads_dir


def get_processed_dir() -> Path:
    """
    Get processed directory for processed files.
    Creates the directory if it doesn't exist.
    """
    processed_dir = get_data_dir() / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)
    return processed_dir


def get_archive_dir() -> Path:
    """
    Get archive directory for quarantined/archived files.
    Creates the directory if it doesn't exist.
    """
    archive_dir = _PROJECT_ROOT / "_archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    return archive_dir


# Environment variable overrides (for container deployments)
def _get_env_path(env_var: str, default_path: Path) -> Path:
    """Get path from environment variable or use default."""
    env_value = os.environ.get(env_var)
    if env_value:
        path = Path(env_value)
        path.mkdir(parents=True, exist_ok=True)
        return path
    return default_path


# Convenience functions with env override support
def get_log_file(name: str) -> Path:
    """
    Get full path for a log file.

    Args:
        name: Log file name (without path)

    Returns:
        Full path to the log file
    """
    logs_dir = _get_env_path("ERPX_LOGS_DIR", get_logs_dir())
    return logs_dir / name


def get_artifact_file(name: str) -> Path:
    """
    Get full path for an artifact file.

    Args:
        name: Artifact file name (without path)

    Returns:
        Full path to the artifact file
    """
    artifacts_dir = _get_env_path("ERPX_ARTIFACTS_DIR", get_artifacts_dir())
    return artifacts_dir / name


def get_report_file(name: str) -> Path:
    """
    Get full path for a report file.

    Args:
        name: Report file name (without path)

    Returns:
        Full path to the report file
    """
    reports_dir = _get_env_path("ERPX_REPORTS_DIR", get_reports_dir())
    return reports_dir / name


if __name__ == "__main__":
    # Test/demo
    print(f"Project root:  {get_project_root()}")
    print(f"Runtime dir:   {get_runtime_dir()}")
    print(f"Artifacts dir: {get_artifacts_dir()}")
    print(f"Logs dir:      {get_logs_dir()}")
    print(f"Reports dir:   {get_reports_dir()}")
    print(f"Data dir:      {get_data_dir()}")
    print(f"Uploads dir:   {get_uploads_dir()}")
    print(f"Processed dir: {get_processed_dir()}")
    print(f"Archive dir:   {get_archive_dir()}")
