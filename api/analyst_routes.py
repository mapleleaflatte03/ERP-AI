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
1. documents - Uploaded accounting documents (main source)
   - id (uuid), tenant_id (uuid), job_id (varchar), filename (varchar)
   - content_type (varchar), file_size (bigint), status (varchar)
   - doc_type (varchar: invoice/payment/receipt/contract/other)
   - extracted_data (jsonb: contains invoice_no, invoice_date, vendor_name, total_amount, etc)
   - created_at, updated_at

2. ledger_entries - Posted journal entries
   - id (uuid), document_id (uuid ref), tenant_id
   - entry_date, description, status (draft/posted/reversed)
   - debit_total, credit_total, created_by
   - created_at

3. ledger_lines - Individual debit/credit lines
   - id (uuid), entry_id (ref), account_code, account_name
   - debit_amount, credit_amount, description

4. approvals - Approval records
   - id (uuid), document_id (uuid ref), proposal_id
   - status (pending/approved/rejected), approver, comment
   - created_at, approved_at

To get invoice fields from documents, use: 
  extracted_data->>'invoice_no' as invoice_no
  extracted_data->>'vendor_name' as vendor_name
  (extracted_data->>'total_amount')::numeric as total_amount

Common Vietnamese accounting terms:
- Doanh thu = Revenue (TK 511)
- Chi phí = Expense (TK 6xx)
- Hóa đơn = Invoice
- Nhà cung cấp = Vendor/Supplier
- Bút toán = Journal entry
- Tài khoản = Account
"""


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
1. Return ONLY the SQL query, no explanations
2. Use Vietnamese column aliases when appropriate
3. Always limit results to 1000 rows max
4. Use proper date handling for Vietnamese formats
5. Handle NULL values gracefully
6. For aggregate queries, include appropriate GROUP BY
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
    
    # Basic SQL injection prevention
    sql_lower = sql.lower()
    dangerous = ["drop", "delete", "truncate", "update", "insert", "alter", "create"]
    if any(d in sql_lower for d in dangerous):
        raise ValueError("Query contains potentially dangerous operations")
    
    return sql


def _translate_with_patterns(question: str) -> str:
    """Pattern-based NL2SQL fallback"""
    q = question.lower()
    
    # Revenue queries
    if "doanh thu" in q:
        if "tháng này" in q or "thang nay" in q:
            return """
                SELECT COALESCE(SUM(total_amount), 0) as "Tổng doanh thu"
                FROM documents
                WHERE invoice_date >= date_trunc('month', CURRENT_DATE)
                  AND status = 'approved'
            """
        if "năm nay" in q or "nam nay" in q:
            return """
                SELECT COALESCE(SUM(total_amount), 0) as "Tổng doanh thu"
                FROM documents
                WHERE invoice_date >= date_trunc('year', CURRENT_DATE)
                  AND status = 'approved'
            """
    
    # Top vendors
    if "nhà cung cấp" in q or "nha cung cap" in q:
        if "top" in q or "cao nhất" in q:
            return """
                SELECT vendor_name as "Nhà cung cấp", 
                       COUNT(*) as "Số hóa đơn",
                       SUM(total_amount) as "Tổng tiền"
                FROM documents
                WHERE vendor_name IS NOT NULL
                GROUP BY vendor_name
                ORDER BY SUM(total_amount) DESC
                LIMIT 10
            """
    
    # Invoice counts
    if "hóa đơn" in q or "hoa don" in q:
        if "chưa" in q or "pending" in q:
            return """
                SELECT status as "Trạng thái", COUNT(*) as "Số lượng"
                FROM documents
                WHERE status NOT IN ('approved', 'rejected')
                GROUP BY status
            """
    
    # Journal entries
    if "bút toán" in q or "but toan" in q:
        if "tuần" in q or "tuan" in q:
            return """
                SELECT je.entry_date as "Ngày", je.description as "Mô tả",
                       je.debit_total as "Nợ", je.credit_total as "Có"
                FROM journal_entries je
                WHERE je.entry_date >= CURRENT_DATE - INTERVAL '7 days'
                ORDER BY je.entry_date DESC
                LIMIT 50
            """
    
    # Default: show recent documents
    return """
        SELECT id, filename as "Tên file", doc_type as "Loại",
               extracted_data->>'vendor_name' as "NCC",
               status as "Trạng thái", created_at::date as "Ngày tạo"
        FROM documents
        ORDER BY created_at DESC
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
            rows = await conn.fetch(sql)
            
            # Convert to dict
            if rows:
                columns = list(rows[0].keys())
                data = [dict(row) for row in rows]
            else:
                columns = []
                data = []
        
        execution_time = int((time.time() - start_time) * 1000)
        
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
