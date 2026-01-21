"""
ERPX AI Accounting - Database Module
=====================================
PostgreSQL database operations with async support.
"""

import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, List, Optional

import asyncpg
from asyncpg import Pool

from src.core import JobRecord, JobStatus, config

logger = logging.getLogger(__name__)

# =============================================================================
# Database Pool
# =============================================================================

_pool: Pool | None = None


async def get_pool() -> Pool:
    """Get or create database connection pool"""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            config.DATABASE_URL,
            min_size=2,
            max_size=10,
            command_timeout=60,
        )
        logger.info("Database pool created")
    return _pool


async def close_pool():
    """Close database connection pool"""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        logger.info("Database pool closed")


@asynccontextmanager
async def get_connection():
    """Get database connection from pool"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        yield conn


# =============================================================================
# Schema Initialization
# =============================================================================

SCHEMA_SQL = """
-- Companies
CREATE TABLE IF NOT EXISTS companies (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    tax_id VARCHAR(50),
    address TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Users
CREATE TABLE IF NOT EXISTS users (
    id VARCHAR(36) PRIMARY KEY,
    company_id VARCHAR(36) REFERENCES companies(id),
    username VARCHAR(100) NOT NULL UNIQUE,
    email VARCHAR(255),
    role VARCHAR(50) DEFAULT 'accountant',
    created_at TIMESTAMP DEFAULT NOW()
);

-- Documents (raw uploads)
CREATE TABLE IF NOT EXISTS documents (
    id VARCHAR(36) PRIMARY KEY,
    company_id VARCHAR(36) REFERENCES companies(id),
    user_id VARCHAR(36) REFERENCES users(id),
    filename VARCHAR(500) NOT NULL,
    content_type VARCHAR(100),
    file_size BIGINT,
    checksum VARCHAR(64),
    minio_bucket VARCHAR(100),
    minio_key VARCHAR(500),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Jobs (processing jobs)
CREATE TABLE IF NOT EXISTS jobs (
    id VARCHAR(36) PRIMARY KEY,
    company_id VARCHAR(36) DEFAULT 'default',
    user_id VARCHAR(36),
    document_id VARCHAR(36) REFERENCES documents(id),
    status VARCHAR(50) DEFAULT 'pending',
    document_type VARCHAR(50),
    filename VARCHAR(500),
    content_type VARCHAR(100),
    file_size BIGINT,
    minio_bucket VARCHAR(100),
    minio_key VARCHAR(500),
    extracted_data JSONB,
    journal_proposal JSONB,
    validation_result JSONB,
    approval_state VARCHAR(50),
    approved_by VARCHAR(36),
    approved_at TIMESTAMP,
    ledger_posted BOOLEAN DEFAULT FALSE,
    ledger_entry_id VARCHAR(36),
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Extracted invoices
CREATE TABLE IF NOT EXISTS extracted_invoices (
    id VARCHAR(36) PRIMARY KEY,
    job_id VARCHAR(36) REFERENCES jobs(id),
    company_id VARCHAR(36),
    raw_text TEXT,
    vendor_name VARCHAR(255),
    vendor_tax_id VARCHAR(50),
    invoice_number VARCHAR(100),
    invoice_date DATE,
    total_amount DECIMAL(18,2),
    vat_amount DECIMAL(18,2),
    currency VARCHAR(10) DEFAULT 'VND',
    line_items JSONB,
    confidence DECIMAL(5,4),
    extraction_method VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Journal proposals
CREATE TABLE IF NOT EXISTS journal_proposals (
    id VARCHAR(36) PRIMARY KEY,
    job_id VARCHAR(36) REFERENCES jobs(id),
    company_id VARCHAR(36),
    doc_type VARCHAR(50),
    description TEXT,
    reference VARCHAR(100),
    vendor_name VARCHAR(255),
    invoice_number VARCHAR(100),
    invoice_date DATE,
    total_amount DECIMAL(18,2),
    currency VARCHAR(10) DEFAULT 'VND',
    vat_amount DECIMAL(18,2),
    entries JSONB NOT NULL,
    confidence DECIMAL(5,4),
    reasoning TEXT,
    is_balanced BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Approvals
CREATE TABLE IF NOT EXISTS approvals (
    id VARCHAR(36) PRIMARY KEY,
    job_id VARCHAR(36) REFERENCES jobs(id),
    proposal_id VARCHAR(36) REFERENCES journal_proposals(id),
    action VARCHAR(20) NOT NULL,
    approved_by VARCHAR(36),
    reason TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Ledger entries (posted transactions)
CREATE TABLE IF NOT EXISTS ledger_entries (
    id VARCHAR(36) PRIMARY KEY,
    company_id VARCHAR(36),
    job_id VARCHAR(36) REFERENCES jobs(id),
    proposal_id VARCHAR(36) REFERENCES journal_proposals(id),
    entry_date DATE NOT NULL,
    description TEXT,
    reference VARCHAR(100),
    total_debit DECIMAL(18,2) NOT NULL,
    total_credit DECIMAL(18,2) NOT NULL,
    posted_by VARCHAR(36),
    posted_at TIMESTAMP DEFAULT NOW(),
    reversed BOOLEAN DEFAULT FALSE,
    reversed_by VARCHAR(36),
    reversed_at TIMESTAMP,
    CONSTRAINT ledger_balanced CHECK (total_debit = total_credit)
);

-- Ledger lines
CREATE TABLE IF NOT EXISTS ledger_lines (
    id VARCHAR(36) PRIMARY KEY,
    entry_id VARCHAR(36) REFERENCES ledger_entries(id),
    account_code VARCHAR(20) NOT NULL,
    account_name VARCHAR(255),
    debit DECIMAL(18,2) DEFAULT 0,
    credit DECIMAL(18,2) DEFAULT 0,
    description TEXT,
    line_order INT DEFAULT 0
);

-- Audit logs
CREATE TABLE IF NOT EXISTS audit_logs (
    id SERIAL PRIMARY KEY,
    company_id VARCHAR(36),
    user_id VARCHAR(36),
    job_id VARCHAR(36),
    action VARCHAR(100) NOT NULL,
    entity_type VARCHAR(50),
    entity_id VARCHAR(36),
    old_value JSONB,
    new_value JSONB,
    ip_address VARCHAR(50),
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- LLM call logs
CREATE TABLE IF NOT EXISTS llm_call_logs (
    id SERIAL PRIMARY KEY,
    request_id VARCHAR(36) NOT NULL,
    job_id VARCHAR(36),
    llm_provider VARCHAR(50) DEFAULT 'do_agent',
    model VARCHAR(50) DEFAULT 'qwen3-32b',
    prompt_tokens INT,
    completion_tokens INT,
    latency_ms DECIMAL(10,2),
    status VARCHAR(20),
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- KB sources (knowledge base)
CREATE TABLE IF NOT EXISTS kb_sources (
    id VARCHAR(36) PRIMARY KEY,
    source_type VARCHAR(50) NOT NULL,
    source_url TEXT,
    source_file VARCHAR(500),
    doc_type VARCHAR(50),
    title VARCHAR(500),
    content_hash VARCHAR(64),
    chunk_count INT DEFAULT 0,
    qdrant_collection VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Chart of accounts
CREATE TABLE IF NOT EXISTS chart_of_accounts (
    id VARCHAR(36) PRIMARY KEY,
    company_id VARCHAR(36),
    account_code VARCHAR(20) NOT NULL,
    account_name VARCHAR(255) NOT NULL,
    account_type VARCHAR(50),
    parent_code VARCHAR(20),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(company_id, account_code)
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company_id);
CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ledger_company ON ledger_entries(company_id);
CREATE INDEX IF NOT EXISTS idx_ledger_date ON ledger_entries(entry_date);
CREATE INDEX IF NOT EXISTS idx_audit_job ON audit_logs(job_id);
CREATE INDEX IF NOT EXISTS idx_llm_logs_job ON llm_call_logs(job_id);

-- Insert default company
INSERT INTO companies (id, name, tax_id) 
VALUES ('default', 'Default Company', '0000000000')
ON CONFLICT (id) DO NOTHING;

-- Insert default user
INSERT INTO users (id, company_id, username, email, role)
VALUES ('system', 'default', 'system', 'system@erpx.local', 'admin')
ON CONFLICT (id) DO NOTHING;

-- Insert TT200 Chart of Accounts for default company
INSERT INTO chart_of_accounts (id, company_id, account_code, account_name, account_type) VALUES
('coa-111', 'default', '111', 'Tiền mặt', 'asset'),
('coa-112', 'default', '112', 'Tiền gửi ngân hàng', 'asset'),
('coa-131', 'default', '131', 'Phải thu của khách hàng', 'asset'),
('coa-133', 'default', '133', 'Thuế GTGT được khấu trừ', 'asset'),
('coa-141', 'default', '141', 'Tạm ứng', 'asset'),
('coa-152', 'default', '152', 'Nguyên liệu, vật liệu', 'asset'),
('coa-153', 'default', '153', 'Công cụ, dụng cụ', 'asset'),
('coa-154', 'default', '154', 'Chi phí SXKD dở dang', 'asset'),
('coa-155', 'default', '155', 'Thành phẩm', 'asset'),
('coa-156', 'default', '156', 'Hàng hóa', 'asset'),
('coa-211', 'default', '211', 'TSCĐ hữu hình', 'asset'),
('coa-214', 'default', '214', 'Hao mòn TSCĐ', 'contra_asset'),
('coa-331', 'default', '331', 'Phải trả người bán', 'liability'),
('coa-333', 'default', '333', 'Thuế và các khoản phải nộp NN', 'liability'),
('coa-3331', 'default', '3331', 'Thuế GTGT phải nộp', 'liability'),
('coa-334', 'default', '334', 'Phải trả người lao động', 'liability'),
('coa-338', 'default', '338', 'Phải trả, phải nộp khác', 'liability'),
('coa-341', 'default', '341', 'Vay và nợ thuê tài chính', 'liability'),
('coa-411', 'default', '411', 'Vốn đầu tư của chủ sở hữu', 'equity'),
('coa-421', 'default', '421', 'Lợi nhuận sau thuế chưa phân phối', 'equity'),
('coa-511', 'default', '511', 'Doanh thu bán hàng và cung cấp dịch vụ', 'revenue'),
('coa-515', 'default', '515', 'Doanh thu hoạt động tài chính', 'revenue'),
('coa-621', 'default', '621', 'Chi phí nguyên liệu, vật liệu trực tiếp', 'expense'),
('coa-622', 'default', '622', 'Chi phí nhân công trực tiếp', 'expense'),
('coa-627', 'default', '627', 'Chi phí sản xuất chung', 'expense'),
('coa-632', 'default', '632', 'Giá vốn hàng bán', 'expense'),
('coa-635', 'default', '635', 'Chi phí tài chính', 'expense'),
('coa-641', 'default', '641', 'Chi phí bán hàng', 'expense'),
('coa-642', 'default', '642', 'Chi phí quản lý doanh nghiệp', 'expense'),
('coa-811', 'default', '811', 'Chi phí khác', 'expense'),
('coa-821', 'default', '821', 'Chi phí thuế thu nhập doanh nghiệp', 'expense'),
('coa-911', 'default', '911', 'Xác định kết quả kinh doanh', 'summary')
ON CONFLICT (id) DO NOTHING;
"""


async def init_schema():
    """Initialize database schema"""
    async with get_connection() as conn:
        await conn.execute(SCHEMA_SQL)
        logger.info("Database schema initialized")


# =============================================================================
# Job Operations
# =============================================================================


async def create_job(
    job_id: str,
    filename: str,
    content_type: str,
    file_size: int,
    minio_bucket: str,
    minio_key: str,
    company_id: str = "default",
    user_id: str | None = None,
) -> dict:
    """Create a new job record"""
    async with get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO jobs (id, company_id, user_id, filename, content_type, file_size, minio_bucket, minio_key, status, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'pending', NOW(), NOW())
            """,
            job_id,
            company_id,
            user_id,
            filename,
            content_type,
            file_size,
            minio_bucket,
            minio_key,
        )
        logger.info(f"Created job {job_id}")
        return {"job_id": job_id, "status": "pending"}


async def get_job(job_id: str) -> dict | None:
    """Get job by ID"""
    async with get_connection() as conn:
        row = await conn.fetchrow("SELECT * FROM jobs WHERE id = $1", job_id)
        if row:
            return dict(row)
        return None


async def update_job_status(job_id: str, status: str, **kwargs):
    """Update job status and optional fields"""
    async with get_connection() as conn:
        # Build update query
        set_clauses = ["status = $2", "updated_at = NOW()"]
        params = [job_id, status]
        param_idx = 3

        field_map = {
            "document_type": "document_type",
            "extracted_data": "extracted_data",
            "journal_proposal": "journal_proposal",
            "validation_result": "validation_result",
            "approval_state": "approval_state",
            "approved_by": "approved_by",
            "approved_at": "approved_at",
            "ledger_posted": "ledger_posted",
            "ledger_entry_id": "ledger_entry_id",
            "error_message": "error_message",
        }

        for key, col in field_map.items():
            if key in kwargs:
                set_clauses.append(f"{col} = ${param_idx}")
                params.append(kwargs[key])
                param_idx += 1

        query = f"UPDATE jobs SET {', '.join(set_clauses)} WHERE id = $1"
        await conn.execute(query, *params)
        logger.info(f"Updated job {job_id} to status {status}")


async def get_jobs_by_status(status: str, limit: int = 100) -> list[dict]:
    """Get jobs by status"""
    async with get_connection() as conn:
        rows = await conn.fetch("SELECT * FROM jobs WHERE status = $1 ORDER BY created_at DESC LIMIT $2", status, limit)
        return [dict(row) for row in rows]


async def get_recent_jobs(company_id: str = "default", limit: int = 10) -> list[dict]:
    """Get recent jobs for a company"""
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT id, status, document_type, filename, created_at, updated_at,
                   ledger_posted, approval_state
            FROM jobs 
            WHERE company_id = $1 
            ORDER BY created_at DESC 
            LIMIT $2
            """,
            company_id,
            limit,
        )
        return [dict(row) for row in rows]


# =============================================================================
# Ledger Operations
# =============================================================================


async def post_ledger_entry(
    job_id: str,
    proposal_id: str,
    entries: list[dict],
    description: str,
    reference: str | None = None,
    posted_by: str = "system",
    company_id: str = "default",
) -> str:
    """Post a journal entry to ledger"""
    entry_id = str(uuid.uuid4())

    total_debit = sum(e.get("debit", 0) for e in entries)
    total_credit = sum(e.get("credit", 0) for e in entries)

    if abs(total_debit - total_credit) > 0.01:
        raise ValueError(f"Ledger entry not balanced: debit={total_debit}, credit={total_credit}")

    async with get_connection() as conn:
        async with conn.transaction():
            # Insert ledger entry
            await conn.execute(
                """
                INSERT INTO ledger_entries (id, company_id, job_id, proposal_id, entry_date, description, reference, total_debit, total_credit, posted_by)
                VALUES ($1, $2, $3, $4, CURRENT_DATE, $5, $6, $7, $8, $9)
                """,
                entry_id,
                company_id,
                job_id,
                proposal_id,
                description,
                reference,
                total_debit,
                total_credit,
                posted_by,
            )

            # Insert ledger lines
            for idx, entry in enumerate(entries):
                line_id = str(uuid.uuid4())
                await conn.execute(
                    """
                    INSERT INTO ledger_lines (id, entry_id, account_code, account_name, debit, credit, description, line_order)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    """,
                    line_id,
                    entry_id,
                    entry["account_code"],
                    entry.get("account_name", ""),
                    entry.get("debit", 0),
                    entry.get("credit", 0),
                    entry.get("description", ""),
                    idx,
                )

            # Update job
            await conn.execute(
                """
                UPDATE jobs SET ledger_posted = TRUE, ledger_entry_id = $2, 
                                approval_state = 'approved', status = 'posted', updated_at = NOW()
                WHERE id = $1
                """,
                job_id,
                entry_id,
            )

            logger.info(f"Posted ledger entry {entry_id} for job {job_id}")
            return entry_id


async def get_ledger_entry(entry_id: str) -> dict | None:
    """Get ledger entry with lines"""
    async with get_connection() as conn:
        entry = await conn.fetchrow("SELECT * FROM ledger_entries WHERE id = $1", entry_id)
        if not entry:
            return None

        lines = await conn.fetch("SELECT * FROM ledger_lines WHERE entry_id = $1 ORDER BY line_order", entry_id)

        result = dict(entry)
        result["lines"] = [dict(line) for line in lines]
        return result


# =============================================================================
# Audit Operations
# =============================================================================


async def log_audit(
    action: str,
    entity_type: str,
    entity_id: str,
    company_id: str = "default",
    user_id: str | None = None,
    job_id: str | None = None,
    old_value: dict | None = None,
    new_value: dict | None = None,
):
    """Log an audit event"""
    async with get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO audit_logs (company_id, user_id, job_id, action, entity_type, entity_id, old_value, new_value)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """,
            company_id,
            user_id,
            job_id,
            action,
            entity_type,
            entity_id,
            old_value,
            new_value,
        )


# =============================================================================
# LLM Log Operations
# =============================================================================


async def log_llm_call(
    request_id: str,
    latency_ms: float,
    status: str,
    job_id: str | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    error_message: str | None = None,
):
    """Log LLM API call"""
    async with get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO llm_call_logs (request_id, job_id, llm_provider, model, prompt_tokens, completion_tokens, latency_ms, status, error_message)
            VALUES ($1, $2, 'do_agent', 'qwen3-32b', $3, $4, $5, $6, $7)
            """,
            request_id,
            job_id,
            prompt_tokens,
            completion_tokens,
            latency_ms,
            status,
            error_message,
        )
        logger.info(
            f"llm_provider=do_agent model=qwen3-32b request_id={request_id} latency_ms={latency_ms:.0f} status={status}"
        )


# =============================================================================
# Chart of Accounts Operations
# =============================================================================


async def get_chart_of_accounts(company_id: str = "default") -> list[dict]:
    """Get chart of accounts for a company"""
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT account_code, account_name, account_type, is_active
            FROM chart_of_accounts
            WHERE company_id = $1 AND is_active = TRUE
            ORDER BY account_code
            """,
            company_id,
        )
        return [dict(row) for row in rows]


async def validate_account_code(account_code: str, company_id: str = "default") -> bool:
    """Validate account code exists in chart of accounts"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT 1 FROM chart_of_accounts
            WHERE company_id = $1 AND account_code = $2 AND is_active = TRUE
            """,
            company_id,
            account_code,
        )
        return row is not None


__all__ = [
    "get_pool",
    "close_pool",
    "get_connection",
    "init_schema",
    "create_job",
    "get_job",
    "update_job_status",
    "get_jobs_by_status",
    "get_recent_jobs",
    "post_ledger_entry",
    "get_ledger_entry",
    "log_audit",
    "log_llm_call",
    "get_chart_of_accounts",
    "validate_account_code",
]
