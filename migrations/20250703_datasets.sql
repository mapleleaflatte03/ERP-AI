-- Datasets table for Analyze module
-- Stores uploaded CSV/XLSX files for analysis

CREATE TABLE IF NOT EXISTS datasets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id),
    
    -- File info
    name VARCHAR(255) NOT NULL,
    description TEXT,
    filename VARCHAR(500),
    content_type VARCHAR(100),
    file_size BIGINT,
    minio_bucket VARCHAR(255),
    minio_key VARCHAR(500),
    
    -- Schema info (detected from file)
    columns JSONB DEFAULT '[]'::jsonb,  -- [{name, type, nullable, sample_values}]
    row_count INTEGER DEFAULT 0,
    
    -- ETL status
    status VARCHAR(50) DEFAULT 'pending',  -- pending, processing, ready, error
    etl_config JSONB DEFAULT '{}'::jsonb,   -- ETL transformation config
    error_message TEXT,
    
    -- For NL2SQL
    table_name VARCHAR(100),  -- Generated table name for queries
    
    -- Audit
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_datasets_tenant ON datasets(tenant_id);
CREATE INDEX IF NOT EXISTS idx_datasets_status ON datasets(status);
CREATE INDEX IF NOT EXISTS idx_datasets_name ON datasets(name);
CREATE INDEX IF NOT EXISTS idx_datasets_created ON datasets(created_at DESC);

-- Update trigger
DROP TRIGGER IF EXISTS update_datasets_updated_at ON datasets;
CREATE TRIGGER update_datasets_updated_at
    BEFORE UPDATE ON datasets
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

COMMENT ON TABLE datasets IS 'Uploaded datasets (CSV/XLSX) for the Analyze module';
COMMENT ON COLUMN datasets.columns IS 'Column schema: [{name: "col1", type: "text|numeric|date", nullable: true}]';
COMMENT ON COLUMN datasets.table_name IS 'Virtual table name used for NL2SQL queries';
