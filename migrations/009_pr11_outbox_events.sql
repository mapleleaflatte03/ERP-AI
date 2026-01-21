-- PR-11: Event Bus / Outbox Pattern
-- ================================
-- Transactional outbox for reliable event delivery
-- Supports webhooks, Temporal workflows, and external integrations

-- ============================================
-- Outbox Events Table
-- ============================================
-- Stores events that need to be published to external systems

CREATE TABLE IF NOT EXISTS outbox_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Event identification
    event_type VARCHAR(50) NOT NULL, -- job.created, job.completed, proposal.approved, ledger.posted
    aggregate_type VARCHAR(50) NOT NULL, -- job, proposal, approval, ledger
    aggregate_id VARCHAR(100) NOT NULL, -- The ID of the entity that emitted the event
    
    -- Tenant isolation
    tenant_id UUID REFERENCES tenants(id),
    
    -- Event payload
    payload JSONB NOT NULL,
    
    -- Delivery tracking
    status VARCHAR(20) DEFAULT 'pending', -- pending, processing, delivered, failed, dead_letter
    attempts INTEGER DEFAULT 0,
    max_attempts INTEGER DEFAULT 5,
    last_attempt_at TIMESTAMPTZ,
    last_error TEXT,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    scheduled_at TIMESTAMPTZ DEFAULT NOW(), -- For delayed delivery
    delivered_at TIMESTAMPTZ,
    
    -- Tracing
    request_id VARCHAR(100),
    trace_id VARCHAR(100)
);

CREATE INDEX IF NOT EXISTS idx_outbox_status ON outbox_events(status);
CREATE INDEX IF NOT EXISTS idx_outbox_type ON outbox_events(event_type);
CREATE INDEX IF NOT EXISTS idx_outbox_aggregate ON outbox_events(aggregate_type, aggregate_id);
CREATE INDEX IF NOT EXISTS idx_outbox_scheduled ON outbox_events(scheduled_at) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_outbox_tenant ON outbox_events(tenant_id);

-- ============================================
-- Event Subscriptions Table
-- ============================================
-- Configures where events should be delivered

CREATE TABLE IF NOT EXISTS event_subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Subscription configuration
    name VARCHAR(100) NOT NULL,
    tenant_id UUID REFERENCES tenants(id),
    
    -- Event filtering
    event_types TEXT[] NOT NULL, -- Array of event types to subscribe to
    
    -- Delivery target
    delivery_type VARCHAR(20) NOT NULL, -- webhook, temporal, internal
    delivery_config JSONB NOT NULL DEFAULT '{}',
    -- webhook: {"url": "https://...", "headers": {}, "method": "POST"}
    -- temporal: {"workflow": "...", "task_queue": "...", "workflow_id_prefix": "..."}
    -- internal: {"handler": "..."}
    
    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    
    -- Rate limiting
    rate_limit_per_minute INTEGER DEFAULT 60,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT uk_subscription_name_tenant UNIQUE(name, tenant_id)
);

CREATE INDEX IF NOT EXISTS idx_subscription_active ON event_subscriptions(is_active);
CREATE INDEX IF NOT EXISTS idx_subscription_types ON event_subscriptions USING GIN(event_types);

-- ============================================
-- Event Delivery Log Table
-- ============================================
-- Tracks individual delivery attempts

CREATE TABLE IF NOT EXISTS event_deliveries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- References
    event_id UUID NOT NULL REFERENCES outbox_events(id) ON DELETE CASCADE,
    subscription_id UUID REFERENCES event_subscriptions(id),
    
    -- Delivery info
    attempt_number INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL, -- success, failed, timeout
    
    -- Response tracking
    response_code INTEGER,
    response_body TEXT,
    response_time_ms INTEGER,
    
    -- Error info
    error_message TEXT,
    
    -- Timestamps
    attempted_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_delivery_event ON event_deliveries(event_id);
CREATE INDEX IF NOT EXISTS idx_delivery_subscription ON event_deliveries(subscription_id);
CREATE INDEX IF NOT EXISTS idx_delivery_status ON event_deliveries(status);

-- ============================================
-- Dead Letter Queue
-- ============================================
-- Events that failed all delivery attempts

CREATE TABLE IF NOT EXISTS dead_letter_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Original event reference
    original_event_id UUID NOT NULL REFERENCES outbox_events(id),
    
    -- Copy of event data
    event_type VARCHAR(50) NOT NULL,
    aggregate_type VARCHAR(50) NOT NULL,
    aggregate_id VARCHAR(100) NOT NULL,
    payload JSONB NOT NULL,
    
    -- Failure info
    failure_reason TEXT NOT NULL,
    total_attempts INTEGER NOT NULL,
    
    -- Resolution
    status VARCHAR(20) DEFAULT 'unresolved', -- unresolved, retrying, resolved, discarded
    resolved_at TIMESTAMPTZ,
    resolved_by VARCHAR(100),
    resolution_notes TEXT,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Tenant
    tenant_id UUID REFERENCES tenants(id)
);

CREATE INDEX IF NOT EXISTS idx_dlq_status ON dead_letter_events(status);
CREATE INDEX IF NOT EXISTS idx_dlq_event_type ON dead_letter_events(event_type);

-- ============================================
-- Insert Default Subscriptions
-- ============================================

INSERT INTO event_subscriptions (name, event_types, delivery_type, delivery_config)
VALUES 
    -- Internal audit logging
    ('internal_audit', 
     ARRAY['job.created', 'job.completed', 'job.failed', 'proposal.approved', 'proposal.rejected', 'ledger.posted'],
     'internal', 
     '{"handler": "audit_log_handler"}'),
    
    -- Temporal workflow trigger
    ('temporal_workflow',
     ARRAY['job.created'],
     'temporal',
     '{"workflow": "process_document_workflow", "task_queue": "erpx-ai", "workflow_id_prefix": "doc-"}')
ON CONFLICT DO NOTHING;

-- ============================================
-- Grants
-- ============================================

GRANT SELECT, INSERT, UPDATE ON outbox_events TO erpx;
GRANT SELECT, INSERT, UPDATE ON event_subscriptions TO erpx;
GRANT SELECT, INSERT ON event_deliveries TO erpx;
GRANT SELECT, INSERT, UPDATE ON dead_letter_events TO erpx;

-- ============================================
-- Comments
-- ============================================

COMMENT ON TABLE outbox_events IS 'PR-11: Transactional outbox for reliable event delivery';
COMMENT ON TABLE event_subscriptions IS 'PR-11: Event subscription configuration';
COMMENT ON TABLE event_deliveries IS 'PR-11: Event delivery attempt log';
COMMENT ON TABLE dead_letter_events IS 'PR-11: Dead letter queue for failed events';

-- ============================================
-- Helper Function: Publish Event
-- ============================================

CREATE OR REPLACE FUNCTION publish_event(
    p_event_type VARCHAR(50),
    p_aggregate_type VARCHAR(50),
    p_aggregate_id VARCHAR(100),
    p_payload JSONB,
    p_tenant_id UUID DEFAULT NULL,
    p_request_id VARCHAR(100) DEFAULT NULL
)
RETURNS UUID AS $$
DECLARE
    v_event_id UUID;
BEGIN
    INSERT INTO outbox_events 
    (event_type, aggregate_type, aggregate_id, payload, tenant_id, request_id)
    VALUES (p_event_type, p_aggregate_type, p_aggregate_id, p_payload, p_tenant_id, p_request_id)
    RETURNING id INTO v_event_id;
    
    RETURN v_event_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION publish_event IS 'PR-11: Publish event to outbox within transaction';
