-- PR21: AI CFO/Controller Insights table
-- Migration: 014_pr21_cfo_insights.sql

-- Table: cfo_insights
-- Stores AI-generated CFO/Controller insights and recommendations
CREATE TABLE IF NOT EXISTS cfo_insights (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'queued',
    source_window_days INTEGER NOT NULL DEFAULT 30,
    inputs JSONB,
    result JSONB,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

-- Index for querying insights by tenant (most recent first)
CREATE INDEX IF NOT EXISTS idx_cfo_insights_tenant_created
    ON cfo_insights (tenant_id, created_at DESC);

-- Index for querying by status (for async worker)
CREATE INDEX IF NOT EXISTS idx_cfo_insights_status
    ON cfo_insights (status);

-- Add constraint to validate status values
ALTER TABLE cfo_insights DROP CONSTRAINT IF EXISTS cfo_insights_status_check;
ALTER TABLE cfo_insights ADD CONSTRAINT cfo_insights_status_check 
    CHECK (status IN ('queued', 'running', 'completed', 'failed'));
