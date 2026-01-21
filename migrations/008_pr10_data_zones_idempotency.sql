-- PR-10: Data Zones + Idempotency
-- ================================
-- Data lineage tracking through processing zones
-- Idempotent job processing with deduplication

-- ============================================
-- Data Zones Tracking Table
-- ============================================
-- Tracks data movement through zones:
-- RAW -> EXTRACTED -> PROPOSED -> POSTED

CREATE TABLE IF NOT EXISTS data_zones (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id VARCHAR(100) NOT NULL,
    tenant_id UUID REFERENCES tenants(id),
    document_id UUID REFERENCES documents(id),
    
    -- Zone tracking
    zone VARCHAR(20) NOT NULL, -- raw, extracted, proposed, posted
    status VARCHAR(20) DEFAULT 'active', -- active, superseded, archived
    
    -- Content references
    raw_file_uri TEXT,
    extracted_text_preview TEXT,
    proposal_id UUID REFERENCES journal_proposals(id),
    ledger_entry_id UUID REFERENCES ledger_entries(id),
    
    -- Metadata
    checksum VARCHAR(64), -- SHA256 of content
    byte_count INTEGER,
    processing_time_ms INTEGER,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    zone_entered_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Request tracking
    request_id VARCHAR(100)
);

CREATE INDEX IF NOT EXISTS idx_data_zones_job ON data_zones(job_id);
CREATE INDEX IF NOT EXISTS idx_data_zones_zone ON data_zones(zone);
CREATE INDEX IF NOT EXISTS idx_data_zones_document ON data_zones(document_id);
CREATE INDEX IF NOT EXISTS idx_data_zones_checksum ON data_zones(checksum);

-- ============================================
-- Idempotency Keys Table
-- ============================================
-- Prevents duplicate job processing

CREATE TABLE IF NOT EXISTS idempotency_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Key components
    idempotency_key VARCHAR(255) NOT NULL UNIQUE,
    tenant_id UUID REFERENCES tenants(id),
    
    -- Request info
    operation VARCHAR(50) NOT NULL, -- upload, process, approve, post
    job_id VARCHAR(100),
    
    -- Response caching
    status VARCHAR(20) DEFAULT 'processing', -- processing, completed, failed
    response_code INTEGER,
    response_body JSONB,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ DEFAULT NOW() + INTERVAL '24 hours',
    completed_at TIMESTAMPTZ,
    
    -- Metadata
    request_hash VARCHAR(64), -- Hash of request body for validation
    request_id VARCHAR(100)
);

CREATE INDEX IF NOT EXISTS idx_idempotency_key ON idempotency_keys(idempotency_key);
CREATE INDEX IF NOT EXISTS idx_idempotency_tenant ON idempotency_keys(tenant_id);
CREATE INDEX IF NOT EXISTS idx_idempotency_job ON idempotency_keys(job_id);
CREATE INDEX IF NOT EXISTS idx_idempotency_expires ON idempotency_keys(expires_at);

-- ============================================
-- Document Checksums for Deduplication
-- ============================================
-- Prevents processing same document twice

CREATE TABLE IF NOT EXISTS document_checksums (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id),
    
    -- Checksum info
    file_checksum VARCHAR(64) NOT NULL, -- SHA256 of file content
    file_size INTEGER NOT NULL,
    filename VARCHAR(255),
    content_type VARCHAR(100),
    
    -- Reference to original job
    first_job_id VARCHAR(100) NOT NULL,
    document_id UUID REFERENCES documents(id),
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Stats
    duplicate_count INTEGER DEFAULT 0,
    
    CONSTRAINT uk_checksum_tenant UNIQUE(file_checksum, tenant_id)
);

CREATE INDEX IF NOT EXISTS idx_doc_checksum ON document_checksums(file_checksum);
CREATE INDEX IF NOT EXISTS idx_doc_checksum_tenant ON document_checksums(tenant_id, file_checksum);

-- ============================================
-- Processing State Table
-- ============================================
-- Track job processing state for idempotent resume

CREATE TABLE IF NOT EXISTS job_processing_state (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id VARCHAR(100) NOT NULL UNIQUE,
    tenant_id UUID REFERENCES tenants(id),
    
    -- State tracking
    current_state VARCHAR(30) NOT NULL, -- uploaded, extracting, extracted, proposing, proposed, approving, posting, completed, failed
    previous_state VARCHAR(30),
    
    -- Checkpoint data for resume
    checkpoint_data JSONB DEFAULT '{}',
    
    -- Processing info
    attempts INTEGER DEFAULT 0,
    max_attempts INTEGER DEFAULT 3,
    last_error TEXT,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    state_changed_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Request tracking
    request_id VARCHAR(100)
);

CREATE INDEX IF NOT EXISTS idx_job_state ON job_processing_state(current_state);
CREATE INDEX IF NOT EXISTS idx_job_state_job ON job_processing_state(job_id);

-- ============================================
-- Grants
-- ============================================

GRANT SELECT, INSERT, UPDATE ON data_zones TO erpx;
GRANT SELECT, INSERT, UPDATE ON idempotency_keys TO erpx;
GRANT SELECT, INSERT, UPDATE ON document_checksums TO erpx;
GRANT SELECT, INSERT, UPDATE ON job_processing_state TO erpx;

-- ============================================
-- Comments
-- ============================================

COMMENT ON TABLE data_zones IS 'PR-10: Track data lineage through RAW->EXTRACTED->PROPOSED->POSTED zones';
COMMENT ON TABLE idempotency_keys IS 'PR-10: Idempotency key store for request deduplication';
COMMENT ON TABLE document_checksums IS 'PR-10: Document content checksums for deduplication';
COMMENT ON TABLE job_processing_state IS 'PR-10: Job processing state for idempotent resume';

-- ============================================
-- Auto-cleanup function for expired keys
-- ============================================

CREATE OR REPLACE FUNCTION cleanup_expired_idempotency_keys()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM idempotency_keys WHERE expires_at < NOW();
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION cleanup_expired_idempotency_keys IS 'PR-10: Cleanup expired idempotency keys';
