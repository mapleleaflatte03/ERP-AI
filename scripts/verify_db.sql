-- verify_db.sql - Quick verification query for Golden Flow tables
-- Part of PR-0: Baseline Freeze + Golden Tests
-- Usage: docker exec -i erpx-postgres psql -U erpx -d erpx < scripts/verify_db.sql

\echo '=================================================='
\echo 'ERPX AI Accounting - Database Verification'
\echo '=================================================='
\echo ''

-- Table counts summary
\echo '📊 TABLE RECORD COUNTS:'
\echo '-----------------------------------'
SELECT 'extracted_invoices' as table_name, count(*) as record_count FROM extracted_invoices
UNION ALL SELECT 'journal_proposals', count(*) FROM journal_proposals
UNION ALL SELECT 'journal_proposal_entries', count(*) FROM journal_proposal_entries
UNION ALL SELECT 'approvals', count(*) FROM approvals
UNION ALL SELECT 'ledger_entries', count(*) FROM ledger_entries
UNION ALL SELECT 'ledger_lines', count(*) FROM ledger_lines
ORDER BY table_name;

\echo ''
\echo '📋 LATEST EXTRACTED INVOICE:'
\echo '-----------------------------------'
SELECT 
    id,
    vendor_name,
    invoice_number,
    invoice_date,
    total_amount,
    currency,
    ai_confidence,
    created_at
FROM extracted_invoices 
ORDER BY created_at DESC 
LIMIT 1;

\echo ''
\echo '📋 LATEST JOURNAL PROPOSAL:'
\echo '-----------------------------------'
SELECT 
    id,
    status,
    ai_model,
    ai_confidence,
    risk_level,
    created_at
FROM journal_proposals 
ORDER BY created_at DESC 
LIMIT 1;

\echo ''
\echo '📋 LATEST JOURNAL ENTRIES (Debit/Credit):'
\echo '-----------------------------------'
SELECT 
    jpe.account_code,
    jpe.account_name,
    jpe.debit_amount,
    jpe.credit_amount,
    jpe.line_order
FROM journal_proposal_entries jpe
JOIN journal_proposals jp ON jp.id = jpe.proposal_id
ORDER BY jp.created_at DESC, jpe.line_order
LIMIT 4;

\echo ''
\echo '📋 LATEST APPROVAL:'
\echo '-----------------------------------'
SELECT 
    id,
    approver_name,
    action,
    comments,
    created_at
FROM approvals 
ORDER BY created_at DESC 
LIMIT 1;

\echo ''
\echo '📋 LATEST LEDGER ENTRY:'
\echo '-----------------------------------'
SELECT 
    id,
    entry_number,
    entry_date,
    description,
    posted_by_name,
    created_at
FROM ledger_entries 
ORDER BY created_at DESC 
LIMIT 1;

\echo ''
\echo '📋 LATEST LEDGER LINES:'
\echo '-----------------------------------'
SELECT 
    ll.account_code,
    ll.account_name,
    ll.debit_amount,
    ll.credit_amount,
    ll.line_order
FROM ledger_lines ll
JOIN ledger_entries le ON le.id = ll.ledger_entry_id
ORDER BY le.created_at DESC, ll.line_order
LIMIT 4;

\echo ''
\echo '=================================================='
\echo 'Verification complete'
\echo '=================================================='
