"""
Data Analyst API Routes - NL2SQL
================================
Natural language to SQL translation for accounting data queries.

Endpoints:
- POST /analyst/query - Execute NL query
- GET /analyst/history - Get query history
- POST /analyst/history/{id}/favorite - Toggle favorite
"""

import json
import logging
import os
import re
import time
import uuid
from datetime import datetime
from typing import Any, Optional

import requests
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.config import settings
from src.db import get_pool

logger = logging.getLogger("analyst-routes")

router = APIRouter(prefix="/analyst", tags=["Data Analyst"])


# ===== Pydantic Models =====

class NLQueryRequest(BaseModel):
    """Natural language query request"""
    question: str


class QueryResult(BaseModel):
    """Query execution result"""
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int
    execution_time_ms: int
    sql: str


class QueryHistoryItem(BaseModel):
    """Query history item"""
    id: str
    question: str
    sql: str
    created_at: str
    is_favorite: bool
    row_count: Optional[int] = None


# ===== Database Schema for Query History =====

SCHEMA_CONTEXT = """
Database schema for ERP-AI accounting system (PostgreSQL):

Tables:
1. extracted_invoices - Parsed invoice data (PRIMARY for financial queries)
   - id (uuid), document_id (uuid), job_id (uuid), tenant_id (uuid)
   - vendor_name (varchar 255), vendor_tax_id (varchar 50)
   - invoice_number (varchar 100), invoice_date (date), due_date (date)
   - subtotal (numeric 18,2), tax_amount (numeric 18,2), total_amount (numeric 18,2)
   - currency (varchar 10, default VND), line_items (jsonb)
   - raw_text (text), ocr_confidence (numeric), ai_confidence (numeric)
   - extracted_by (varchar 100), created_at, updated_at

2. documents - Uploaded document files
   - id (uuid), tenant_id (uuid), job_id (varchar), filename (varchar)
   - content_type (varchar), file_size (bigint), file_path (varchar)
   - status (varchar: pending/processing/completed/failed)
   - doc_type (varchar: invoice/payment/receipt/contract/other)
   - extracted_data (jsonb), raw_text (text)
   - created_at, updated_at

3. ledger_entries - Posted journal entries
   - id (uuid), document_id (uuid ref), tenant_id
   - entry_date, description, status (draft/posted/reversed)
   - debit_total, credit_total, created_by
   - created_at

4. ledger_lines - Individual debit/credit lines
   - id (uuid), entry_id (ref), account_code, account_name
   - debit_amount, credit_amount, description

5. approvals - Approval records
   - id (uuid), document_id (uuid ref), proposal_id
   - status (pending/approved/rejected), approver, comment
   - created_at, approved_at

6. journal_proposals - Proposed journal entries (pending approval)
   - id (uuid), document_id (uuid ref), invoice_id (uuid ref)
   - journal_type, debit_account, credit_account
   - amount (numeric), description
   - status (pending/approved/rejected)
   - created_at

IMPORTANT: For revenue/amount queries, use extracted_invoices table with:
  total_amount, subtotal, tax_amount columns directly (NOT jsonb)

Common Vietnamese accounting terms:
- Doanh thu = Revenue (TK 511)
- Chi phí = Expense (TK 6xx)
- Hóa đơn = Invoice
- Nhà cung cấp = Vendor/Supplier
- Bút toán = Journal entry
- Tài khoản = Account
- Tổng tiền = total_amount
- Thuế = tax_amount
"""

def _extract_cte_names(sql: str) -> set[str]:
    names: set[str] = set()
    for match in re.finditer(r'\bWITH\s+([a-zA-Z0-9_]+)\s+AS\b', sql, re.IGNORECASE):
        names.add(match.group(1))
    for match in re.finditer(r',\s*([a-zA-Z0-9_]+)\s+AS\b', sql, re.IGNORECASE):
        names.add(match.group(1))
    return names


def _extract_table_names(sql: str) -> list[str]:
    tables: list[str] = []
    for match in re.finditer(r'\b(FROM|JOIN)\s+([a-zA-Z0-9_."`]+)', sql, re.IGNORECASE):
        token = match.group(2).strip()
        if token.startswith("("):
            continue
        token = token.strip('`"')
        token = token.split()[0]
        token = token.split(".")[-1]
        tables.append(token)
    return tables


def _enforce_sql_guard(sql: str, allowed_tables: set[str], limit: int) -> tuple[str, Optional[str]]:
    sql_upper = sql.strip().upper()
    if not (sql_upper.startswith("SELECT") or sql_upper.startswith("WITH")):
        return sql, "Only SELECT queries are allowed"
    dangerous = ["DROP", "DELETE", "UPDATE", "INSERT", "TRUNCATE", "ALTER", "CREATE", "GRANT", "REVOKE"]
    for kw in dangerous:
        if re.search(rf'\b{kw}\b', sql_upper):
            return sql, f"Query contains forbidden keyword: {kw}"
    ctes = _extract_cte_names(sql)
    tables = [t for t in _extract_table_names(sql) if t not in ctes]
    for table in tables:
        if table not in allowed_tables:
            return sql, f"Table not allowed for analytics: {table}"
    if "LIMIT" not in sql_upper:
        sql = f"{sql.rstrip(';')} LIMIT {limit}"
    return sql, None


# ===== NL2SQL Translation =====

def translate_nl_to_sql(question: str) -> str:
    """
    Translate natural language question to SQL using LLM.
    Falls back to pattern matching if LLM unavailable.
    """
    if settings.DO_AGENT_KEY and settings.DO_AGENT_URL:
        try:
            return _translate_with_llm(question)
        except Exception as e:
            logger.error(f"LLM translation failed: {e}")
    
    # Fallback to pattern matching
    return _translate_with_patterns(question)


def _translate_with_llm(question: str) -> str:
    """Use LLM for NL2SQL translation"""
    headers = {
        "Authorization": f"Bearer {settings.DO_AGENT_KEY}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "model": settings.DO_AGENT_MODEL,
        "messages": [
            {
                "role": "system",
                "content": f"""You are a SQL expert for Vietnamese accounting systems.
Convert natural language questions to PostgreSQL queries.

{SCHEMA_CONTEXT}

Rules:
1. Return ONLY the SQL query, no explanations or markdown
2. Use Vietnamese column aliases when appropriate
3. Always limit results to 1000 rows max
4. Use proper date handling for Vietnamese formats
5. Handle NULL values gracefully with COALESCE
6. For aggregate queries, include appropriate GROUP BY
7. For revenue/amount queries, ALWAYS use extracted_invoices table
8. Use total_amount, subtotal, tax_amount columns directly from extracted_invoices
"""
            },
            {
                "role": "user",
                "content": f"Convert this question to SQL: {question}"
            }
        ],
        "temperature": 0.1,
        "max_tokens": 500,
    }
    
    response = requests.post(
        f"{settings.DO_AGENT_URL}/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    
    result = response.json()
    sql = result["choices"][0]["message"]["content"].strip()
    
    # Clean up SQL (remove markdown code blocks if present)
    if sql.startswith("```"):
        sql = sql.split("```")[1]
        if sql.startswith("sql"):
            sql = sql[3:]
    sql = sql.strip()
    
    # Remove any trailing markdown
    if "```" in sql:
        sql = sql.split("```")[0].strip()
    
    # Basic SQL injection prevention
    sql_lower = sql.lower()
    dangerous = ["drop", "delete", "truncate", "update", "insert", "alter", "create"]
    if any(d in sql_lower for d in dangerous):
        raise ValueError("Query contains potentially dangerous operations")
    
    return sql


def _translate_with_patterns(question: str) -> str:
    """Pattern-based NL2SQL fallback"""
    q = question.lower()
    
    # Revenue queries - use extracted_invoices
    if "doanh thu" in q or "tổng tiền" in q or "total" in q or "revenue" in q:
        if "tháng này" in q or "thang nay" in q or "this month" in q:
            return """
                SELECT COALESCE(SUM(total_amount), 0) as "Tổng doanh thu",
                       COUNT(*) as "Số hóa đơn",
                       COALESCE(SUM(tax_amount), 0) as "Tổng thuế"
                FROM extracted_invoices
                WHERE invoice_date >= date_trunc('month', CURRENT_DATE)
            """
        if "năm nay" in q or "nam nay" in q or "this year" in q:
            return """
                SELECT COALESCE(SUM(total_amount), 0) as "Tổng doanh thu",
                       COUNT(*) as "Số hóa đơn",
                       COALESCE(SUM(tax_amount), 0) as "Tổng thuế"
                FROM extracted_invoices
                WHERE invoice_date >= date_trunc('year', CURRENT_DATE)
            """
        # Default revenue query
        return """
            SELECT COALESCE(SUM(total_amount), 0) as "Tổng doanh thu",
                   COUNT(*) as "Số hóa đơn",
                   COALESCE(SUM(tax_amount), 0) as "Tổng thuế"
            FROM extracted_invoices
        """
    
    # Top vendors - use extracted_invoices
    if "nhà cung cấp" in q or "nha cung cap" in q or "vendor" in q:
        if "top" in q or "cao nhất" in q or "lớn nhất" in q:
            return """
                SELECT vendor_name as "Nhà cung cấp", 
                       COUNT(*) as "Số hóa đơn",
                       SUM(total_amount) as "Tổng tiền"
                FROM extracted_invoices
                WHERE vendor_name IS NOT NULL
                GROUP BY vendor_name
                ORDER BY SUM(total_amount) DESC NULLS LAST
                LIMIT 10
            """
    
    # Invoice counts
    if "hóa đơn" in q or "hoa don" in q or "invoice" in q:
        if "chưa" in q or "pending" in q or "chờ" in q:
            return """
                SELECT status as "Trạng thái", COUNT(*) as "Số lượng"
                FROM documents
                WHERE doc_type = 'invoice' AND status NOT IN ('completed', 'failed')
                GROUP BY status
            """
        # List recent invoices
        return """
            SELECT ei.invoice_number as "Số HĐ",
                   ei.vendor_name as "Nhà cung cấp",
                   ei.invoice_date as "Ngày HĐ",
                   ei.total_amount as "Tổng tiền",
                   ei.currency as "Tiền tệ"
            FROM extracted_invoices ei
            ORDER BY ei.created_at DESC
            LIMIT 20
        """
    
    # Journal entries
    if "bút toán" in q or "but toan" in q or "journal" in q:
        if "tuần" in q or "tuan" in q or "week" in q:
            return """
                SELECT le.entry_date as "Ngày", le.description as "Mô tả",
                       le.debit_total as "Nợ", le.credit_total as "Có",
                       le.status as "Trạng thái"
                FROM ledger_entries le
                WHERE le.entry_date >= CURRENT_DATE - INTERVAL '7 days'
                ORDER BY le.entry_date DESC
                LIMIT 50
            """
        return """
            SELECT le.entry_date as "Ngày", le.description as "Mô tả",
                   le.debit_total as "Nợ", le.credit_total as "Có",
                   le.status as "Trạng thái"
            FROM ledger_entries le
            ORDER BY le.entry_date DESC
            LIMIT 20
        """
    
    # Approval status
    if "duyệt" in q or "duyet" in q or "approval" in q:
        return """
            SELECT a.status as "Trạng thái",
                   COUNT(*) as "Số lượng"
            FROM approvals a
            GROUP BY a.status
            ORDER BY COUNT(*) DESC
        """
    
    # Default: show recent invoices from extracted_invoices
    return """
        SELECT ei.invoice_number as "Số HĐ",
               ei.vendor_name as "Nhà cung cấp",
               ei.invoice_date as "Ngày HĐ",
               ei.total_amount as "Tổng tiền",
               d.filename as "Tên file",
               d.status as "Trạng thái"
        FROM extracted_invoices ei
        LEFT JOIN documents d ON ei.document_id = d.id
        ORDER BY ei.created_at DESC
        LIMIT 20
    """


# ===== API Endpoints =====

@router.post("/query", response_model=QueryResult)
async def execute_nl_query(request: NLQueryRequest, pool=Depends(get_pool)):
    """
    Execute natural language query.
    Translates NL to SQL and executes against the database.
    """
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question is required")
    
    if len(question) > 500:
        raise HTTPException(status_code=400, detail="Question too long (max 500 chars)")
    
    start_time = time.time()
    
    try:
        # Translate to SQL
        sql = translate_nl_to_sql(question)
        logger.info(f"NL2SQL: '{question[:50]}...' -> {sql[:100]}...")

        max_limit = 1000
        allowed_tables = {
            "extracted_invoices",
            "documents",
            "ledger_entries",
            "ledger_lines",
            "approvals",
            "journal_proposals",
        }
        sql, guard_error = _enforce_sql_guard(sql, allowed_tables, max_limit)
        if guard_error:
            raise HTTPException(status_code=400, detail=guard_error)
        
        # Execute query
        async with pool.acquire() as conn:
            # Save to history first
            history_id = str(uuid.uuid4())
            try:
                await conn.execute("""
                    INSERT INTO query_history (id, question, sql, created_at)
                    VALUES ($1, $2, $3, $4)
                """, history_id, question, sql, datetime.utcnow())
            except Exception:
                pass  # History table might not exist
            
            # Execute the query
            timeout_ms = int(os.getenv("ANALYTICS_QUERY_TIMEOUT_MS", "30000"))
            async with conn.transaction():
                await conn.execute(f"SET LOCAL statement_timeout = {timeout_ms}")
                rows = await conn.fetch(sql)
            
            # Convert to dict
            if rows:
                columns = list(rows[0].keys())
                data = [dict(row) for row in rows]
            else:
                columns = []
                data = []
        
        execution_time = int((time.time() - start_time) * 1000)
        
        # Audit log (best-effort)
        try:
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO audit_events (entity_type, entity_id, action, actor, details, created_at)
                    VALUES ('analytics_query', $1, 'executed', 'analyst', $2, NOW())
                    """,
                    str(uuid.uuid4()),
                    {
                        "module": "analyst",
                        "row_count": len(data),
                        "execution_time_ms": execution_time,
                    }
                )
        except Exception:
            pass

        return QueryResult(
            columns=columns,
            rows=data,
            row_count=len(data),
            execution_time_ms=execution_time,
            sql=sql
        )
        
    except Exception as e:
        logger.error(f"Query execution failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/history", response_model=list[QueryHistoryItem])
async def get_query_history(limit: int = 50, pool=Depends(get_pool)):
    """Get query history for the current user"""
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT id, question, sql, created_at, 
                       COALESCE(is_favorite, false) as is_favorite,
                       row_count
                FROM query_history
                ORDER BY created_at DESC
                LIMIT $1
            """, limit)
            
            return [
                QueryHistoryItem(
                    id=str(row["id"]),
                    question=row["question"],
                    sql=row["sql"],
                    created_at=row["created_at"].isoformat(),
                    is_favorite=row["is_favorite"],
                    row_count=row.get("row_count")
                )
                for row in rows
            ]
    except Exception as e:
        logger.warning(f"Could not fetch history: {e}")
        return []


@router.post("/history/{history_id}/favorite")
async def toggle_favorite(history_id: str, pool=Depends(get_pool)):
    """Toggle favorite status for a history item"""
    try:
        async with pool.acquire() as conn:
            await conn.execute("""
                UPDATE query_history
                SET is_favorite = NOT COALESCE(is_favorite, false)
                WHERE id = $1
            """, history_id)
            return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
