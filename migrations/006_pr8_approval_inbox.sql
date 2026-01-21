-- PR-8: Approval Inbox Enhancements
-- =====================================================
-- Enhances approvals table for inbox workflow

-- Add status column if not exists (check current schema first)
DO $$ 
BEGIN
    -- Add status column if missing
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='approvals' AND column_name='status') THEN
        ALTER TABLE approvals ADD COLUMN status VARCHAR(50) DEFAULT 'pending';
    END IF;
    
    -- Add job_id column for direct reference
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='approvals' AND column_name='job_id') THEN
        ALTER TABLE approvals ADD COLUMN job_id UUID;
    END IF;
    
    -- Add comment column (rename from comments if needed)
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='approvals' AND column_name='comment') THEN
        ALTER TABLE approvals ADD COLUMN comment TEXT;
    END IF;
    
    -- Add updated_at
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='approvals' AND column_name='updated_at') THEN
        ALTER TABLE approvals ADD COLUMN updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
    END IF;
END $$;

-- Create index on status
CREATE INDEX IF NOT EXISTS idx_approvals_status ON approvals(status);
CREATE INDEX IF NOT EXISTS idx_approvals_tenant ON approvals(tenant_id);
CREATE INDEX IF NOT EXISTS idx_approvals_job_id ON approvals(job_id);

-- =====================================================
-- APPROVAL_INBOX VIEW (Pending items with full context)
-- =====================================================
CREATE OR REPLACE VIEW approval_inbox AS
SELECT 
    a.id AS approval_id,
    a.proposal_id,
    a.job_id,
    a.tenant_id,
    a.status AS approval_status,
    a.action,
    a.approver_name,
    a.comment,
    a.comments,
    a.created_at AS approval_created_at,
    a.updated_at AS approval_updated_at,
    jp.status AS proposal_status,
    jp.ai_confidence,
    jp.ai_model,
    jp.ai_reasoning,
    jp.risk_level,
    ei.vendor_name,
    ei.invoice_number,
    ei.invoice_date,
    ei.total_amount,
    ei.currency,
    d.filename,
    d.file_path
FROM approvals a
LEFT JOIN journal_proposals jp ON a.proposal_id = jp.id
LEFT JOIN extracted_invoices ei ON jp.invoice_id = ei.id
LEFT JOIN documents d ON jp.document_id = d.id
WHERE a.action = 'pending' OR a.status = 'pending';

GRANT SELECT ON approval_inbox TO erpx;
