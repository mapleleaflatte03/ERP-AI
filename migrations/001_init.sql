-- ERPX AI Accounting - PostgreSQL Schema
-- ======================================
-- Database schema for accounting system

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ===========================================================================
-- Tenants
-- ===========================================================================

CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    code VARCHAR(50) UNIQUE NOT NULL,
    settings JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_tenants_code ON tenants(code);

-- ===========================================================================
-- Users
-- ===========================================================================

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID REFERENCES tenants(id),
    keycloak_id VARCHAR(255) UNIQUE,
    telegram_id BIGINT UNIQUE,
    email VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    role VARCHAR(50) DEFAULT 'viewer', -- admin, manager, accountant, auditor, viewer
    approval_limit DECIMAL(18,2) DEFAULT 0,
    settings JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_users_tenant ON users(tenant_id);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_telegram ON users(telegram_id);

-- ===========================================================================
-- Documents
-- ===========================================================================

CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID REFERENCES tenants(id) NOT NULL,
    job_id VARCHAR(255) UNIQUE NOT NULL,
    
    -- File info
    filename VARCHAR(500),
    content_type VARCHAR(100),
    file_size BIGINT,
    file_path VARCHAR(1000),
    minio_bucket VARCHAR(255),
    minio_key VARCHAR(500),
    checksum VARCHAR(64),
    
    -- Processing status
    status VARCHAR(50) DEFAULT 'pending', -- pending, processing, completed, failed, approved, rejected
    
    -- Extracted data
    raw_text TEXT,
    doc_type VARCHAR(50),
    doc_type_confidence DECIMAL(5,4),
    extracted_data JSONB,
    
    -- Proposal
    proposal JSONB,
    
    -- Validation
    validation_result JSONB,
    
    -- Processing metadata
    llm_provider VARCHAR(50),
    llm_model VARCHAR(100),
    llm_tokens_used INTEGER,
    processing_time_ms INTEGER,
    
    -- Error tracking
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    
    -- Audit
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_documents_tenant ON documents(tenant_id);
CREATE INDEX idx_documents_job ON documents(job_id);
CREATE INDEX idx_documents_status ON documents(status);
CREATE INDEX idx_documents_created ON documents(created_at DESC);
CREATE INDEX idx_documents_doc_type ON documents(doc_type);

-- ===========================================================================
-- Journal Entries
-- ===========================================================================

CREATE TABLE journal_entries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID REFERENCES tenants(id) NOT NULL,
    document_id UUID REFERENCES documents(id),
    
    -- Entry info
    entry_no VARCHAR(50),
    entry_date DATE NOT NULL,
    period VARCHAR(7), -- YYYY-MM
    fiscal_year INTEGER,
    
    -- Source document info
    vendor VARCHAR(255),
    invoice_no VARCHAR(100),
    invoice_date DATE,
    
    -- Amounts
    total_amount DECIMAL(18,2),
    vat_amount DECIMAL(18,2),
    currency VARCHAR(3) DEFAULT 'VND',
    
    -- Description
    description TEXT,
    notes TEXT,
    
    -- Status
    status VARCHAR(50) DEFAULT 'draft', -- draft, pending_approval, approved, posted, voided
    
    -- AI metadata
    ai_confidence DECIMAL(5,4),
    ai_explanation TEXT,
    needs_review BOOLEAN DEFAULT false,
    
    -- Approval
    approved_by UUID REFERENCES users(id),
    approved_at TIMESTAMPTZ,
    approval_notes TEXT,
    
    -- Posting
    posted_by UUID REFERENCES users(id),
    posted_at TIMESTAMPTZ,
    
    -- Audit
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_journal_tenant ON journal_entries(tenant_id);
CREATE INDEX idx_journal_document ON journal_entries(document_id);
CREATE INDEX idx_journal_date ON journal_entries(entry_date);
CREATE INDEX idx_journal_period ON journal_entries(period);
CREATE INDEX idx_journal_status ON journal_entries(status);

-- ===========================================================================
-- Journal Lines (Debit/Credit entries)
-- ===========================================================================

CREATE TABLE journal_lines (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    journal_entry_id UUID REFERENCES journal_entries(id) ON DELETE CASCADE,
    
    -- Account
    account_code VARCHAR(20) NOT NULL,
    account_name VARCHAR(255),
    
    -- Amounts
    debit DECIMAL(18,2) DEFAULT 0,
    credit DECIMAL(18,2) DEFAULT 0,
    
    -- Description
    description TEXT,
    
    -- Line order
    line_no INTEGER,
    
    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_journal_lines_entry ON journal_lines(journal_entry_id);
CREATE INDEX idx_journal_lines_account ON journal_lines(account_code);

-- ===========================================================================
-- Chart of Accounts
-- ===========================================================================

CREATE TABLE accounts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID REFERENCES tenants(id) NOT NULL,
    
    -- Account info (TT200)
    code VARCHAR(20) NOT NULL,
    name VARCHAR(255) NOT NULL,
    name_en VARCHAR(255),
    
    -- Classification
    account_type VARCHAR(50), -- asset, liability, equity, revenue, expense
    account_group VARCHAR(50), -- current_asset, fixed_asset, etc.
    parent_code VARCHAR(20),
    level INTEGER DEFAULT 1,
    
    -- Settings
    is_active BOOLEAN DEFAULT true,
    allow_posting BOOLEAN DEFAULT true,
    currency VARCHAR(3) DEFAULT 'VND',
    
    -- Description
    description TEXT,
    
    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(tenant_id, code)
);

CREATE INDEX idx_accounts_tenant ON accounts(tenant_id);
CREATE INDEX idx_accounts_code ON accounts(code);
CREATE INDEX idx_accounts_type ON accounts(account_type);

-- ===========================================================================
-- Audit Trail
-- ===========================================================================

CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID REFERENCES tenants(id),
    user_id UUID REFERENCES users(id),
    
    -- Action
    action VARCHAR(100) NOT NULL, -- create, update, delete, approve, reject, etc.
    entity_type VARCHAR(100) NOT NULL, -- document, journal_entry, etc.
    entity_id UUID,
    
    -- Details
    old_values JSONB,
    new_values JSONB,
    metadata JSONB,
    
    -- Request info
    ip_address INET,
    user_agent TEXT,
    request_id VARCHAR(255),
    trace_id VARCHAR(255),
    
    -- Timestamp
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_audit_tenant ON audit_logs(tenant_id);
CREATE INDEX idx_audit_user ON audit_logs(user_id);
CREATE INDEX idx_audit_entity ON audit_logs(entity_type, entity_id);
CREATE INDEX idx_audit_created ON audit_logs(created_at DESC);

-- ===========================================================================
-- Knowledge Base (for RAG)
-- ===========================================================================

CREATE TABLE knowledge_documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Document info
    title VARCHAR(500) NOT NULL,
    source VARCHAR(255), -- TT200, VAS, SOP, etc.
    category VARCHAR(100),
    
    -- Content
    content TEXT NOT NULL,
    content_vector vector(1536), -- For embeddings
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    
    -- Status
    is_active BOOLEAN DEFAULT true,
    
    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_knowledge_source ON knowledge_documents(source);
CREATE INDEX idx_knowledge_category ON knowledge_documents(category);

-- ===========================================================================
-- Workflow State (for Temporal tracking)
-- ===========================================================================

CREATE TABLE workflow_state (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workflow_id VARCHAR(255) UNIQUE NOT NULL,
    workflow_type VARCHAR(100), -- document_processing, approval
    
    -- State
    job_id VARCHAR(255),
    tenant_id UUID REFERENCES tenants(id),
    status VARCHAR(50),
    
    -- Temporal info
    temporal_run_id VARCHAR(255),
    task_queue VARCHAR(100),
    
    -- Timing
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    
    -- Result
    result JSONB,
    error TEXT,
    
    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_workflow_job ON workflow_state(job_id);
CREATE INDEX idx_workflow_status ON workflow_state(status);

-- ===========================================================================
-- LLM Call Logs
-- ===========================================================================

CREATE TABLE llm_call_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Request
    request_id VARCHAR(255),
    trace_id VARCHAR(255),
    job_id VARCHAR(255),
    
    -- Provider
    provider VARCHAR(50) NOT NULL, -- do_agent
    model VARCHAR(100) NOT NULL,
    endpoint VARCHAR(500),
    
    -- Request details
    prompt_text TEXT,
    prompt_tokens INTEGER,
    system_prompt TEXT,
    temperature DECIMAL(3,2),
    max_tokens INTEGER,
    
    -- Response
    response_text TEXT,
    response_tokens INTEGER,
    total_tokens INTEGER,
    
    -- Timing
    latency_ms INTEGER,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    
    -- Status
    status VARCHAR(50), -- success, error, timeout
    error_message TEXT,
    
    -- Metadata
    metadata JSONB,
    
    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_llm_logs_request ON llm_call_logs(request_id);
CREATE INDEX idx_llm_logs_job ON llm_call_logs(job_id);
CREATE INDEX idx_llm_logs_provider ON llm_call_logs(provider, model);
CREATE INDEX idx_llm_logs_created ON llm_call_logs(created_at DESC);

-- ===========================================================================
-- Functions & Triggers
-- ===========================================================================

-- Updated at trigger
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply to tables
CREATE TRIGGER update_tenants_updated_at
    BEFORE UPDATE ON tenants
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_documents_updated_at
    BEFORE UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_journal_entries_updated_at
    BEFORE UPDATE ON journal_entries
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_accounts_updated_at
    BEFORE UPDATE ON accounts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_workflow_state_updated_at
    BEFORE UPDATE ON workflow_state
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ===========================================================================
-- Seed Data: Default Tenant
-- ===========================================================================

INSERT INTO tenants (id, name, code) VALUES 
    ('00000000-0000-0000-0000-000000000001', 'Default Tenant', 'default')
ON CONFLICT (code) DO NOTHING;

-- ===========================================================================
-- Seed Data: TT200 Chart of Accounts (Simplified)
-- ===========================================================================

INSERT INTO accounts (tenant_id, code, name, account_type, account_group, level) VALUES
    -- Assets (Tài sản)
    ('00000000-0000-0000-0000-000000000001', '111', 'Tiền mặt', 'asset', 'current_asset', 1),
    ('00000000-0000-0000-0000-000000000001', '1111', 'Tiền Việt Nam', 'asset', 'current_asset', 2),
    ('00000000-0000-0000-0000-000000000001', '112', 'Tiền gửi ngân hàng', 'asset', 'current_asset', 1),
    ('00000000-0000-0000-0000-000000000001', '1121', 'Tiền Việt Nam', 'asset', 'current_asset', 2),
    ('00000000-0000-0000-0000-000000000001', '131', 'Phải thu của khách hàng', 'asset', 'current_asset', 1),
    ('00000000-0000-0000-0000-000000000001', '133', 'Thuế GTGT được khấu trừ', 'asset', 'current_asset', 1),
    ('00000000-0000-0000-0000-000000000001', '1331', 'Thuế GTGT được khấu trừ của hàng hóa, dịch vụ', 'asset', 'current_asset', 2),
    ('00000000-0000-0000-0000-000000000001', '152', 'Nguyên liệu, vật liệu', 'asset', 'current_asset', 1),
    ('00000000-0000-0000-0000-000000000001', '153', 'Công cụ, dụng cụ', 'asset', 'current_asset', 1),
    ('00000000-0000-0000-0000-000000000001', '156', 'Hàng hóa', 'asset', 'current_asset', 1),
    ('00000000-0000-0000-0000-000000000001', '211', 'Tài sản cố định hữu hình', 'asset', 'fixed_asset', 1),
    ('00000000-0000-0000-0000-000000000001', '214', 'Hao mòn TSCĐ', 'asset', 'fixed_asset', 1),
    
    -- Liabilities (Nợ phải trả)
    ('00000000-0000-0000-0000-000000000001', '331', 'Phải trả cho người bán', 'liability', 'current_liability', 1),
    ('00000000-0000-0000-0000-000000000001', '333', 'Thuế và các khoản phải nộp Nhà nước', 'liability', 'current_liability', 1),
    ('00000000-0000-0000-0000-000000000001', '3331', 'Thuế GTGT phải nộp', 'liability', 'current_liability', 2),
    ('00000000-0000-0000-0000-000000000001', '33311', 'Thuế GTGT đầu ra', 'liability', 'current_liability', 3),
    ('00000000-0000-0000-0000-000000000001', '334', 'Phải trả người lao động', 'liability', 'current_liability', 1),
    ('00000000-0000-0000-0000-000000000001', '341', 'Vay và nợ thuê tài chính', 'liability', 'long_term_liability', 1),
    
    -- Equity (Vốn chủ sở hữu)
    ('00000000-0000-0000-0000-000000000001', '411', 'Vốn đầu tư của chủ sở hữu', 'equity', 'equity', 1),
    ('00000000-0000-0000-0000-000000000001', '421', 'Lợi nhuận sau thuế chưa phân phối', 'equity', 'equity', 1),
    
    -- Revenue (Doanh thu)
    ('00000000-0000-0000-0000-000000000001', '511', 'Doanh thu bán hàng và cung cấp dịch vụ', 'revenue', 'revenue', 1),
    ('00000000-0000-0000-0000-000000000001', '515', 'Doanh thu hoạt động tài chính', 'revenue', 'revenue', 1),
    ('00000000-0000-0000-0000-000000000001', '711', 'Thu nhập khác', 'revenue', 'other_income', 1),
    
    -- Expenses (Chi phí)
    ('00000000-0000-0000-0000-000000000001', '621', 'Chi phí nguyên liệu, vật liệu trực tiếp', 'expense', 'cost', 1),
    ('00000000-0000-0000-0000-000000000001', '622', 'Chi phí nhân công trực tiếp', 'expense', 'cost', 1),
    ('00000000-0000-0000-0000-000000000001', '627', 'Chi phí sản xuất chung', 'expense', 'cost', 1),
    ('00000000-0000-0000-0000-000000000001', '632', 'Giá vốn hàng bán', 'expense', 'cost', 1),
    ('00000000-0000-0000-0000-000000000001', '641', 'Chi phí bán hàng', 'expense', 'operating', 1),
    ('00000000-0000-0000-0000-000000000001', '642', 'Chi phí quản lý doanh nghiệp', 'expense', 'operating', 1),
    ('00000000-0000-0000-0000-000000000001', '811', 'Chi phí khác', 'expense', 'other_expense', 1),
    ('00000000-0000-0000-0000-000000000001', '821', 'Chi phí thuế thu nhập doanh nghiệp', 'expense', 'tax', 1),
    
    -- Summary (Xác định kết quả)
    ('00000000-0000-0000-0000-000000000001', '911', 'Xác định kết quả kinh doanh', 'equity', 'summary', 1)
ON CONFLICT DO NOTHING;
