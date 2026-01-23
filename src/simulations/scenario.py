# src/simulations/scenario.py
"""
PR20: Scenario Simulation - What-if analysis on cashflow forecasts.

Takes a baseline forecast and applies scenario assumptions:
- revenue_multiplier: Scale revenue (inflows)
- cost_multiplier: Scale costs (outflows)
- payment_delay_days: Shift timing of flows

Produces projected daily values and delta vs baseline.
"""

import json
import logging
import uuid
from datetime import date, timedelta
from typing import Any

logger = logging.getLogger(__name__)


def run_scenario_simulation(
    tenant_id: uuid.UUID,
    base_forecast: dict[str, Any],
    inputs: dict[str, Any]
) -> dict[str, Any]:
    """
    Run a what-if scenario simulation on a baseline forecast.
    
    Args:
        tenant_id: Tenant UUID  
        base_forecast: The baseline forecast dict (from cashflow.py)
        inputs: Scenario assumptions:
            - window_days: Override forecast window (optional)
            - assumptions:
                - revenue_multiplier: Scale positive flows (default 1.0)
                - cost_multiplier: Scale negative flows (default 1.0)
                - payment_delay_days: Shift timing (default 0)
                
    Returns:
        Simulation result with projected values and deltas
    """
    # Extract inputs
    window_days = inputs.get("window_days", base_forecast.get("window_days", 30))
    assumptions = inputs.get("assumptions", {})
    
    revenue_mult = float(assumptions.get("revenue_multiplier", 1.0))
    cost_mult = float(assumptions.get("cost_multiplier", 1.0))
    delay_days = int(assumptions.get("payment_delay_days", 0))
    
    # Get baseline daily values
    baseline_daily = base_forecast.get("daily", [])
    avg_daily_net = float(base_forecast.get("avg_daily_net", 0))
    
    # Decompose avg_daily_net into revenue and cost components
    # Heuristic: if positive, treat as net revenue; if negative, net cost
    # For simulation, we assume a 60/40 split for illustration
    if avg_daily_net >= 0:
        base_revenue = abs(avg_daily_net) * 1.5  # Gross revenue estimate
        base_cost = abs(avg_daily_net) * 0.5     # Costs that offset
    else:
        base_revenue = abs(avg_daily_net) * 0.3  # Some revenue
        base_cost = abs(avg_daily_net) * 1.3     # Higher costs
    
    # Apply multipliers
    sim_revenue = base_revenue * revenue_mult
    sim_cost = base_cost * cost_mult
    sim_daily_net = sim_revenue - sim_cost
    
    # Generate projected daily values
    as_of_date = date.fromisoformat(base_forecast.get("as_of_date", date.today().isoformat()))
    projected_daily = []
    
    for i in range(1, window_days + 1):
        # Shift by delay_days (payments arrive later)
        effective_day = i - delay_days
        
        if effective_day <= 0:
            # Before delay kicks in, no flow expected
            expected = 0.0
        else:
            expected = round(sim_daily_net, 2)
        
        proj_date = as_of_date + timedelta(days=i)
        
        # Find baseline value for same date
        baseline_val = 0.0
        for bd in baseline_daily:
            if bd.get("date") == proj_date.isoformat():
                baseline_val = bd.get("expected_net", 0)
                break
        
        projected_daily.append({
            "date": proj_date.isoformat(),
            "baseline_net": baseline_val,
            "projected_net": expected,
            "delta": round(expected - baseline_val, 2)
        })
    
    # Compute summary
    total_baseline = sum(d.get("baseline_net", 0) for d in projected_daily)
    total_projected = sum(d.get("projected_net", 0) for d in projected_daily)
    total_delta = round(total_projected - total_baseline, 2)
    
    result = {
        "scenario_applied": {
            "revenue_multiplier": revenue_mult,
            "cost_multiplier": cost_mult,
            "payment_delay_days": delay_days
        },
        "window_days": window_days,
        "base_as_of_date": as_of_date.isoformat(),
        "daily": projected_daily,
        "summary": {
            "total_baseline_net": round(total_baseline, 2),
            "total_projected_net": round(total_projected, 2),
            "total_delta": total_delta,
            "impact_percent": round((total_delta / total_baseline * 100) if total_baseline != 0 else 0, 2)
        }
    }
    
    return result


async def persist_simulation(
    conn,
    tenant_id: uuid.UUID,
    base_forecast_id: uuid.UUID | None,
    base_as_of_date: date,
    inputs: dict[str, Any],
    result: dict[str, Any]
) -> uuid.UUID:
    """
    Persist simulation run to scenario_simulations table.
    
    Returns:
        The simulation_id (UUID)
    """
    simulation_id = uuid.uuid4()
    
    await conn.execute("""
        INSERT INTO scenario_simulations 
            (id, tenant_id, base_forecast_id, base_as_of_date, inputs, result)
        VALUES ($1, $2, $3, $4, $5, $6)
    """,
        simulation_id,
        tenant_id,
        base_forecast_id,
        base_as_of_date,
        json.dumps(inputs),
        json.dumps(result)
    )
    
    logger.info(f"Persisted scenario simulation {simulation_id} for tenant {tenant_id}")
    
    return simulation_id


async def get_simulation(conn, simulation_id: uuid.UUID) -> dict[str, Any] | None:
    """
    Get a simulation by ID.
    
    Returns:
        Simulation dict with all data, or None if not found
    """
    row = await conn.fetchrow("""
        SELECT id, tenant_id, base_forecast_id, base_as_of_date, inputs, result, created_at
        FROM scenario_simulations
        WHERE id = $1
    """, simulation_id)
    
    if not row:
        return None
    
    return {
        "simulation_id": str(row['id']),
        "tenant_id": str(row['tenant_id']),
        "base_forecast_id": str(row['base_forecast_id']) if row['base_forecast_id'] else None,
        "base_as_of_date": row['base_as_of_date'].isoformat() if row['base_as_of_date'] else None,
        "inputs": row['inputs'] if isinstance(row['inputs'], dict) else json.loads(row['inputs']),
        "result": row['result'] if isinstance(row['result'], dict) else json.loads(row['result']),
        "created_at": row['created_at'].isoformat() if row['created_at'] else None
    }
