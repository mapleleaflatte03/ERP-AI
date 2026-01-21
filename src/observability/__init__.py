"""
ERPX Observability Module
=========================
PR-12: Metrics, evaluation, and alerting.
"""

from .metrics import (
    AlertCondition,
    AlertSeverity,
    MetricType,
    add_evaluation_case,
    check_alerts,
    complete_evaluation_run,
    create_evaluation_run,
    fire_alert,
    get_evaluation_run,
    get_metric_series,
    get_metric_stats,
    list_active_alerts,
    list_evaluation_runs,
    list_metric_names,
    record_counter,
    record_gauge,
    record_histogram,
    record_latency,
    record_metric,
)

__all__ = [
    # Types
    "MetricType",
    "AlertSeverity",
    "AlertCondition",
    # Metrics
    "record_metric",
    "record_counter",
    "record_gauge",
    "record_histogram",
    "record_latency",
    "get_metric_stats",
    "get_metric_series",
    "list_metric_names",
    # Evaluation
    "create_evaluation_run",
    "add_evaluation_case",
    "complete_evaluation_run",
    "get_evaluation_run",
    "list_evaluation_runs",
    # Alerting
    "check_alerts",
    "fire_alert",
    "list_active_alerts",
]
