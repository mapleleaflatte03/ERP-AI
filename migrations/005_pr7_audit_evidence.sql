-- PR-7: Audit & Evidence Store
-- =====================================================
-- Creates audit_evidence table for complete traceability

-- Enable uuid extension if not already
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =====================================================
-- AUDIT_EVIDENCE TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS audit_evidence (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id UUID NOT NULL,
    tenant_id TEXT NOT NULL,
    request_id TEXT,
    document_id UUID,
    
    -- File references
    raw_file_uri TEXT,                    -- minio path to original file
    extracted_text_preview TEXT,          -- truncated extracted text (max 4KB)
    extracted_text_uri TEXT,              -- minio path to full extracted text
    
    -- LLM provenance
    prompt_version TEXT DEFAULT 'v1',
    model_name TEXT,
    llm_stage TEXT,                       -- direct/extract/repair/self_fix
    llm_input_preview TEXT,               -- truncated prompt (max 2KB)
    llm_output_json JSONB,                -- parsed JSON output
    llm_output_raw TEXT,                  -- raw LLM response (max 8KB)
    llm_latency_ms INTEGER,
    
    -- Validation & decision
    validation_errors JSONB DEFAULT '[]'::jsonb,
    risk_flags JSONB DEFAULT '[]'::jsonb,
    decision TEXT DEFAULT 'proposed',     -- proposed/needs_approval/approved/rejected/posted
    decision_reason TEXT,
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_audit_evidence_job_id ON audit_evidence(job_id);
CREATE INDEX IF NOT EXISTS idx_audit_evidence_tenant_id ON audit_evidence(tenant_id);
CREATE INDEX IF NOT EXISTS idx_audit_evidence_request_id ON audit_evidence(request_id);
CREATE INDEX IF NOT EXISTS idx_audit_evidence_decision ON audit_evidence(decision);
CREATE INDEX IF NOT EXISTS idx_audit_evidence_created_at ON audit_evidence(created_at);

-- =====================================================
-- AUDIT_EVENTS TABLE (timeline/append-only events)
-- =====================================================
CREATE TABLE IF NOT EXISTS audit_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id UUID NOT NULL,
    tenant_id TEXT NOT NULL,
    request_id TEXT,
    
    event_type TEXT NOT NULL,             -- upload/ocr_complete/llm_complete/validate/approve/reject/post
    event_data JSONB DEFAULT '{}'::jsonb,
    actor TEXT,                           -- system/user/auto-approver
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_events_job_id ON audit_events(job_id);
CREATE INDEX IF NOT EXISTS idx_audit_events_tenant_id ON audit_events(tenant_id);
CREATE INDEX IF NOT EXISTS idx_audit_events_event_type ON audit_events(event_type);
CREATE INDEX IF NOT EXISTS idx_audit_events_created_at ON audit_events(created_at);

-- Trigger to update updated_at
CREATE OR REPLACE FUNCTION update_audit_evidence_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS trigger_audit_evidence_updated_at ON audit_evidence;
CREATE TRIGGER trigger_audit_evidence_updated_at
    BEFORE UPDATE ON audit_evidence
    FOR EACH ROW
    EXECUTE FUNCTION update_audit_evidence_updated_at();

-- Grant permissions
GRANT ALL PRIVILEGES ON audit_evidence TO erpx;
GRANT ALL PRIVILEGES ON audit_events TO erpx;
