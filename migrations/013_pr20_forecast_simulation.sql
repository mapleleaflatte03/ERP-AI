-- PR20: Cashflow Forecast + Scenario Simulation tables
-- Migration: 013_pr20_forecast_simulation.sql

-- Table: cashflow_forecasts
-- Stores baseline cashflow forecasts derived from ledger data
CREATE TABLE IF NOT EXISTS cashflow_forecasts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    as_of_date DATE NOT NULL,
    window_days INTEGER NOT NULL DEFAULT 30,
    forecast JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for querying forecasts by tenant
CREATE INDEX IF NOT EXISTS idx_cashflow_forecasts_tenant_created
    ON cashflow_forecasts (tenant_id, created_at DESC);

-- Table: scenario_simulations
-- Stores what-if scenario simulation runs
CREATE TABLE IF NOT EXISTS scenario_simulations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    base_forecast_id UUID REFERENCES cashflow_forecasts(id),
    base_as_of_date DATE NOT NULL,
    inputs JSONB NOT NULL,
    result JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for querying simulations by tenant
CREATE INDEX IF NOT EXISTS idx_scenario_simulations_tenant_created
    ON scenario_simulations (tenant_id, created_at DESC);
