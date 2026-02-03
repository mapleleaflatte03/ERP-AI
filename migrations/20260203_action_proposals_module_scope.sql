-- Migration: Add module scope support to agent_action_proposals
-- Date: 2026-02-03
-- Description: Extends agent_action_proposals for per-module chat support

-- Add module column for faster filtering
ALTER TABLE agent_action_proposals 
ADD COLUMN IF NOT EXISTS module VARCHAR(50) DEFAULT 'global';

-- Add scope_id for context linking
ALTER TABLE agent_action_proposals 
ADD COLUMN IF NOT EXISTS scope_id VARCHAR(100);

-- Add risk_level for UI display
ALTER TABLE agent_action_proposals 
ADD COLUMN IF NOT EXISTS risk_level VARCHAR(20) DEFAULT 'medium';

-- Add preview JSONB for rich proposal display
ALTER TABLE agent_action_proposals 
ADD COLUMN IF NOT EXISTS preview JSONB;

-- Add idempotency_key for duplicate prevention
ALTER TABLE agent_action_proposals 
ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(100);

-- Index for module-scoped queries
CREATE INDEX IF NOT EXISTS idx_action_proposals_module 
ON agent_action_proposals(module, status);

-- Index for scope queries
CREATE INDEX IF NOT EXISTS idx_action_proposals_scope 
ON agent_action_proposals(module, scope_id) WHERE scope_id IS NOT NULL;

-- Index for idempotency
CREATE UNIQUE INDEX IF NOT EXISTS idx_action_proposals_idempotency 
ON agent_action_proposals(idempotency_key) 
WHERE idempotency_key IS NOT NULL AND created_at > NOW() - INTERVAL '1 hour';

-- Update existing rows to extract module from action_params
UPDATE agent_action_proposals 
SET module = COALESCE(action_params->>'_module', 'global')
WHERE module = 'global' AND action_params->>'_module' IS NOT NULL;

-- Comment for documentation
COMMENT ON COLUMN agent_action_proposals.module IS 'Module scope: documents, proposals, approvals, analyze, admin, global';
COMMENT ON COLUMN agent_action_proposals.scope_id IS 'Context ID within module: document_id, proposal_id, etc.';
COMMENT ON COLUMN agent_action_proposals.risk_level IS 'Risk level: low, medium, high';
