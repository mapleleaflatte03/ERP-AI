-- PR13.5: Seed vendor_allowlist policy rule
-- ================================
-- Adds vendor_allowlist rule for system-wide (tenant_id NULL)
-- Idempotent: Uses unique index + ON CONFLICT for rerun safety

-- First, create unique constraint for NULL tenant_id rules (complement existing)
-- Existing: idx_policy_rules_tenant_name WHERE tenant_id IS NOT NULL
-- New: idx_policy_rules_null_tenant_name WHERE tenant_id IS NULL
CREATE UNIQUE INDEX IF NOT EXISTS idx_policy_rules_null_tenant_name 
ON policy_rules(name) WHERE tenant_id IS NULL;

-- Seed vendor_allowlist rule
-- Config schema: {"allowed_vendors": [...], "check_tax_id": boolean}
INSERT INTO policy_rules (tenant_id, name, rule_type, priority, config, action_on_fail, is_active)
VALUES (
    NULL,
    'vendor_allowlist',
    'vendor_allowlist',
    50,
    '{"allowed_vendors": ["Cong ty ABC", "Công ty TNHH XYZ", "Acme Corp"], "check_tax_id": true}'::jsonb,
    'require_review',
    true
)
ON CONFLICT (name) WHERE tenant_id IS NULL DO NOTHING;

COMMENT ON INDEX idx_policy_rules_null_tenant_name IS 'PR13.5: Unique constraint for system-wide rules (tenant_id IS NULL)';
