# src/insights/cfo.py
"""
PR21: AI CFO/Controller Insights Engine

Generates deterministic insights and recommendations based on:
- ledger_entries, ledger_lines (actual transactions)
- cashflow_forecasts (PR20)
- scenario_simulations (PR20)

No external LLM calls - fully deterministic for CI compatibility.
"""

import json
import logging
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

logger = logging.getLogger(__name__)


async def generate_cfo_insight(
    conn, tenant_id: uuid.UUID, window_days: int = 30, assumptions: dict | None = None
) -> dict[str, Any]:
    """
    Generate CFO insights from ledger data and forecasts.

    Args:
        conn: Async database connection (asyncpg)
        tenant_id: Tenant UUID
        window_days: Days of historical data to analyze
        assumptions: Optional parameters for analysis

    Returns:
        Insight result dict with summary, findings, recommendations, references
    """
    # Calculate date window
    end_date = date.today()
    start_date = end_date - timedelta(days=window_days)

    # Gather data
    ledger_stats = await _get_ledger_stats(conn, tenant_id, start_date, end_date)
    top_vendors = await _get_top_vendors(conn, tenant_id, start_date, end_date)
    forecast_data = await _get_latest_forecast(conn, tenant_id)
    simulation_data = await _get_latest_simulation(conn, tenant_id)

    # Generate insights
    findings = _generate_findings(ledger_stats, top_vendors, forecast_data, simulation_data)
    recommendations = _generate_recommendations(ledger_stats, forecast_data, simulation_data)
    references = _collect_references(ledger_stats, forecast_data, simulation_data)

    # Build summary
    summary = _build_summary(ledger_stats, forecast_data, window_days)

    result = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "window_days": window_days,
        "analysis_period": {"start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
        "summary": summary,
        "top_findings": findings,
        "recommendations": recommendations,
        "references": references,
        "metrics": {
            "ledger_entries_analyzed": ledger_stats.get("entry_count", 0),
            "total_debit": float(ledger_stats.get("total_debit", 0)),
            "total_credit": float(ledger_stats.get("total_credit", 0)),
            "net_position": float(ledger_stats.get("net_position", 0)),
            "vendors_count": len(top_vendors),
        },
    }

    return result


async def _get_ledger_stats(conn, tenant_id: uuid.UUID, start_date: date, end_date: date) -> dict:
    """Get aggregated ledger statistics for the period."""
    row = await conn.fetchrow(
        """
        SELECT 
            COUNT(DISTINCT le.id) as entry_count,
            COALESCE(SUM(ll.debit_amount), 0) as total_debit,
            COALESCE(SUM(ll.credit_amount), 0) as total_credit,
            COALESCE(SUM(ll.debit_amount), 0) - COALESCE(SUM(ll.credit_amount), 0) as net_position,
            MIN(le.entry_date) as first_entry_date,
            MAX(le.entry_date) as last_entry_date
        FROM ledger_entries le
        LEFT JOIN ledger_lines ll ON ll.ledger_entry_id = le.id
        WHERE le.tenant_id = $1
          AND le.entry_date >= $2
          AND le.entry_date <= $3
    """,
        tenant_id,
        start_date,
        end_date,
    )

    if not row:
        return {"entry_count": 0, "total_debit": Decimal(0), "total_credit": Decimal(0), "net_position": Decimal(0)}

    return {
        "entry_count": row["entry_count"] or 0,
        "total_debit": row["total_debit"] or Decimal(0),
        "total_credit": row["total_credit"] or Decimal(0),
        "net_position": row["net_position"] or Decimal(0),
        "first_entry_date": row["first_entry_date"],
        "last_entry_date": row["last_entry_date"],
    }


async def _get_top_vendors(conn, tenant_id: uuid.UUID, start_date: date, end_date: date, limit: int = 5) -> list:
    """Get top vendors by transaction volume."""
    rows = await conn.fetch(
        """
        SELECT 
            ei.vendor_name,
            COUNT(*) as transaction_count,
            SUM(ei.total_amount) as total_amount
        FROM extracted_invoices ei
        JOIN documents d ON d.id = ei.document_id
        WHERE ei.tenant_id = $1
          AND ei.invoice_date >= $2
          AND ei.invoice_date <= $3
          AND ei.vendor_name IS NOT NULL
          AND ei.vendor_name != ''
        GROUP BY ei.vendor_name
        ORDER BY total_amount DESC NULLS LAST
        LIMIT $4
    """,
        tenant_id,
        start_date,
        end_date,
        limit,
    )

    return [
        {
            "vendor_name": row["vendor_name"],
            "transaction_count": row["transaction_count"],
            "total_amount": float(row["total_amount"]) if row["total_amount"] else 0,
        }
        for row in rows
    ]


async def _get_latest_forecast(conn, tenant_id: uuid.UUID) -> dict | None:
    """Get the most recent cashflow forecast."""
    row = await conn.fetchrow(
        """
        SELECT id, as_of_date, window_days, forecast, created_at
        FROM cashflow_forecasts
        WHERE tenant_id = $1
        ORDER BY created_at DESC
        LIMIT 1
    """,
        tenant_id,
    )

    if not row:
        return None

    # Handle forecast - might be dict or string
    forecast = row["forecast"]
    if isinstance(forecast, str):
        forecast = json.loads(forecast)

    return {
        "forecast_id": str(row["id"]),
        "as_of_date": row["as_of_date"].isoformat() if row["as_of_date"] else None,
        "window_days": row["window_days"],
        "forecast": forecast or {},
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }


async def _get_latest_simulation(conn, tenant_id: uuid.UUID) -> dict | None:
    """Get the most recent scenario simulation."""
    row = await conn.fetchrow(
        """
        SELECT id, base_as_of_date, inputs, result, created_at
        FROM scenario_simulations
        WHERE tenant_id = $1
        ORDER BY created_at DESC
        LIMIT 1
    """,
        tenant_id,
    )

    if not row:
        return None

    # Handle inputs and result - might be dict or string
    inputs = row["inputs"]
    result = row["result"]
    if isinstance(inputs, str):
        inputs = json.loads(inputs)
    if isinstance(result, str):
        result = json.loads(result)

    return {
        "simulation_id": str(row["id"]),
        "base_as_of_date": row["base_as_of_date"].isoformat() if row["base_as_of_date"] else None,
        "inputs": inputs or {},
        "result": result or {},
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }


def _generate_findings(
    ledger_stats: dict, top_vendors: list, forecast_data: dict | None, simulation_data: dict | None
) -> list[dict]:
    """Generate top findings based on data analysis."""
    findings = []

    # Finding 1: Transaction volume
    entry_count = ledger_stats.get("entry_count", 0)
    if entry_count > 0:
        findings.append(
            {
                "id": "F001",
                "category": "transaction_volume",
                "severity": "info",
                "title": "Transaction Activity",
                "description": f"Processed {entry_count} ledger entries in the analysis period.",
                "impact": "normal",
            }
        )
    else:
        findings.append(
            {
                "id": "F001",
                "category": "transaction_volume",
                "severity": "warning",
                "title": "Low Transaction Activity",
                "description": "No ledger entries found in the analysis period.",
                "impact": "review_needed",
            }
        )

    # Finding 2: Net position
    net_position = float(ledger_stats.get("net_position", 0))
    total_debit = float(ledger_stats.get("total_debit", 0))

    if total_debit > 0:
        net_ratio = net_position / total_debit if total_debit != 0 else 0
        severity = "info" if -0.2 <= net_ratio <= 0.2 else ("warning" if abs(net_ratio) <= 0.5 else "alert")

        findings.append(
            {
                "id": "F002",
                "category": "financial_position",
                "severity": severity,
                "title": "Net Position Analysis",
                "description": f"Net position is {net_position:,.2f} ({net_ratio * 100:.1f}% of total debits).",
                "impact": "balanced" if severity == "info" else "imbalanced",
            }
        )

    # Finding 3: Vendor concentration
    if top_vendors:
        top_vendor = top_vendors[0]
        findings.append(
            {
                "id": "F003",
                "category": "vendor_analysis",
                "severity": "info",
                "title": "Top Vendor",
                "description": f"Highest spending with {top_vendor['vendor_name']}: {top_vendor['total_amount']:,.2f} across {top_vendor['transaction_count']} transactions.",
                "impact": "concentration_noted",
            }
        )

    # Finding 4: Forecast availability
    if forecast_data:
        forecast = forecast_data.get("forecast", {})
        expected_net = forecast.get("summary", {}).get("total_expected_net", 0)
        findings.append(
            {
                "id": "F004",
                "category": "forecasting",
                "severity": "info",
                "title": "Cashflow Forecast Available",
                "description": f"30-day forecast projects net cashflow of {expected_net:,.2f}.",
                "impact": "forecast_available",
            }
        )
    else:
        findings.append(
            {
                "id": "F004",
                "category": "forecasting",
                "severity": "warning",
                "title": "No Forecast Available",
                "description": "No cashflow forecast has been generated. Consider running POST /v1/forecast/cashflow.",
                "impact": "forecast_missing",
            }
        )

    # Finding 5: Simulation insights
    if simulation_data:
        result = simulation_data.get("result", {})
        summary = result.get("summary", {})
        delta = summary.get("total_delta", 0)
        impact_pct = summary.get("impact_percent", 0)

        severity = "info" if abs(impact_pct) < 10 else ("warning" if abs(impact_pct) < 25 else "alert")
        findings.append(
            {
                "id": "F005",
                "category": "scenario_analysis",
                "severity": severity,
                "title": "Scenario Impact",
                "description": f"Latest scenario simulation shows {impact_pct:.1f}% impact (delta: {delta:,.2f}).",
                "impact": "scenario_analyzed",
            }
        )

    return findings[:5]  # Ensure at least top 5


def _generate_recommendations(
    ledger_stats: dict, forecast_data: dict | None, simulation_data: dict | None
) -> list[dict]:
    """Generate actionable recommendations."""
    recommendations = []

    # Recommendation 1: Based on net position
    net_position = float(ledger_stats.get("net_position", 0))
    if net_position < 0:
        recommendations.append(
            {
                "id": "R001",
                "priority": "high",
                "category": "cash_management",
                "title": "Review Cash Position",
                "action": "Investigate negative net position and consider accelerating receivables collection.",
                "expected_benefit": "Improved liquidity",
            }
        )
    else:
        recommendations.append(
            {
                "id": "R001",
                "priority": "medium",
                "category": "cash_management",
                "title": "Optimize Cash Deployment",
                "action": "Consider short-term investment options for excess cash.",
                "expected_benefit": "Increased returns",
            }
        )

    # Recommendation 2: Forecasting
    if not forecast_data:
        recommendations.append(
            {
                "id": "R002",
                "priority": "high",
                "category": "planning",
                "title": "Enable Cashflow Forecasting",
                "action": "Generate baseline forecast using POST /v1/forecast/cashflow to improve planning.",
                "expected_benefit": "Better visibility into future cash needs",
            }
        )
    else:
        recommendations.append(
            {
                "id": "R002",
                "priority": "low",
                "category": "planning",
                "title": "Refresh Forecast Regularly",
                "action": "Update cashflow forecast weekly to maintain accuracy.",
                "expected_benefit": "Accurate financial planning",
            }
        )

    # Recommendation 3: Scenario planning
    if not simulation_data:
        recommendations.append(
            {
                "id": "R003",
                "priority": "medium",
                "category": "risk_management",
                "title": "Run What-If Scenarios",
                "action": "Create scenario simulations to stress-test financial plans.",
                "expected_benefit": "Better risk preparedness",
            }
        )
    else:
        inputs = simulation_data.get("inputs", {})
        assumptions = inputs.get("assumptions", {})
        cost_mult = assumptions.get("cost_multiplier", 1.0)

        if cost_mult > 1.0:
            recommendations.append(
                {
                    "id": "R003",
                    "priority": "medium",
                    "category": "cost_control",
                    "title": "Monitor Cost Increases",
                    "action": f"Scenario assumes {(cost_mult - 1) * 100:.0f}% cost increase. Implement cost controls if this materializes.",
                    "expected_benefit": "Maintain profitability",
                }
            )
        else:
            recommendations.append(
                {
                    "id": "R003",
                    "priority": "low",
                    "category": "scenario_planning",
                    "title": "Explore Additional Scenarios",
                    "action": "Test scenarios with different revenue and cost assumptions.",
                    "expected_benefit": "Comprehensive risk assessment",
                }
            )

    # Recommendation 4: Entry volume based
    entry_count = ledger_stats.get("entry_count", 0)
    if entry_count > 100:
        recommendations.append(
            {
                "id": "R004",
                "priority": "medium",
                "category": "process_efficiency",
                "title": "Review High-Volume Processing",
                "action": "Consider batch processing optimizations for high transaction volumes.",
                "expected_benefit": "Improved processing efficiency",
            }
        )
    else:
        recommendations.append(
            {
                "id": "R004",
                "priority": "low",
                "category": "automation",
                "title": "Increase Automation",
                "action": "Automate more document processing to increase throughput.",
                "expected_benefit": "Reduced manual effort",
            }
        )

    return recommendations[:4]  # At least 3-4 recommendations


def _collect_references(ledger_stats: dict, forecast_data: dict | None, simulation_data: dict | None) -> list[dict]:
    """Collect references to source data."""
    references = []

    # Add ledger reference
    if ledger_stats.get("entry_count", 0) > 0:
        references.append(
            {
                "type": "ledger_summary",
                "description": f"Analyzed {ledger_stats['entry_count']} ledger entries",
                "period": {
                    "start": ledger_stats.get("first_entry_date").isoformat()
                    if ledger_stats.get("first_entry_date")
                    else None,
                    "end": ledger_stats.get("last_entry_date").isoformat()
                    if ledger_stats.get("last_entry_date")
                    else None,
                },
            }
        )

    # Add forecast reference
    if forecast_data:
        references.append(
            {
                "type": "cashflow_forecast",
                "forecast_id": forecast_data["forecast_id"],
                "as_of_date": forecast_data["as_of_date"],
                "created_at": forecast_data["created_at"],
            }
        )

    # Add simulation reference
    if simulation_data:
        references.append(
            {
                "type": "scenario_simulation",
                "simulation_id": simulation_data["simulation_id"],
                "base_as_of_date": simulation_data["base_as_of_date"],
                "created_at": simulation_data["created_at"],
            }
        )

    return references


def _build_summary(ledger_stats: dict, forecast_data: dict | None, window_days: int) -> str:
    """Build executive summary string."""
    entry_count = ledger_stats.get("entry_count", 0)
    total_debit = float(ledger_stats.get("total_debit", 0))
    total_credit = float(ledger_stats.get("total_credit", 0))
    net_position = float(ledger_stats.get("net_position", 0))

    summary_parts = [
        f"Analysis of {window_days}-day period:",
        f"- {entry_count} ledger entries processed",
        f"- Total debits: {total_debit:,.2f}",
        f"- Total credits: {total_credit:,.2f}",
        f"- Net position: {net_position:,.2f}",
    ]

    if forecast_data:
        forecast = forecast_data.get("forecast", {})
        expected = forecast.get("summary", {}).get("total_expected_net", 0)
        summary_parts.append(f"- 30-day forecast: {expected:,.2f} expected net")

    return " | ".join(summary_parts)


# ============================================================
# Persistence functions
# ============================================================


async def create_insight_record(
    conn, tenant_id: uuid.UUID, window_days: int = 30, inputs: dict | None = None
) -> uuid.UUID:
    """Create a new insight record with status=queued."""
    insight_id = uuid.uuid4()

    await conn.execute(
        """
        INSERT INTO cfo_insights (id, tenant_id, status, source_window_days, inputs, created_at)
        VALUES ($1, $2, 'queued', $3, $4, NOW())
    """,
        insight_id,
        tenant_id,
        window_days,
        json.dumps(inputs or {}),
    )

    logger.info(f"Created CFO insight record {insight_id} for tenant {tenant_id}")
    return insight_id


async def update_insight_status(
    conn, insight_id: uuid.UUID, status: str, result: dict | None = None, error_message: str | None = None
) -> None:
    """Update insight status and result."""
    if status == "running":
        await conn.execute(
            """
            UPDATE cfo_insights 
            SET status = $2, started_at = NOW()
            WHERE id = $1
        """,
            insight_id,
            status,
        )
    elif status == "completed":
        await conn.execute(
            """
            UPDATE cfo_insights 
            SET status = $2, result = $3, completed_at = NOW()
            WHERE id = $1
        """,
            insight_id,
            status,
            json.dumps(result) if result else None,
        )
    elif status == "failed":
        await conn.execute(
            """
            UPDATE cfo_insights 
            SET status = $2, error_message = $3, completed_at = NOW()
            WHERE id = $1
        """,
            insight_id,
            status,
            error_message,
        )

    logger.info(f"Updated CFO insight {insight_id} status to {status}")


async def get_insight(conn, insight_id: uuid.UUID) -> dict | None:
    """Get insight by ID."""
    row = await conn.fetchrow(
        """
        SELECT id, tenant_id, status, source_window_days, inputs, result, 
               error_message, created_at, started_at, completed_at
        FROM cfo_insights
        WHERE id = $1
    """,
        insight_id,
    )

    if not row:
        return None

    # Handle inputs and result - might be dict or string
    inputs = row["inputs"]
    result = row["result"]
    if isinstance(inputs, str):
        inputs = json.loads(inputs) if inputs else {}
    if isinstance(result, str):
        result = json.loads(result) if result else None

    return {
        "insight_id": str(row["id"]),
        "tenant_id": str(row["tenant_id"]),
        "status": row["status"],
        "source_window_days": row["source_window_days"],
        "inputs": inputs or {},
        "result": result,
        "error_message": row["error_message"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "started_at": row["started_at"].isoformat() if row["started_at"] else None,
        "completed_at": row["completed_at"].isoformat() if row["completed_at"] else None,
    }


async def get_latest_insights(conn, tenant_id: uuid.UUID, limit: int = 5) -> list[dict]:
    """Get latest insights for a tenant."""
    rows = await conn.fetch(
        """
        SELECT id, tenant_id, status, source_window_days, inputs, result,
               error_message, created_at, started_at, completed_at
        FROM cfo_insights
        WHERE tenant_id = $1
        ORDER BY created_at DESC
        LIMIT $2
    """,
        tenant_id,
        limit,
    )

    result_list = []
    for row in rows:
        # Handle inputs and result - might be dict or string
        inputs = row["inputs"]
        result = row["result"]
        if isinstance(inputs, str):
            inputs = json.loads(inputs) if inputs else {}
        if isinstance(result, str):
            result = json.loads(result) if result else None

        result_list.append(
            {
                "insight_id": str(row["id"]),
                "tenant_id": str(row["tenant_id"]),
                "status": row["status"],
                "source_window_days": row["source_window_days"],
                "inputs": inputs or {},
                "result": result,
                "error_message": row["error_message"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                "started_at": row["started_at"].isoformat() if row["started_at"] else None,
                "completed_at": row["completed_at"].isoformat() if row["completed_at"] else None,
            }
        )

    return result_list


# ============================================================
# Background processing function
# ============================================================


async def process_insight_async(conn, insight_id: uuid.UUID, tenant_id: uuid.UUID, window_days: int = 30) -> dict:
    """
    Process insight generation in background.
    Updates status: queued -> running -> completed/failed
    Records audit events.
    """
    try:
        # Update to running
        await update_insight_status(conn, insight_id, "running")

        # Generate insight
        result = await generate_cfo_insight(conn, tenant_id, window_days)

        # Update to completed
        await update_insight_status(conn, insight_id, "completed", result=result)

        # Record audit event - completed
        await conn.execute(
            """
            INSERT INTO audit_events (id, job_id, tenant_id, event_type, event_data, created_at)
            VALUES ($1, $2, $3, 'cfo_insight_completed', $4, NOW())
        """,
            uuid.uuid4(),
            insight_id,
            str(tenant_id),
            json.dumps(
                {
                    "insight_id": str(insight_id),
                    "tenant_id": str(tenant_id),
                    "findings_count": len(result.get("top_findings", [])),
                    "recommendations_count": len(result.get("recommendations", [])),
                }
            ),
        )

        logger.info(f"CFO insight {insight_id} completed successfully")
        return result

    except Exception as e:
        logger.error(f"CFO insight {insight_id} failed: {e}")

        # Update to failed
        await update_insight_status(conn, insight_id, "failed", error_message=str(e))

        # Record audit event - failed
        await conn.execute(
            """
            INSERT INTO audit_events (id, job_id, tenant_id, event_type, event_data, created_at)
            VALUES ($1, $2, $3, 'cfo_insight_failed', $4, NOW())
        """,
            uuid.uuid4(),
            insight_id,
            str(tenant_id),
            json.dumps({"insight_id": str(insight_id), "error": str(e)}),
        )

        raise
