-- ERPX AI Accounting - Database Initialization Script
-- ====================================================

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- TRANSACTIONS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS transactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(100) NOT NULL,
    doc_id VARCHAR(100) NOT NULL,
    doc_type VARCHAR(50) NOT NULL,
    posting_date DATE,
    doc_date DATE,
    amount DECIMAL(18, 2),
    currency VARCHAR(10) DEFAULT 'VND',
    status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by VARCHAR(100),
    
    -- ASOFT-T Payload
    asof_payload JSONB,
    
    -- Evidence
    evidence JSONB,
    
    -- Processing metadata
    processing_mode VARCHAR(20),
    confidence_score DECIMAL(3, 2),
    needs_review BOOLEAN DEFAULT FALSE,
    review_reasons TEXT[],
    
    UNIQUE(tenant_id, doc_id)
);

CREATE INDEX idx_transactions_tenant ON transactions(tenant_id);
CREATE INDEX idx_transactions_doc_type ON transactions(doc_type);
CREATE INDEX idx_transactions_status ON transactions(status);
CREATE INDEX idx_transactions_posting_date ON transactions(posting_date);

-- ============================================================================
-- AUDIT LOG TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(100) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    entity_id VARCHAR(100) NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    event_data JSONB,
    user_id VARCHAR(100),
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    ip_address INET,
    user_agent TEXT
);

CREATE INDEX idx_audit_log_tenant ON audit_log(tenant_id);
CREATE INDEX idx_audit_log_entity ON audit_log(entity_type, entity_id);
CREATE INDEX idx_audit_log_timestamp ON audit_log(timestamp);
CREATE INDEX idx_audit_log_user ON audit_log(user_id);

-- ============================================================================
-- APPROVAL QUEUE TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS approval_queue (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    request_id VARCHAR(100) UNIQUE NOT NULL,
    tenant_id VARCHAR(100) NOT NULL,
    doc_id VARCHAR(100) NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    priority VARCHAR(20) DEFAULT 'medium',
    reasons TEXT[],
    document_type VARCHAR(50),
    amount DECIMAL(18, 2),
    currency VARCHAR(10) DEFAULT 'VND',
    vendor VARCHAR(200),
    proposed_coding JSONB,
    evidence_summary TEXT,
    assigned_to VARCHAR(100),
    escalation_path TEXT[],
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by VARCHAR(100),
    resolved_at TIMESTAMP WITH TIME ZONE,
    resolved_by VARCHAR(100),
    resolution_notes TEXT,
    approved_coding JSONB,
    metadata JSONB
);

CREATE INDEX idx_approval_queue_tenant ON approval_queue(tenant_id);
CREATE INDEX idx_approval_queue_status ON approval_queue(status);
CREATE INDEX idx_approval_queue_assigned ON approval_queue(assigned_to);
CREATE INDEX idx_approval_queue_priority ON approval_queue(priority);

-- ============================================================================
-- RECONCILIATION HISTORY TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS reconciliation_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(100) NOT NULL,
    reconciliation_date DATE NOT NULL,
    bank_account VARCHAR(50),
    total_transactions INTEGER,
    matched_count INTEGER,
    unmatched_count INTEGER,
    total_matched_amount DECIMAL(18, 2),
    total_unmatched_amount DECIMAL(18, 2),
    status VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by VARCHAR(100),
    details JSONB
);

CREATE INDEX idx_reconciliation_tenant ON reconciliation_history(tenant_id);
CREATE INDEX idx_reconciliation_date ON reconciliation_history(reconciliation_date);

-- ============================================================================
-- VENDORS TABLE (Master Data)
-- ============================================================================
CREATE TABLE IF NOT EXISTS vendors (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(100) NOT NULL,
    vendor_code VARCHAR(50) NOT NULL,
    vendor_name VARCHAR(200) NOT NULL,
    tax_id VARCHAR(20),
    address TEXT,
    contact_info JSONB,
    payment_terms INTEGER DEFAULT 30,
    credit_limit DECIMAL(18, 2),
    is_active BOOLEAN DEFAULT TRUE,
    is_approved BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(tenant_id, vendor_code)
);

CREATE INDEX idx_vendors_tenant ON vendors(tenant_id);
CREATE INDEX idx_vendors_tax_id ON vendors(tax_id);

-- ============================================================================
-- CHART OF ACCOUNTS TABLE (Master Data)
-- ============================================================================
CREATE TABLE IF NOT EXISTS chart_of_accounts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(100) NOT NULL,
    account_code VARCHAR(20) NOT NULL,
    account_name VARCHAR(200) NOT NULL,
    account_type VARCHAR(50),
    parent_code VARCHAR(20),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(tenant_id, account_code)
);

CREATE INDEX idx_coa_tenant ON chart_of_accounts(tenant_id);
CREATE INDEX idx_coa_type ON chart_of_accounts(account_type);

-- ============================================================================
-- FUNCTIONS
-- ============================================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger for transactions table
CREATE TRIGGER update_transactions_updated_at
    BEFORE UPDATE ON transactions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger for vendors table
CREATE TRIGGER update_vendors_updated_at
    BEFORE UPDATE ON vendors
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- INITIAL DATA
-- ============================================================================

-- Insert demo tenant
INSERT INTO vendors (tenant_id, vendor_code, vendor_name, tax_id, is_approved)
VALUES 
    ('demo-tenant-001', 'V001', 'Công ty TNHH ABC', '0123456789', TRUE),
    ('demo-tenant-001', 'V002', 'Công ty CP XYZ', '0987654321', TRUE),
    ('demo-tenant-001', 'V003', 'Công ty TNHH Thương mại DEF', '0111222333', FALSE)
ON CONFLICT DO NOTHING;

-- Insert Vietnamese chart of accounts (simplified)
INSERT INTO chart_of_accounts (tenant_id, account_code, account_name, account_type)
VALUES
    ('demo-tenant-001', '111', 'Tiền mặt', 'asset'),
    ('demo-tenant-001', '112', 'Tiền gửi ngân hàng', 'asset'),
    ('demo-tenant-001', '131', 'Phải thu khách hàng', 'asset'),
    ('demo-tenant-001', '1331', 'Thuế GTGT được khấu trừ - Hàng hóa dịch vụ', 'asset'),
    ('demo-tenant-001', '141', 'Tạm ứng', 'asset'),
    ('demo-tenant-001', '152', 'Nguyên liệu, vật liệu', 'asset'),
    ('demo-tenant-001', '156', 'Hàng hóa', 'asset'),
    ('demo-tenant-001', '211', 'Tài sản cố định hữu hình', 'asset'),
    ('demo-tenant-001', '331', 'Phải trả người bán', 'liability'),
    ('demo-tenant-001', '333', 'Thuế và các khoản phải nộp Nhà nước', 'liability'),
    ('demo-tenant-001', '3331', 'Thuế GTGT phải nộp', 'liability'),
    ('demo-tenant-001', '411', 'Vốn đầu tư của chủ sở hữu', 'equity'),
    ('demo-tenant-001', '511', 'Doanh thu bán hàng và cung cấp dịch vụ', 'revenue'),
    ('demo-tenant-001', '632', 'Giá vốn hàng bán', 'expense'),
    ('demo-tenant-001', '642', 'Chi phí quản lý doanh nghiệp', 'expense'),
    ('demo-tenant-001', '6421', 'Chi phí văn phòng', 'expense'),
    ('demo-tenant-001', '6422', 'Chi phí điện nước', 'expense'),
    ('demo-tenant-001', '6423', 'Chi phí thuê mặt bằng', 'expense'),
    ('demo-tenant-001', '6424', 'Chi phí dịch vụ', 'expense')
ON CONFLICT DO NOTHING;

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO erpx;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO erpx;
