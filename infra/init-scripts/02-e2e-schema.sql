-- ==============================================================================
-- ERPX E2E Schema Extension
-- Adds: Outbox, Audit, Approval, Ledger tables for E2E architecture
-- ==============================================================================

-- Create extensions if not exist
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ==============================================================================
-- E2E INVOICES (RAW/Staging Zone)
-- ==============================================================================

CREATE TABLE IF NOT EXISTS e2e_invoices (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(100) NOT NULL,
    
    -- File info (RAW/Staging Zone)
    file_name VARCHAR(500) NOT NULL,
    file_path VARCHAR(1000) NOT NULL,
    file_type VARCHAR(50),
    file_size BIGINT,
    
    -- Processing status
    status VARCHAR(50) DEFAULT 'UPLOADED',
    
    -- OCR output path
    ocr_json_path VARCHAR(1000),
    
    -- Extracted data (from OCR)
    invoice_number VARCHAR(100),
    invoice_date TIMESTAMP,
    seller_name VARCHAR(500),
    seller_tax_code VARCHAR(50),
    buyer_name VARCHAR(500),
    buyer_tax_code VARCHAR(50),
    total_amount DECIMAL(18,2),
    vat_amount DECIMAL(18,2),
    currency VARCHAR(10) DEFAULT 'VND',
    
    -- Tracing
    trace_id VARCHAR(100),
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_e2e_inv_tenant_status ON e2e_invoices(tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_e2e_inv_trace ON e2e_invoices(trace_id);
CREATE INDEX IF NOT EXISTS idx_e2e_inv_created ON e2e_invoices(created_at);

-- ==============================================================================
-- E2E PROPOSALS (Proposal Zone)
-- ==============================================================================

CREATE TABLE IF NOT EXISTS e2e_proposals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    invoice_id UUID NOT NULL REFERENCES e2e_invoices(id),
    tenant_id VARCHAR(100) NOT NULL,
    
    -- Proposal content (Proposal Zone)
    suggested_entries JSONB,
    evidence JSONB,
    ai_explanation TEXT,
    
    -- Model versioning (MLflow tracking placeholder)
    llm_model_name VARCHAR(200),
    llm_model_version VARCHAR(100),
    embedding_model_name VARCHAR(200),
    embedding_dim INTEGER,
    prompt_version VARCHAR(100),
    
    -- Confidence
    confidence_score DECIMAL(5,4),
    
    -- Status
    status VARCHAR(50) DEFAULT 'PENDING',
    
    -- Approval info
    approved_by VARCHAR(200),
    approved_at TIMESTAMP,
    rejection_reason TEXT,
    
    -- Artifact path
    artifact_json_path VARCHAR(1000),
    
    -- Tracing
    trace_id VARCHAR(100),
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_e2e_prop_invoice ON e2e_proposals(invoice_id);
CREATE INDEX IF NOT EXISTS idx_e2e_prop_tenant_status ON e2e_proposals(tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_e2e_prop_trace ON e2e_proposals(trace_id);

-- ==============================================================================
-- E2E LEDGER ENTRIES (Ledger Zone / ERP Official DB)
-- ==============================================================================

CREATE TABLE IF NOT EXISTS e2e_ledger_entries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    proposal_id UUID NOT NULL REFERENCES e2e_proposals(id),
    tenant_id VARCHAR(100) NOT NULL,
    
    -- Entry details (Ledger Zone)
    entry_type VARCHAR(20) NOT NULL, -- DEBIT or CREDIT
    account_code VARCHAR(20) NOT NULL,
    account_name VARCHAR(200),
    amount DECIMAL(18,2) NOT NULL,
    currency VARCHAR(10) DEFAULT 'VND',
    description TEXT,
    
    -- Journal info
    journal_number VARCHAR(100),
    posting_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Approval tracking
    approved_by VARCHAR(200) NOT NULL,
    approved_at TIMESTAMP NOT NULL,
    source_proposal_id UUID,
    
    -- Tracing
    trace_id VARCHAR(100),
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_e2e_ledger_proposal ON e2e_ledger_entries(proposal_id);
CREATE INDEX IF NOT EXISTS idx_e2e_ledger_tenant_date ON e2e_ledger_entries(tenant_id, posting_date);
CREATE INDEX IF NOT EXISTS idx_e2e_ledger_account ON e2e_ledger_entries(account_code);
CREATE INDEX IF NOT EXISTS idx_e2e_ledger_journal ON e2e_ledger_entries(journal_number);

-- ==============================================================================
-- E2E OUTBOX EVENTS (Event Bus / Outbox Pattern)
-- ==============================================================================

CREATE TABLE IF NOT EXISTS e2e_outbox_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Event info
    event_type VARCHAR(100) NOT NULL,
    aggregate_type VARCHAR(100),
    aggregate_id VARCHAR(100),
    
    -- Payload
    payload JSONB NOT NULL,
    
    -- Processing status
    status VARCHAR(50) DEFAULT 'PENDING',
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    error_message TEXT,
    
    -- Tenant
    tenant_id VARCHAR(100),
    
    -- Tracing
    trace_id VARCHAR(100),
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_e2e_outbox_status_created ON e2e_outbox_events(status, created_at);
CREATE INDEX IF NOT EXISTS idx_e2e_outbox_type ON e2e_outbox_events(event_type);
CREATE INDEX IF NOT EXISTS idx_e2e_outbox_aggregate ON e2e_outbox_events(aggregate_type, aggregate_id);

-- ==============================================================================
-- E2E AUDIT EVENTS (Audit & Evidence Store)
-- ==============================================================================

CREATE TABLE IF NOT EXISTS e2e_audit_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- What happened
    action VARCHAR(100) NOT NULL,
    entity_type VARCHAR(100),
    entity_id VARCHAR(100),
    
    -- Who
    actor VARCHAR(200),
    tenant_id VARCHAR(100),
    
    -- Details
    old_state JSONB,
    new_state JSONB,
    details JSONB,
    
    -- Evidence
    evidence JSONB,
    
    -- Versioning
    model_version VARCHAR(100),
    prompt_version VARCHAR(100),
    
    -- Tracing
    trace_id VARCHAR(100),
    request_id VARCHAR(100),
    
    -- Error info
    error_message TEXT,
    error_traceback TEXT,
    
    -- Foreign key
    invoice_id UUID REFERENCES e2e_invoices(id),
    
    -- Timestamp
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_e2e_audit_entity ON e2e_audit_events(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_e2e_audit_trace ON e2e_audit_events(trace_id);
CREATE INDEX IF NOT EXISTS idx_e2e_audit_tenant_time ON e2e_audit_events(tenant_id, created_at);
CREATE INDEX IF NOT EXISTS idx_e2e_audit_action ON e2e_audit_events(action);
CREATE INDEX IF NOT EXISTS idx_e2e_audit_invoice ON e2e_audit_events(invoice_id);

-- ==============================================================================
-- E2E TENANT API KEYS (RBAC/Quota)
-- ==============================================================================

CREATE TABLE IF NOT EXISTS e2e_tenant_api_keys (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(100) NOT NULL,
    api_key_hash VARCHAR(256) NOT NULL UNIQUE,
    name VARCHAR(200),
    
    -- Quota
    daily_quota INTEGER DEFAULT 1000,
    requests_today INTEGER DEFAULT 0,
    quota_reset_at TIMESTAMP,
    
    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_e2e_apikey_tenant ON e2e_tenant_api_keys(tenant_id);
CREATE INDEX IF NOT EXISTS idx_e2e_apikey_hash ON e2e_tenant_api_keys(api_key_hash);

-- ==============================================================================
-- INSERT DEFAULT TENANT & API KEY (for dev/demo)
-- API Key: erp-demo-key-2024 (SHA256 hashed)
-- ==============================================================================

INSERT INTO e2e_tenant_api_keys (tenant_id, api_key_hash, name, daily_quota, is_active)
VALUES (
    'demo-tenant',
    'a8b5d0f7c3e2a1b4d6f8e0c2a4b6d8e0f2a4c6e8b0d2f4a6c8e0b2d4f6a8c0e2',  -- SHA256 of 'erp-demo-key-2024'
    'Demo API Key',
    10000,
    TRUE
)
ON CONFLICT (api_key_hash) DO NOTHING;

-- ==============================================================================
-- GRANT PERMISSIONS
-- ==============================================================================

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO erp_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO erp_user;

-- ==============================================================================
-- LOG INITIALIZATION
-- ==============================================================================

DO $$
BEGIN
    RAISE NOTICE 'ERPX E2E Schema initialized successfully at %', NOW();
END $$;
