"""
ERPX AI Accounting - Observability Module
=========================================
PR-12: Metrics collection, evaluation, and alerting.

Features:
- Simple metrics recording (counters, gauges, histograms)
- Evaluation run management
- Alert checking and firing
"""

import json
import logging
import time
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

logger = logging.getLogger("erpx.observability")


class MetricType(str, Enum):
    """Metric types."""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"


class AlertSeverity(str, Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertCondition(str, Enum):
    """Alert conditions."""

    GT = "gt"  # Greater than
    LT = "lt"  # Less than
    GTE = "gte"  # Greater than or equal
    LTE = "lte"  # Less than or equal
    EQ = "eq"  # Equal


# ===========================================================================
# Metrics Recording
# ===========================================================================


async def record_metric(
    conn,
    metric_name: str,
    value: float,
    metric_type: MetricType = MetricType.GAUGE,
    labels: dict | None = None,
    bucket: str | None = None,
):
    """
    Record a metric value.

    Args:
        conn: asyncpg connection
        metric_name: Name of the metric
        value: Metric value
        metric_type: Type of metric
        labels: Dimension labels (e.g., {"tenant": "abc", "endpoint": "/upload"})
        bucket: For histograms, the bucket label
    """
    await conn.execute(
        """
        INSERT INTO system_metrics
        (metric_name, metric_type, value, labels, bucket)
        VALUES ($1, $2, $3, $4, $5)
        """,
        metric_name,
        metric_type.value,
        value,
        json.dumps(labels) if labels else "{}",
        bucket,
    )


async def record_counter(conn, metric_name: str, increment: float = 1.0, labels: dict | None = None):
    """Record counter increment."""
    await record_metric(conn, metric_name, increment, MetricType.COUNTER, labels)


async def record_gauge(conn, metric_name: str, value: float, labels: dict | None = None):
    """Record gauge value."""
    await record_metric(conn, metric_name, value, MetricType.GAUGE, labels)


async def record_histogram(
    conn,
    metric_name: str,
    value: float,
    buckets: list[float] = [0.1, 0.5, 1.0, 2.0, 5.0, 10.0],
    labels: dict | None = None,
):
    """Record histogram value into appropriate buckets."""
    for bucket in buckets:
        if value <= bucket:
            await record_metric(conn, metric_name, 1.0, MetricType.HISTOGRAM, labels, f"le_{bucket}")
    # Always record +Inf bucket
    await record_metric(conn, metric_name, 1.0, MetricType.HISTOGRAM, labels, "le_inf")


async def record_latency(conn, metric_name: str, latency_ms: float, labels: dict | None = None):
    """Record latency in milliseconds."""
    await record_gauge(conn, f"{metric_name}_ms", latency_ms, labels)
    # Also record in histogram buckets
    await record_histogram(
        conn,
        f"{metric_name}_histogram",
        latency_ms,
        buckets=[50, 100, 200, 500, 1000, 2000, 5000, 10000],
        labels=labels,
    )


# ===========================================================================
# Metrics Querying
# ===========================================================================


async def get_metric_stats(
    conn,
    metric_name: str,
    hours: int = 24,
) -> dict:
    """Get aggregate stats for a metric."""
    row = await conn.fetchrow(
        """
        SELECT 
            COUNT(*) as sample_count,
            AVG(value) as avg_value,
            MIN(value) as min_value,
            MAX(value) as max_value,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY value) as p50,
            PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY value) as p95,
            PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY value) as p99
        FROM system_metrics
        WHERE metric_name = $1
        AND recorded_at > NOW() - INTERVAL '%s hours'
        """
        % hours,
        metric_name,
    )

    return {
        "metric_name": metric_name,
        "period_hours": hours,
        "sample_count": row["sample_count"],
        "avg": float(row["avg_value"]) if row["avg_value"] else None,
        "min": float(row["min_value"]) if row["min_value"] else None,
        "max": float(row["max_value"]) if row["max_value"] else None,
        "p50": float(row["p50"]) if row["p50"] else None,
        "p95": float(row["p95"]) if row["p95"] else None,
        "p99": float(row["p99"]) if row["p99"] else None,
    }


async def get_metric_series(
    conn,
    metric_name: str,
    hours: int = 24,
    resolution_minutes: int = 5,
) -> list[dict]:
    """Get time series data for a metric."""
    rows = await conn.fetch(
        """
        SELECT 
            DATE_TRUNC('minute', recorded_at) - 
            (EXTRACT(MINUTE FROM recorded_at)::integer %% $3) * INTERVAL '1 minute' as bucket,
            AVG(value) as avg_value,
            COUNT(*) as count
        FROM system_metrics
        WHERE metric_name = $1
        AND recorded_at > NOW() - INTERVAL '%s hours'
        GROUP BY bucket
        ORDER BY bucket DESC
        """
        % hours,
        metric_name,
        resolution_minutes,
    )

    return [
        {
            "timestamp": row["bucket"].isoformat() if row["bucket"] else None,
            "avg_value": float(row["avg_value"]) if row["avg_value"] else None,
            "count": row["count"],
        }
        for row in rows
    ]


async def list_metric_names(conn) -> list[str]:
    """List all unique metric names."""
    rows = await conn.fetch(
        """
        SELECT DISTINCT metric_name 
        FROM system_metrics
        ORDER BY metric_name
        """
    )
    return [row["metric_name"] for row in rows]


# ===========================================================================
# Evaluation Runs
# ===========================================================================


async def create_evaluation_run(
    conn,
    run_name: str,
    run_type: str,
    config: dict | None = None,
    git_commit: str | None = None,
    git_branch: str | None = None,
    environment: str = "test",
    created_by: str | None = None,
) -> str:
    """Create a new evaluation run."""
    run_id = uuid.uuid4()

    await conn.execute(
        """
        INSERT INTO evaluation_runs
        (id, run_name, run_type, config, git_commit, git_branch, environment, created_by)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        """,
        run_id,
        run_name,
        run_type,
        json.dumps(config or {}),
        git_commit,
        git_branch,
        environment,
        created_by,
    )

    logger.info(f"Created evaluation run: {run_name} ({run_id})")
    return str(run_id)


async def add_evaluation_case(
    conn,
    run_id: str,
    case_name: str,
    input_data: dict,
    expected_output: dict | None,
    actual_output: dict | None,
    result: str,  # pass, fail, error, skip
    latency_ms: float | None = None,
    confidence: float | None = None,
    error_message: str | None = None,
    case_number: int | None = None,
) -> str:
    """Add a test case to an evaluation run."""
    case_id = uuid.uuid4()

    # Compute diff if both expected and actual exist
    diff = None
    if expected_output and actual_output:
        diff = compute_diff(expected_output, actual_output)

    await conn.execute(
        """
        INSERT INTO evaluation_cases
        (id, run_id, case_name, case_number, input_data, expected_output,
         actual_output, result, latency_ms, confidence, error_message, diff)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
        """,
        case_id,
        uuid.UUID(run_id),
        case_name,
        case_number,
        json.dumps(input_data),
        json.dumps(expected_output) if expected_output else None,
        json.dumps(actual_output) if actual_output else None,
        result,
        latency_ms,
        confidence,
        error_message,
        json.dumps(diff) if diff else None,
    )

    return str(case_id)


def compute_diff(expected: dict, actual: dict) -> dict:
    """Compute diff between expected and actual outputs."""
    diff = {"missing": [], "extra": [], "different": []}

    for key in expected:
        if key not in actual:
            diff["missing"].append(key)
        elif expected[key] != actual[key]:
            diff["different"].append(
                {
                    "key": key,
                    "expected": expected[key],
                    "actual": actual.get(key),
                }
            )

    for key in actual:
        if key not in expected:
            diff["extra"].append(key)

    return diff if (diff["missing"] or diff["extra"] or diff["different"]) else None


async def complete_evaluation_run(
    conn,
    run_id: str,
) -> dict:
    """Complete evaluation run and compute aggregate metrics."""
    # Get case statistics
    stats = await conn.fetchrow(
        """
        SELECT 
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE result = 'pass') as passed,
            COUNT(*) FILTER (WHERE result = 'fail') as failed,
            COUNT(*) FILTER (WHERE result = 'error') as errors,
            AVG(latency_ms) as avg_latency,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY latency_ms) as p50_latency,
            PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms) as p95_latency,
            PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY latency_ms) as p99_latency,
            AVG(confidence) as avg_confidence
        FROM evaluation_cases
        WHERE run_id = $1
        """,
        uuid.UUID(run_id),
    )

    # Compute accuracy
    total = stats["total"] or 0
    passed = stats["passed"] or 0
    accuracy = passed / total if total > 0 else None

    # Get start time
    run = await conn.fetchrow("SELECT started_at FROM evaluation_runs WHERE id = $1", uuid.UUID(run_id))
    started_at = run["started_at"] if run else datetime.utcnow()
    duration = (datetime.utcnow() - started_at).total_seconds() if started_at else None

    # Update run
    await conn.execute(
        """
        UPDATE evaluation_runs
        SET status = 'completed',
            completed_at = NOW(),
            duration_seconds = $1,
            total_cases = $2,
            passed_cases = $3,
            failed_cases = $4,
            error_cases = $5,
            accuracy = $6,
            avg_latency_ms = $7,
            p50_latency_ms = $8,
            p95_latency_ms = $9,
            p99_latency_ms = $10
        WHERE id = $11
        """,
        duration,
        total,
        passed,
        stats["failed"],
        stats["errors"],
        accuracy,
        float(stats["avg_latency"]) if stats["avg_latency"] else None,
        float(stats["p50_latency"]) if stats["p50_latency"] else None,
        float(stats["p95_latency"]) if stats["p95_latency"] else None,
        float(stats["p99_latency"]) if stats["p99_latency"] else None,
        uuid.UUID(run_id),
    )

    logger.info(
        f"Completed evaluation run {run_id}: {passed}/{total} passed ({accuracy * 100:.1f}%)"
        if accuracy
        else f"Completed evaluation run {run_id}"
    )

    return {
        "run_id": run_id,
        "status": "completed",
        "total_cases": total,
        "passed_cases": passed,
        "failed_cases": stats["failed"],
        "error_cases": stats["errors"],
        "accuracy": accuracy,
        "avg_latency_ms": float(stats["avg_latency"]) if stats["avg_latency"] else None,
    }


async def get_evaluation_run(conn, run_id: str) -> dict | None:
    """Get evaluation run by ID."""
    row = await conn.fetchrow(
        "SELECT * FROM evaluation_runs WHERE id = $1",
        uuid.UUID(run_id),
    )

    if not row:
        return None

    return {
        "id": str(row["id"]),
        "run_name": row["run_name"],
        "run_type": row["run_type"],
        "status": row["status"],
        "total_cases": row["total_cases"],
        "passed_cases": row["passed_cases"],
        "failed_cases": row["failed_cases"],
        "error_cases": row["error_cases"],
        "accuracy": float(row["accuracy"]) if row["accuracy"] else None,
        "avg_latency_ms": float(row["avg_latency_ms"]) if row["avg_latency_ms"] else None,
        "p95_latency_ms": float(row["p95_latency_ms"]) if row["p95_latency_ms"] else None,
        "started_at": row["started_at"].isoformat() if row["started_at"] else None,
        "completed_at": row["completed_at"].isoformat() if row["completed_at"] else None,
        "duration_seconds": float(row["duration_seconds"]) if row["duration_seconds"] else None,
        "environment": row["environment"],
    }


async def list_evaluation_runs(conn, limit: int = 20) -> list[dict]:
    """List recent evaluation runs."""
    rows = await conn.fetch(
        """
        SELECT * FROM evaluation_runs
        ORDER BY started_at DESC
        LIMIT $1
        """,
        limit,
    )

    return [
        {
            "id": str(row["id"]),
            "run_name": row["run_name"],
            "run_type": row["run_type"],
            "status": row["status"],
            "accuracy": float(row["accuracy"]) if row["accuracy"] else None,
            "total_cases": row["total_cases"],
            "started_at": row["started_at"].isoformat() if row["started_at"] else None,
        }
        for row in rows
    ]


# ===========================================================================
# Alert Management
# ===========================================================================


async def check_alerts(conn) -> list[dict]:
    """Check all active alert rules and fire if needed."""
    rules = await conn.fetch("SELECT * FROM alert_rules WHERE is_active = TRUE")

    fired_alerts = []

    for rule in rules:
        try:
            # Get recent metric values
            stats = await get_metric_stats(
                conn,
                rule["metric_name"],
                hours=rule["evaluation_window_minutes"] / 60,
            )

            if stats["sample_count"] == 0:
                continue

            avg_value = stats["avg"]
            if avg_value is None:
                continue

            # Check condition
            triggered = False
            condition = rule["condition"]
            threshold = rule["threshold"]

            if condition == "gt" and avg_value > threshold:
                triggered = True
            elif condition == "lt" and avg_value < threshold:
                triggered = True
            elif condition == "gte" and avg_value >= threshold:
                triggered = True
            elif condition == "lte" and avg_value <= threshold:
                triggered = True
            elif condition == "eq" and avg_value == threshold:
                triggered = True

            if triggered:
                # Fire alert
                alert = await fire_alert(
                    conn,
                    rule_id=str(rule["id"]),
                    rule_name=rule["name"],
                    metric_name=rule["metric_name"],
                    metric_value=avg_value,
                    threshold=threshold,
                    severity=rule["severity"],
                )
                fired_alerts.append(alert)

        except Exception as e:
            logger.error(f"Alert check failed for rule {rule['name']}: {e}")

    return fired_alerts


async def fire_alert(
    conn,
    rule_id: str,
    rule_name: str,
    metric_name: str,
    metric_value: float,
    threshold: float,
    severity: str,
) -> dict:
    """Fire an alert."""
    alert_id = uuid.uuid4()

    await conn.execute(
        """
        INSERT INTO alert_history
        (id, rule_id, rule_name, metric_name, metric_value, threshold, severity)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        """,
        alert_id,
        uuid.UUID(rule_id),
        rule_name,
        metric_name,
        metric_value,
        threshold,
        severity,
    )

    # Update rule last triggered
    await conn.execute(
        "UPDATE alert_rules SET last_triggered_at = NOW() WHERE id = $1",
        uuid.UUID(rule_id),
    )

    logger.warning(f"ALERT [{severity.upper()}] {rule_name}: {metric_name}={metric_value:.2f} (threshold: {threshold})")

    return {
        "alert_id": str(alert_id),
        "rule_name": rule_name,
        "metric_name": metric_name,
        "metric_value": metric_value,
        "threshold": threshold,
        "severity": severity,
    }


async def list_active_alerts(conn) -> list[dict]:
    """List currently firing alerts."""
    rows = await conn.fetch(
        """
        SELECT * FROM alert_history
        WHERE status = 'firing'
        ORDER BY triggered_at DESC
        """
    )

    return [
        {
            "id": str(row["id"]),
            "rule_name": row["rule_name"],
            "metric_name": row["metric_name"],
            "metric_value": float(row["metric_value"]),
            "threshold": float(row["threshold"]),
            "severity": row["severity"],
            "triggered_at": row["triggered_at"].isoformat() if row["triggered_at"] else None,
        }
        for row in rows
    ]
