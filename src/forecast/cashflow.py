# src/forecast/cashflow.py
"""
PR20: Cashflow Forecast - Deterministic baseline forecast from ledger data.

Algorithm (simple + deterministic):
1. Pull last N ledger_lines for tenant (e.g. last 90 days)
2. Compute net daily cashflow proxy:
   - inflow = sum(debit lines on cash/bank accounts) OR fallback heuristic
   - outflow = sum(credit lines)
3. Forecast next 30 days using rolling average of last 14 days net flow
4. Return JSON with daily buckets and summary
"""

import json
import logging
import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

logger = logging.getLogger(__name__)


async def compute_cashflow_forecast(
    conn,
    tenant_id: uuid.UUID,
    as_of_date: date | None = None,
    window_days: int = 30,
    lookback_days: int = 90,
    rolling_window: int = 14,
) -> dict[str, Any]:
    """
    Compute a deterministic cashflow forecast based on ledger data.
    
    Args:
        conn: Async database connection (asyncpg)
        tenant_id: Tenant UUID
        as_of_date: Date to compute forecast from (defaults to today)
        window_days: Number of days to forecast
        lookback_days: Days of historical data to analyze
        rolling_window: Days for rolling average calculation
        
    Returns:
        Forecast dict with daily projections and summary
    """
    if as_of_date is None:
        as_of_date = date.today()
    
    # Calculate lookback period
    start_date = as_of_date - timedelta(days=lookback_days)
    
    # Query daily net cashflow from ledger
    daily_flows = await _get_daily_cashflows(conn, tenant_id, start_date, as_of_date)
    
    # Compute rolling average for forecast
    if daily_flows:
        # Get last N days of actual data
        recent_flows = daily_flows[-rolling_window:] if len(daily_flows) >= rolling_window else daily_flows
        avg_daily_net = sum(recent_flows) / len(recent_flows) if recent_flows else Decimal("0")
    else:
        # Fallback: if no data, assume zero flow
        avg_daily_net = Decimal("0")
    
    # Generate forecast for next window_days
    daily_forecast = []
    for i in range(1, window_days + 1):
        forecast_date = as_of_date + timedelta(days=i)
        daily_forecast.append({
            "date": forecast_date.isoformat(),
            "expected_net": float(round(avg_daily_net, 2))
        })
    
    # Compute summary
    total_expected_net = float(round(avg_daily_net * window_days, 2))
    
    forecast = {
        "as_of_date": as_of_date.isoformat(),
        "window_days": window_days,
        "lookback_days": lookback_days,
        "rolling_window": rolling_window,
        "avg_daily_net": float(round(avg_daily_net, 2)),
        "daily": daily_forecast,
        "summary": {
            "total_expected_net": total_expected_net,
            "historical_data_points": len(daily_flows)
        }
    }
    
    return forecast


async def _get_daily_cashflows(
    conn,
    tenant_id: uuid.UUID,
    start_date: date,
    end_date: date
) -> list[Decimal]:
    """
    Query daily net cashflows from ledger data.
    Returns list of daily net amounts (debit - credit).
    """
    # Get daily net cashflow: sum(debit) - sum(credit) per day
    rows = await conn.fetch("""
        SELECT 
            le.entry_date,
            COALESCE(SUM(ll.debit_amount), 0) - COALESCE(SUM(ll.credit_amount), 0) as net_flow
        FROM ledger_entries le
        JOIN ledger_lines ll ON ll.ledger_entry_id = le.id
        WHERE le.tenant_id = $1
          AND le.entry_date >= $2
          AND le.entry_date <= $3
        GROUP BY le.entry_date
        ORDER BY le.entry_date
    """, tenant_id, start_date, end_date)
    
    # Return just the net flow values
    return [row['net_flow'] for row in rows]


async def persist_forecast(
    conn,
    tenant_id: uuid.UUID,
    forecast: dict[str, Any]
) -> uuid.UUID:
    """
    Persist forecast to cashflow_forecasts table.
    
    Returns:
        The forecast_id (UUID)
    """
    forecast_id = uuid.uuid4()
    
    await conn.execute("""
        INSERT INTO cashflow_forecasts (id, tenant_id, as_of_date, window_days, forecast)
        VALUES ($1, $2, $3, $4, $5)
    """,
        forecast_id,
        tenant_id,
        date.fromisoformat(forecast["as_of_date"]),
        forecast["window_days"],
        json.dumps(forecast)
    )
    
    logger.info(f"Persisted cashflow forecast {forecast_id} for tenant {tenant_id}")
    
    return forecast_id


async def get_latest_forecast(conn, tenant_id: uuid.UUID) -> dict[str, Any] | None:
    """
    Get the most recent forecast for a tenant.
    
    Returns:
        Forecast dict with id and data, or None if not found
    """
    row = await conn.fetchrow("""
        SELECT id, as_of_date, window_days, forecast, created_at
        FROM cashflow_forecasts
        WHERE tenant_id = $1
        ORDER BY created_at DESC
        LIMIT 1
    """, tenant_id)
    
    if not row:
        return None
    
    return {
        "forecast_id": str(row['id']),
        "as_of_date": row['as_of_date'].isoformat() if row['as_of_date'] else None,
        "window_days": row['window_days'],
        "forecast": row['forecast'] if isinstance(row['forecast'], dict) else json.loads(row['forecast']),
        "created_at": row['created_at'].isoformat() if row['created_at'] else None
    }
