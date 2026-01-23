-- PR19: Durable DB Idempotency Constraints
-- =========================================
-- Ensure posting operations are exactly-once at the database level.
-- These constraints prevent duplicate ledger entries and outbox events
-- even under activity retries, duplicate approve signals, or crashes.

-- 1. Unique constraint for ledger_entries per proposal
-- Ensures only one ledger entry can exist per proposal_id
CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_ledger_per_proposal 
    ON ledger_entries (proposal_id) 
    WHERE proposal_id IS NOT NULL;

-- 2. Unique constraint for outbox ledger.posted events per aggregate
-- Ensures only one ledger.posted event can exist per ledger entry
CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_outbox_ledger_posted 
    ON outbox_events (aggregate_type, aggregate_id, event_type) 
    WHERE event_type = 'ledger.posted';

-- Note: These are partial unique indexes that only apply when:
-- - ledger_entries.proposal_id is NOT NULL
-- - outbox_events.event_type = 'ledger.posted'
-- This allows flexibility for other use cases while enforcing
-- idempotency for the critical posting paths.
