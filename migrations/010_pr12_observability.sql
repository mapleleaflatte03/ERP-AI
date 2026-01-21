-- PR-12: Observability & Evaluation
-- ================================
-- Metrics storage, evaluation runs, and system insights

-- ============================================
-- System Metrics Table
-- ============================================
-- Time-series metrics storage (simple, no external dependency)

CREATE TABLE IF NOT EXISTS system_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Metric identification
    metric_name VARCHAR(100) NOT NULL,
    metric_type VARCHAR(20) NOT NULL, -- counter, gauge, histogram
    
    -- Labels (dimensions)
    labels JSONB DEFAULT '{}',
    
    -- Values
    value DOUBLE PRECISION NOT NULL,
    bucket VARCHAR(20), -- For histogram: 'le_0.1', 'le_0.5', etc.
    
    -- Timestamps
    recorded_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Aggregation helper
    minute_bucket TIMESTAMPTZ DEFAULT DATE_TRUNC('minute', NOW())
);

-- Indexes for querying
CREATE INDEX IF NOT EXISTS idx_metrics_name ON system_metrics(metric_name);
CREATE INDEX IF NOT EXISTS idx_metrics_time ON system_metrics(recorded_at);
CREATE INDEX IF NOT EXISTS idx_metrics_bucket ON system_metrics(minute_bucket);
CREATE INDEX IF NOT EXISTS idx_metrics_name_time ON system_metrics(metric_name, recorded_at DESC);

-- ============================================
-- Evaluation Runs Table
-- ============================================
-- Track model/system evaluation runs

CREATE TABLE IF NOT EXISTS evaluation_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Run identification
    run_name VARCHAR(100) NOT NULL,
    run_type VARCHAR(50) NOT NULL, -- accuracy, latency, end_to_end, regression
    
    -- Configuration
    config JSONB NOT NULL DEFAULT '{}',
    
    -- Status
    status VARCHAR(20) DEFAULT 'running', -- running, completed, failed
    
    -- Timing
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    duration_seconds DOUBLE PRECISION,
    
    -- Results summary
    total_cases INTEGER DEFAULT 0,
    passed_cases INTEGER DEFAULT 0,
    failed_cases INTEGER DEFAULT 0,
    error_cases INTEGER DEFAULT 0,
    
    -- Aggregate metrics
    accuracy DOUBLE PRECISION,
    precision_score DOUBLE PRECISION,
    recall_score DOUBLE PRECISION,
    f1_score DOUBLE PRECISION,
    avg_latency_ms DOUBLE PRECISION,
    p50_latency_ms DOUBLE PRECISION,
    p95_latency_ms DOUBLE PRECISION,
    p99_latency_ms DOUBLE PRECISION,
    
    -- Full results
    results JSONB DEFAULT '[]',
    
    -- Git info
    git_commit VARCHAR(40),
    git_branch VARCHAR(100),
    
    -- Environment
    environment VARCHAR(20) DEFAULT 'test', -- test, staging, production
    
    created_by VARCHAR(100)
);

CREATE INDEX IF NOT EXISTS idx_eval_runs_name ON evaluation_runs(run_name);
CREATE INDEX IF NOT EXISTS idx_eval_runs_type ON evaluation_runs(run_type);
CREATE INDEX IF NOT EXISTS idx_eval_runs_status ON evaluation_runs(status);
CREATE INDEX IF NOT EXISTS idx_eval_runs_time ON evaluation_runs(started_at DESC);

-- ============================================
-- Evaluation Cases Table
-- ============================================
-- Individual test cases within evaluation runs

CREATE TABLE IF NOT EXISTS evaluation_cases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Run reference
    run_id UUID NOT NULL REFERENCES evaluation_runs(id) ON DELETE CASCADE,
    
    -- Case identification
    case_name VARCHAR(200) NOT NULL,
    case_number INTEGER,
    
    -- Input
    input_data JSONB NOT NULL,
    expected_output JSONB,
    
    -- Output
    actual_output JSONB,
    
    -- Result
    result VARCHAR(20) NOT NULL, -- pass, fail, error, skip
    error_message TEXT,
    
    -- Metrics
    latency_ms DOUBLE PRECISION,
    confidence DOUBLE PRECISION,
    
    -- Comparison details
    diff JSONB, -- Diff between expected and actual
    
    -- Timestamps
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_eval_cases_run ON evaluation_cases(run_id);
CREATE INDEX IF NOT EXISTS idx_eval_cases_result ON evaluation_cases(result);

-- ============================================
-- Model Performance Snapshots
-- ============================================
-- Track model performance over time

CREATE TABLE IF NOT EXISTS model_performance_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Model identification
    model_name VARCHAR(100) NOT NULL,
    model_version VARCHAR(50),
    
    -- Performance metrics
    accuracy DOUBLE PRECISION,
    avg_latency_ms DOUBLE PRECISION,
    error_rate DOUBLE PRECISION,
    
    -- Volume
    total_requests INTEGER,
    successful_requests INTEGER,
    failed_requests INTEGER,
    
    -- Time window
    snapshot_date DATE NOT NULL DEFAULT CURRENT_DATE,
    snapshot_hour INTEGER,
    
    -- Additional metrics
    metrics JSONB DEFAULT '{}',
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT uk_model_snapshot UNIQUE(model_name, snapshot_date, snapshot_hour)
);

CREATE INDEX IF NOT EXISTS idx_model_perf_name ON model_performance_snapshots(model_name);
CREATE INDEX IF NOT EXISTS idx_model_perf_date ON model_performance_snapshots(snapshot_date DESC);

-- ============================================
-- Alert Rules Table
-- ============================================
-- Define alerting thresholds

CREATE TABLE IF NOT EXISTS alert_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Rule identification
    name VARCHAR(100) NOT NULL,
    description TEXT,
    
    -- Metric configuration
    metric_name VARCHAR(100) NOT NULL,
    condition VARCHAR(20) NOT NULL, -- gt, lt, gte, lte, eq
    threshold DOUBLE PRECISION NOT NULL,
    
    -- Evaluation
    evaluation_window_minutes INTEGER DEFAULT 5,
    min_violations INTEGER DEFAULT 1,
    
    -- Actions
    severity VARCHAR(20) DEFAULT 'warning', -- info, warning, critical
    notification_channels TEXT[] DEFAULT ARRAY['log'],
    
    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    last_triggered_at TIMESTAMPTZ,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_alert_rules_active ON alert_rules(is_active);
CREATE INDEX IF NOT EXISTS idx_alert_rules_metric ON alert_rules(metric_name);

-- ============================================
-- Alert History Table
-- ============================================
-- Track triggered alerts

CREATE TABLE IF NOT EXISTS alert_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Rule reference
    rule_id UUID REFERENCES alert_rules(id),
    rule_name VARCHAR(100) NOT NULL,
    
    -- Alert details
    metric_name VARCHAR(100) NOT NULL,
    metric_value DOUBLE PRECISION NOT NULL,
    threshold DOUBLE PRECISION NOT NULL,
    severity VARCHAR(20) NOT NULL,
    
    -- Status
    status VARCHAR(20) DEFAULT 'firing', -- firing, resolved
    
    -- Timestamps
    triggered_at TIMESTAMPTZ DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,
    
    -- Context
    context JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_alert_history_rule ON alert_history(rule_id);
CREATE INDEX IF NOT EXISTS idx_alert_history_status ON alert_history(status);
CREATE INDEX IF NOT EXISTS idx_alert_history_time ON alert_history(triggered_at DESC);

-- ============================================
-- Insert Default Alert Rules
-- ============================================

INSERT INTO alert_rules (name, description, metric_name, condition, threshold, severity)
VALUES
    ('High Error Rate', 'Error rate exceeds 5%', 'error_rate', 'gt', 0.05, 'critical'),
    ('High Latency', 'P95 latency exceeds 5 seconds', 'p95_latency_ms', 'gt', 5000, 'warning'),
    ('Low Accuracy', 'LLM accuracy drops below 80%', 'llm_accuracy', 'lt', 0.80, 'warning'),
    ('Outbox Backlog', 'Pending outbox events exceed 100', 'outbox_pending', 'gt', 100, 'warning')
ON CONFLICT DO NOTHING;

-- ============================================
-- Grants
-- ============================================

GRANT SELECT, INSERT ON system_metrics TO erpx;
GRANT SELECT, INSERT, UPDATE ON evaluation_runs TO erpx;
GRANT SELECT, INSERT ON evaluation_cases TO erpx;
GRANT SELECT, INSERT ON model_performance_snapshots TO erpx;
GRANT SELECT, INSERT, UPDATE ON alert_rules TO erpx;
GRANT SELECT, INSERT, UPDATE ON alert_history TO erpx;

-- ============================================
-- Comments
-- ============================================

COMMENT ON TABLE system_metrics IS 'PR-12: Time-series metrics storage';
COMMENT ON TABLE evaluation_runs IS 'PR-12: Model/system evaluation runs';
COMMENT ON TABLE evaluation_cases IS 'PR-12: Individual evaluation test cases';
COMMENT ON TABLE model_performance_snapshots IS 'PR-12: Model performance over time';
COMMENT ON TABLE alert_rules IS 'PR-12: Alerting rule definitions';
COMMENT ON TABLE alert_history IS 'PR-12: Alert firing history';

-- ============================================
-- Aggregation View for Metrics
-- ============================================

CREATE OR REPLACE VIEW metrics_summary AS
SELECT 
    metric_name,
    DATE_TRUNC('hour', recorded_at) as hour,
    COUNT(*) as sample_count,
    AVG(value) as avg_value,
    MIN(value) as min_value,
    MAX(value) as max_value,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY value) as p50,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY value) as p95,
    PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY value) as p99
FROM system_metrics
WHERE recorded_at > NOW() - INTERVAL '24 hours'
GROUP BY metric_name, DATE_TRUNC('hour', recorded_at)
ORDER BY hour DESC, metric_name;

GRANT SELECT ON metrics_summary TO erpx;
