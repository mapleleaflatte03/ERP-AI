-- PR-9: Policy & Guardrails
-- ================================
-- Policy rules engine for journal proposal validation
-- Supports: threshold checks, vendor allowlist, balanced journals, tax sanity

-- Policy rules table
CREATE TABLE IF NOT EXISTS policy_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id),
    name VARCHAR(100) NOT NULL,
    rule_type VARCHAR(50) NOT NULL, -- threshold, vendor_allowlist, balanced, tax_sanity, entry_count
    is_active BOOLEAN DEFAULT TRUE,
    priority INTEGER DEFAULT 100, -- lower = higher priority
    config JSONB NOT NULL DEFAULT '{}',
    -- threshold: {"max_amount": 100000000, "currency": "VND"}
    -- vendor_allowlist: {"vendors": ["vendor1", "vendor2"], "mode": "allow|deny"}
    -- balanced: {"tolerance": 0.01}
    -- tax_sanity: {"min_rate": 0.08, "max_rate": 0.12}
    -- entry_count: {"min": 2, "max": 20}
    action_on_fail VARCHAR(20) DEFAULT 'require_review', -- auto_reject, require_review, warn_only
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by VARCHAR(100)
);

-- Create unique constraint on tenant + name
CREATE UNIQUE INDEX IF NOT EXISTS idx_policy_rules_tenant_name 
ON policy_rules(tenant_id, name) WHERE tenant_id IS NOT NULL;

-- Policy evaluation results
CREATE TABLE IF NOT EXISTS policy_evaluations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id VARCHAR(100) NOT NULL,
    proposal_id UUID REFERENCES journal_proposals(id),
    tenant_id UUID REFERENCES tenants(id),
    evaluated_at TIMESTAMPTZ DEFAULT NOW(),
    overall_result VARCHAR(20) NOT NULL, -- approved, rejected, requires_review
    rules_passed INTEGER DEFAULT 0,
    rules_failed INTEGER DEFAULT 0,
    rules_warned INTEGER DEFAULT 0,
    details JSONB NOT NULL DEFAULT '[]',
    -- [{"rule": "threshold", "result": "pass|fail|warn", "message": "..."}]
    auto_approved BOOLEAN DEFAULT FALSE,
    request_id VARCHAR(100)
);

CREATE INDEX IF NOT EXISTS idx_policy_eval_job_id ON policy_evaluations(job_id);
CREATE INDEX IF NOT EXISTS idx_policy_eval_proposal ON policy_evaluations(proposal_id);
CREATE INDEX IF NOT EXISTS idx_policy_eval_result ON policy_evaluations(overall_result);

-- Insert default policy rules (system-wide, tenant_id NULL)
INSERT INTO policy_rules (tenant_id, name, rule_type, priority, config, action_on_fail)
VALUES 
    -- Threshold: Auto-approve under 10M VND
    (NULL, 'auto_approve_threshold', 'threshold', 10, 
     '{"max_amount": 10000000, "currency": "VND"}', 'require_review'),
    
    -- Balanced journal check
    (NULL, 'balanced_journal', 'balanced', 20,
     '{"tolerance": 0.01}', 'auto_reject'),
    
    -- Entry count sanity
    (NULL, 'entry_count_limit', 'entry_count', 30,
     '{"min": 2, "max": 20}', 'require_review'),
    
    -- Tax rate sanity (8-12% VAT)
    (NULL, 'tax_sanity', 'tax_sanity', 40,
     '{"min_rate": 0.08, "max_rate": 0.12}', 'warn_only')
ON CONFLICT DO NOTHING;

-- Grant permissions
GRANT SELECT, INSERT, UPDATE ON policy_rules TO erpx;
GRANT SELECT, INSERT ON policy_evaluations TO erpx;

COMMENT ON TABLE policy_rules IS 'PR-9: Policy engine rules for journal validation';
COMMENT ON TABLE policy_evaluations IS 'PR-9: Policy evaluation audit trail';
