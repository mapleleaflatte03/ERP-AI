-- Migration 015: Add jobs and query_history tables for PR #34
-- =============================================================

-- Jobs table for document processing jobs
CREATE TABLE IF NOT EXISTS jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID REFERENCES tenants(id),
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    status VARCHAR(50) NOT NULL DEFAULT 'pending', -- pending, processing, completed, failed, approved, rejected
    job_type VARCHAR(50) DEFAULT 'document_processing',
    file_name VARCHAR(255),
    file_path TEXT,
    file_size BIGINT,
    file_type VARCHAR(50),
    result JSONB DEFAULT '{}',
    error TEXT,
    processing_time_ms INTEGER,
    created_by UUID REFERENCES users(id),
    approved_by UUID REFERENCES users(id),
    approved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_jobs_tenant ON jobs(tenant_id);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_document ON jobs(document_id);
CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at DESC);

-- Query history for NL2SQL analyst feature
CREATE TABLE IF NOT EXISTS query_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID REFERENCES tenants(id),
    user_id UUID REFERENCES users(id),
    query_text TEXT NOT NULL,
    sql_generated TEXT,
    result JSONB,
    is_favorite BOOLEAN DEFAULT false,
    execution_time_ms INTEGER,
    row_count INTEGER,
    error TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_query_history_tenant ON query_history(tenant_id);
CREATE INDEX IF NOT EXISTS idx_query_history_user ON query_history(user_id);
CREATE INDEX IF NOT EXISTS idx_query_history_favorite ON query_history(is_favorite);
CREATE INDEX IF NOT EXISTS idx_query_history_created_at ON query_history(created_at DESC);
