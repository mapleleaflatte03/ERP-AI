-- Initialize database schema for ERP AI
-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Documents table
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    filename VARCHAR(500) NOT NULL,
    file_type VARCHAR(50),
    file_path VARCHAR(1000),
    file_size BIGINT,
    upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50) DEFAULT 'uploaded',
    ocr_result JSONB,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Invoice extracted data
CREATE TABLE IF NOT EXISTS invoices (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID REFERENCES documents(id),
    invoice_number VARCHAR(100),
    invoice_date DATE,
    seller_name VARCHAR(500),
    seller_tax_code VARCHAR(50),
    buyer_name VARCHAR(500),
    buyer_tax_code VARCHAR(50),
    total_amount DECIMAL(18,2),
    vat_amount DECIMAL(18,2),
    currency VARCHAR(10) DEFAULT 'VND',
    raw_data JSONB,
    confidence_score DECIMAL(5,4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Accounting entries suggestions
CREATE TABLE IF NOT EXISTS accounting_entries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    invoice_id UUID REFERENCES invoices(id),
    debit_account VARCHAR(20),
    credit_account VARCHAR(20),
    amount DECIMAL(18,2),
    description TEXT,
    ai_explanation TEXT,
    confidence_score DECIMAL(5,4),
    source_references JSONB,
    status VARCHAR(50) DEFAULT 'suggested',
    reviewed_by VARCHAR(100),
    reviewed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Knowledge base for accounting rules
CREATE TABLE IF NOT EXISTS knowledge_base (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    category VARCHAR(100),
    title VARCHAR(500),
    content TEXT,
    account_codes JSONB,
    tags TEXT[],
    source VARCHAR(500),
    embedding_id VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Agent execution logs
CREATE TABLE IF NOT EXISTS agent_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID,
    agent_name VARCHAR(100),
    action VARCHAR(200),
    input_data JSONB,
    output_data JSONB,
    status VARCHAR(50),
    error_message TEXT,
    execution_time_ms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX idx_documents_status ON documents(status);
CREATE INDEX idx_documents_upload_time ON documents(upload_time);
CREATE INDEX idx_invoices_date ON invoices(invoice_date);
CREATE INDEX idx_invoices_seller_tax ON invoices(seller_tax_code);
CREATE INDEX idx_accounting_status ON accounting_entries(status);
CREATE INDEX idx_agent_logs_session ON agent_logs(session_id);
CREATE INDEX idx_knowledge_category ON knowledge_base(category);

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO erp_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO erp_user;

-- Log initialization
DO $$
BEGIN
    RAISE NOTICE 'ERP AI Database initialized successfully at %', NOW();
END $$;
