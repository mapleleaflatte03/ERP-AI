-- Add missing business tables for ERPX AI Accounting
-- Version: 004

-- Job Runs table (tracks workflow executions)
CREATE TABLE IF NOT EXISTS job_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES documents(id),
    tenant_id UUID REFERENCES tenants(id),
    status VARCHAR(50) DEFAULT 'pending',
    workflow_id VARCHAR(255),
    run_id VARCHAR(255),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    result JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Extracted Invoices table (OCR/AI extraction results)
CREATE TABLE IF NOT EXISTS extracted_invoices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES documents(id),
    job_id UUID REFERENCES job_runs(id),
    tenant_id UUID REFERENCES tenants(id),
    vendor_name VARCHAR(255),
    vendor_tax_id VARCHAR(50),
    invoice_number VARCHAR(100),
    invoice_date DATE,
    due_date DATE,
    subtotal DECIMAL(18,2),
    tax_amount DECIMAL(18,2),
    total_amount DECIMAL(18,2),
    currency VARCHAR(10) DEFAULT 'VND',
    line_items JSONB,
    raw_text TEXT,
    ocr_confidence DECIMAL(5,4),
    ai_confidence DECIMAL(5,4),
    extracted_by VARCHAR(100) DEFAULT 'do_agent_qwen3-32b',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Journal Proposals table (AI-generated journal entries)
CREATE TABLE IF NOT EXISTS journal_proposals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES documents(id),
    invoice_id UUID REFERENCES extracted_invoices(id),
    tenant_id UUID REFERENCES tenants(id),
    status VARCHAR(50) DEFAULT 'pending',
    ai_confidence DECIMAL(5,4),
    ai_model VARCHAR(100) DEFAULT 'qwen3-32b',
    ai_reasoning TEXT,
    risk_level VARCHAR(20),
    opa_validation JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Journal Proposal Entries table (debit/credit lines)
CREATE TABLE IF NOT EXISTS journal_proposal_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proposal_id UUID REFERENCES journal_proposals(id),
    account_code VARCHAR(20) NOT NULL,
    account_name VARCHAR(255),
    debit_amount DECIMAL(18,2) DEFAULT 0,
    credit_amount DECIMAL(18,2) DEFAULT 0,
    description TEXT,
    line_order INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Approvals table (tracks approval workflow)
CREATE TABLE IF NOT EXISTS approvals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proposal_id UUID REFERENCES journal_proposals(id),
    tenant_id UUID REFERENCES tenants(id),
    approver_id UUID REFERENCES users(id),
    approver_name VARCHAR(255),
    action VARCHAR(50) NOT NULL, -- 'approved', 'rejected', 'requested_changes'
    comments TEXT,
    approved_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Ledger Entries table (posted journal entries)
CREATE TABLE IF NOT EXISTS ledger_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proposal_id UUID REFERENCES journal_proposals(id),
    approval_id UUID REFERENCES approvals(id),
    tenant_id UUID REFERENCES tenants(id),
    entry_date DATE NOT NULL,
    entry_number VARCHAR(50),
    description TEXT,
    reference_number VARCHAR(100),
    source_document VARCHAR(255),
    posted_by UUID REFERENCES users(id),
    posted_by_name VARCHAR(255),
    posted_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    is_reversal BOOLEAN DEFAULT FALSE,
    reversal_of UUID REFERENCES ledger_entries(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Ledger Lines table (debit/credit lines in posted entries)
CREATE TABLE IF NOT EXISTS ledger_lines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ledger_entry_id UUID REFERENCES ledger_entries(id),
    account_code VARCHAR(20) NOT NULL,
    account_name VARCHAR(255),
    debit_amount DECIMAL(18,2) DEFAULT 0,
    credit_amount DECIMAL(18,2) DEFAULT 0,
    description TEXT,
    line_order INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_job_runs_document ON job_runs(document_id);
CREATE INDEX IF NOT EXISTS idx_job_runs_status ON job_runs(status);
CREATE INDEX IF NOT EXISTS idx_extracted_invoices_document ON extracted_invoices(document_id);
CREATE INDEX IF NOT EXISTS idx_journal_proposals_document ON journal_proposals(document_id);
CREATE INDEX IF NOT EXISTS idx_journal_proposals_status ON journal_proposals(status);
CREATE INDEX IF NOT EXISTS idx_approvals_proposal ON approvals(proposal_id);
CREATE INDEX IF NOT EXISTS idx_ledger_entries_date ON ledger_entries(entry_date);
CREATE INDEX IF NOT EXISTS idx_ledger_lines_entry ON ledger_lines(ledger_entry_id);

-- Insert sample data for verification
INSERT INTO job_runs (document_id, status, workflow_id, run_id, started_at)
SELECT d.id, 'completed', 'wf-' || substr(md5(random()::text), 1, 16), 'run-' || substr(md5(random()::text), 1, 16), NOW()
FROM documents d
LIMIT 1
ON CONFLICT DO NOTHING;

COMMIT;
