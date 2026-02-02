-- Agent Action Proposals Table
-- Stores Copilot action plans that require user confirmation
-- Implements Plan → Confirm → Execute pattern

CREATE TABLE IF NOT EXISTS agent_action_proposals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Context
    tenant_id UUID REFERENCES tenants(id),
    session_id VARCHAR(100) NOT NULL,  -- Chat session ID
    
    -- Action details
    action_type VARCHAR(50) NOT NULL,  -- 'approve_proposal', 'reject_proposal', 'create_entry', etc.
    target_entity VARCHAR(50),          -- 'approval', 'document', 'ledger', etc.
    target_id UUID,                     -- ID of the target entity
    
    -- Payload
    action_params JSONB NOT NULL DEFAULT '{}',  -- Parameters for the action
    description TEXT,                            -- Human-readable description
    reasoning TEXT,                              -- AI's reasoning for this action
    
    -- Status workflow: proposed → confirmed → executed / cancelled
    status VARCHAR(20) NOT NULL DEFAULT 'proposed',
    
    -- Result tracking
    executed_at TIMESTAMP WITH TIME ZONE,
    result JSONB,                        -- Execution result
    error_message TEXT,
    
    -- Audit
    proposed_by VARCHAR(100) DEFAULT 'copilot',
    confirmed_by UUID REFERENCES users(id),
    confirmed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT valid_status CHECK (status IN ('proposed', 'confirmed', 'executed', 'cancelled', 'failed'))
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_action_proposals_session ON agent_action_proposals(session_id);
CREATE INDEX IF NOT EXISTS idx_action_proposals_status ON agent_action_proposals(status);
CREATE INDEX IF NOT EXISTS idx_action_proposals_target ON agent_action_proposals(target_entity, target_id);
CREATE INDEX IF NOT EXISTS idx_action_proposals_created ON agent_action_proposals(created_at DESC);

-- Update trigger
CREATE OR REPLACE FUNCTION update_action_proposals_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS update_action_proposals_updated_at ON agent_action_proposals;
CREATE TRIGGER update_action_proposals_updated_at
    BEFORE UPDATE ON agent_action_proposals
    FOR EACH ROW
    EXECUTE FUNCTION update_action_proposals_timestamp();

-- Comment
COMMENT ON TABLE agent_action_proposals IS 'Stores Copilot action proposals for user confirmation (Plan → Confirm → Execute pattern)';
