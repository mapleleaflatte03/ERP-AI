"""
ERPX AI Accounting - Analyze Module Routes
==========================================
Unified analysis module combining:
- Data Analyst (NL2SQL)
- Reports (pre-built queries)
- Dataset Upload (CSV/XLSX)

Endpoints:
- POST /analyze/datasets/upload - Upload CSV/XLSX for analysis
- GET  /analyze/datasets - List datasets
- GET  /analyze/datasets/{id} - Get dataset details
- POST /analyze/query - NL2SQL query (supports datasets + extracted_invoices)
- GET  /analyze/reports - Pre-built report templates
- POST /analyze/reports/{name}/run - Run a pre-built report
"""

import io
import json
import logging
import os
import re
import sys
import uuid
from datetime import datetime
from typing import Any, List, Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analyze", tags=["Analyze"])


# =============================================================================
# Pydantic Models
# =============================================================================

class QueryRequest(BaseModel):
    """Natural language query request"""
    question: str
    dataset_id: Optional[str] = None  # If specified, query this dataset
    limit: int = 100


class QueryResponse(BaseModel):
    """Query response"""
    success: bool
    sql: Optional[str] = None
    results: List[dict] = []
    row_count: int = 0
    error: Optional[str] = None
    execution_time_ms: Optional[float] = None


# =============================================================================
# Helper Functions
# =============================================================================

async def get_db_pool():
    """Get database connection pool"""
    try:
        from src.db import get_pool
        return await get_pool()
    except Exception as e:
        logger.error(f"Failed to get DB pool: {e}")
        return None


def detect_column_types(df) -> list:
    """Detect column types from a DataFrame"""
    import pandas as pd
    
    columns = []
    for col in df.columns:
        dtype = str(df[col].dtype)
        sample_values = df[col].dropna().head(3).tolist()
        
        if 'int' in dtype or 'float' in dtype:
            col_type = 'numeric'
        elif 'datetime' in dtype:
            col_type = 'timestamp'
        elif 'date' in dtype:
            col_type = 'date'
        elif 'bool' in dtype:
            col_type = 'boolean'
        else:
            col_type = 'text'
        
        columns.append({
            "name": str(col),
            "type": col_type,
            "dtype": dtype,
            "nullable": bool(df[col].isna().any()),
            "sample_values": [str(v) for v in sample_values]
        })
    
    return columns


def sanitize_table_name(name: str) -> str:
    """Create a safe table name from dataset name"""
    import re
    # Remove special chars, replace spaces with underscores
    safe = re.sub(r'[^a-zA-Z0-9_]', '_', name.lower())
    # Ensure it starts with a letter
    if safe and safe[0].isdigit():
        safe = 'ds_' + safe
    return safe[:60]  # PostgreSQL limit


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


# =============================================================================
# Dataset Upload & Management
# =============================================================================

@router.post("/datasets/upload")
async def upload_dataset(
    file: UploadFile = File(...),
    name: str = Form(None),
    description: str = Form(None)
):
    """
    Upload a CSV or XLSX file as a dataset for analysis.
    
    The file will be:
    1. Stored in MinIO
    2. Schema detected (columns, types)
    3. Available for NL2SQL queries
    """
    import pandas as pd
    from src.storage import upload_document_v2
    
    # Validate file type
    filename = file.filename or "dataset"
    if not filename.endswith(('.csv', '.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Only CSV and Excel files are supported")
    
    # Read file content
    content = await file.read()
    file_size = len(content)
    
    # Parse file
    try:
        if filename.endswith('.csv'):
            df = pd.read_csv(io.BytesIO(content))
            content_type = 'text/csv'
        else:
            df = pd.read_excel(io.BytesIO(content))
            content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse file: {str(e)}")
    
    # Detect schema
    columns = detect_column_types(df)
    row_count = len(df)
    
    # Generate safe table name
    dataset_name = name or filename.rsplit('.', 1)[0]
    table_name = sanitize_table_name(dataset_name)
    
    # Upload to MinIO
    dataset_id = str(uuid.uuid4())
    bucket = os.getenv("MINIO_BUCKET", "erpx-documents")
    key = f"datasets/{dataset_id}/{filename}"
    
    try:
        # upload_document_v2 takes (file_data, filename, content_type, tenant_id, job_id)
        upload_document_v2(content, filename, content_type, "default", dataset_id)
    except Exception as e:
        logger.error(f"Failed to upload to MinIO: {e}")
        raise HTTPException(status_code=500, detail="Failed to store file")
    
    # Save to database
    pool = await get_db_pool()
    if not pool:
        raise HTTPException(status_code=503, detail="Database unavailable")
    
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO datasets 
            (id, name, description, filename, content_type, file_size, 
             minio_bucket, minio_key, columns, row_count, table_name, status)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, 'ready')
            RETURNING *
            """,
            dataset_id,
            dataset_name,
            description,
            filename,
            content_type,
            file_size,
            bucket,
            key,
            json.dumps(columns),
            row_count,
            table_name
        )
        
        # Audit logging skipped (schema mismatch)
    
    return {
        "success": True,
        "dataset": {
            "id": dataset_id,
            "name": dataset_name,
            "filename": filename,
            "row_count": row_count,
            "columns": columns,
            "table_name": table_name,
            "status": "ready"
        },
        "message": f"Dataset uploaded successfully with {row_count} rows and {len(columns)} columns"
    }


@router.get("/datasets")
async def list_datasets(
    status: str = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0)
) -> dict:
    """List all datasets"""
    pool = await get_db_pool()
    if not pool:
        raise HTTPException(status_code=503, detail="Database unavailable")
    
    async with pool.acquire() as conn:
        if status:
            rows = await conn.fetch(
                """
                SELECT id, name, description, filename, row_count, status, 
                       columns, table_name, created_at
                FROM datasets
                WHERE status = $1
                ORDER BY created_at DESC
                LIMIT $2 OFFSET $3
                """,
                status, limit, offset
            )
        else:
            rows = await conn.fetch(
                """
                SELECT id, name, description, filename, row_count, status,
                       columns, table_name, created_at
                FROM datasets
                ORDER BY created_at DESC
                LIMIT $1 OFFSET $2
                """,
                limit, offset
            )
        
        datasets = []
        for row in rows:
            datasets.append({
                "id": str(row["id"]),
                "name": row["name"],
                "description": row.get("description"),
                "filename": row.get("filename"),
                "row_count": row.get("row_count", 0),
                "column_count": len(row.get("columns") or []),
                "status": row.get("status"),
                "table_name": row.get("table_name"),
                "created_at": row["created_at"].isoformat() if row.get("created_at") else None
            })
        
        # Get total count
        count_row = await conn.fetchrow("SELECT COUNT(*) as total FROM datasets")
        total = count_row["total"] if count_row else 0
        
        return {
            "datasets": datasets,
            "total": total,
            "limit": limit,
            "offset": offset
        }


@router.get("/datasets/{dataset_id}")
async def get_dataset(dataset_id: str) -> dict:
    """Get dataset details including schema"""
    pool = await get_db_pool()
    if not pool:
        raise HTTPException(status_code=503, detail="Database unavailable")
    
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, name, description, filename, content_type, file_size,
                   row_count, columns, table_name, status, error_message,
                   created_at, updated_at
            FROM datasets
            WHERE id = $1
            """,
            dataset_id
        )
        
        if not row:
            raise HTTPException(status_code=404, detail="Dataset not found")
        
        return {
            "id": str(row["id"]),
            "name": row["name"],
            "description": row.get("description"),
            "filename": row.get("filename"),
            "content_type": row.get("content_type"),
            "file_size": row.get("file_size"),
            "row_count": row.get("row_count", 0),
            "columns": row.get("columns") or [],
            "table_name": row.get("table_name"),
            "status": row.get("status"),
            "error_message": row.get("error_message"),
            "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
            "updated_at": row["updated_at"].isoformat() if row.get("updated_at") else None
        }


@router.delete("/datasets/{dataset_id}")
async def delete_dataset(dataset_id: str) -> dict:
    """Delete a dataset"""
    pool = await get_db_pool()
    if not pool:
        raise HTTPException(status_code=503, detail="Database unavailable")
    
    async with pool.acquire() as conn:
        # Get dataset info first
        row = await conn.fetchrow(
            "SELECT id, name, minio_bucket, minio_key FROM datasets WHERE id = $1",
            dataset_id
        )
        
        if not row:
            raise HTTPException(status_code=404, detail="Dataset not found")
        
        # Delete from MinIO
        try:
            from src.storage import delete_document
            if row.get("minio_bucket") and row.get("minio_key"):
                delete_document(row["minio_bucket"], row["minio_key"])
        except Exception as e:
            logger.warning(f"Failed to delete from MinIO: {e}")
        
        # Delete from database
        await conn.execute("DELETE FROM datasets WHERE id = $1", dataset_id)
        
        # Audit logging skipped (schema mismatch)
        
        return {"success": True, "message": "Dataset deleted"}


@router.get("/datasets/{dataset_id}/preview")
async def preview_dataset(
    dataset_id: str,
    limit: int = Query(200, ge=1, le=1000)
) -> dict:
    """Preview dataset rows (up to 200 by default)"""
    pool = await get_db_pool()
    if not pool:
        raise HTTPException(status_code=503, detail="Database unavailable")
    
    async with pool.acquire() as conn:
        # Get dataset metadata
        row = await conn.fetchrow(
            "SELECT table_name, columns, row_count FROM datasets WHERE id = $1",
            dataset_id
        )
        if not row:
            raise HTTPException(status_code=404, detail="Dataset not found")
        
        table_name = row.get("table_name")
        if not table_name:
            raise HTTPException(status_code=400, detail="Dataset not loaded into database")
        
        # Fetch preview rows
        try:
            data = await conn.fetch(f'SELECT * FROM "{table_name}" LIMIT {limit}')
            rows = [dict(r) for r in data]
            return {
                "dataset_id": dataset_id,
                "columns": row.get("columns") or [],
                "total_rows": row.get("row_count", 0),
                "preview_rows": len(rows),
                "data": rows
            }
        except Exception as e:
            logger.error(f"Preview query failed: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to preview: {str(e)}")


@router.post("/datasets/{dataset_id}/clean")
async def clean_dataset(dataset_id: str) -> dict:
    """Clean dataset: strip whitespace, normalize headers, parse dates, handle nulls"""
    pool = await get_db_pool()
    if not pool:
        raise HTTPException(status_code=503, detail="Database unavailable")
    
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT table_name, columns, status FROM datasets WHERE id = $1",
            dataset_id
        )
        if not row:
            raise HTTPException(status_code=404, detail="Dataset not found")
        
        table_name = row.get("table_name")
        if not table_name:
            raise HTTPException(status_code=400, detail="Dataset not loaded into database")
        
        # Already cleaned?
        if row.get("status") == "cleaned":
            return {"success": True, "message": "Dataset already cleaned", "status": "cleaned"}
        
        try:
            # Load into pandas for cleaning
            import pandas as pd
            data = await conn.fetch(f'SELECT * FROM "{table_name}"')
            df = pd.DataFrame([dict(r) for r in data])
            
            # Clean operations
            original_rows = len(df)
            
            # 1. Strip whitespace from string columns
            for col in df.select_dtypes(include=['object']).columns:
                df[col] = df[col].astype(str).str.strip().replace('nan', None)
            
            # 2. Drop all-null rows
            df = df.dropna(how='all')
            
            # 3. Parse datetime candidates
            for col in df.columns:
                if df[col].dtype == 'object':
                    try:
                        parsed = pd.to_datetime(df[col], errors='coerce', dayfirst=True)
                        if parsed.notna().sum() > len(df) * 0.5:  # >50% valid dates
                            df[col] = parsed
                    except:
                        pass
            
            # 4. Numeric coercion for numeric-looking columns
            for col in df.select_dtypes(include=['object']).columns:
                try:
                    numeric = pd.to_numeric(df[col].str.replace(',', ''), errors='coerce')
                    if numeric.notna().sum() > len(df) * 0.5:
                        df[col] = numeric
                except:
                    pass
            
            cleaned_rows = len(df)
            
            # Recreate table with cleaned data
            await conn.execute(f'DROP TABLE IF EXISTS "{table_name}"')
            
            # Create table from cleaned df
            columns_sql = []
            for col in df.columns:
                dtype = df[col].dtype
                if pd.api.types.is_integer_dtype(dtype):
                    col_type = "BIGINT"
                elif pd.api.types.is_float_dtype(dtype):
                    col_type = "DOUBLE PRECISION"
                elif pd.api.types.is_datetime64_any_dtype(dtype):
                    col_type = "TIMESTAMP"
                else:
                    col_type = "TEXT"
                columns_sql.append(f'"{col}" {col_type}')
            
            create_sql = f'CREATE TABLE "{table_name}" ({", ".join(columns_sql)})'
            await conn.execute(create_sql)
            
            # Insert cleaned data
            if len(df) > 0:
                cols = ', '.join([f'"{c}"' for c in df.columns])
                placeholders = ', '.join([f'${i+1}' for i in range(len(df.columns))])
                insert_sql = f'INSERT INTO "{table_name}" ({cols}) VALUES ({placeholders})'
                
                for _, row_data in df.iterrows():
                    values = [
                        v.isoformat() if hasattr(v, 'isoformat') else (None if pd.isna(v) else v)
                        for v in row_data.values
                    ]
                    await conn.execute(insert_sql, *values)
            
            # Update dataset status
            new_columns = [{"name": c, "type": str(df[c].dtype)} for c in df.columns]
            await conn.execute(
                """
                UPDATE datasets 
                SET status = 'cleaned', row_count = $2, columns = $3, updated_at = NOW()
                WHERE id = $1
                """,
                dataset_id, cleaned_rows, json.dumps(new_columns)
            )
            
            return {
                "success": True,
                "message": "Dataset cleaned successfully",
                "status": "cleaned",
                "original_rows": original_rows,
                "cleaned_rows": cleaned_rows,
                "rows_removed": original_rows - cleaned_rows
            }
            
        except Exception as e:
            logger.error(f"Clean failed: {e}")
            raise HTTPException(status_code=500, detail=f"Clean failed: {str(e)}")


@router.get("/datasets/{dataset_id}/export")
async def export_dataset(dataset_id: str) -> dict:
    """Export dataset as downloadable CSV"""
    from fastapi.responses import StreamingResponse
    
    pool = await get_db_pool()
    if not pool:
        raise HTTPException(status_code=503, detail="Database unavailable")
    
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT table_name, name FROM datasets WHERE id = $1",
            dataset_id
        )
        if not row:
            raise HTTPException(status_code=404, detail="Dataset not found")
        
        table_name = row.get("table_name")
        if not table_name:
            raise HTTPException(status_code=400, detail="Dataset not loaded into database")
        
        try:
            import pandas as pd
            data = await conn.fetch(f'SELECT * FROM "{table_name}"')
            df = pd.DataFrame([dict(r) for r in data])
            
            # Convert to CSV
            csv_buffer = io.StringIO()
            df.to_csv(csv_buffer, index=False)
            csv_buffer.seek(0)
            
            filename = f"{row.get('name', 'dataset')}_{dataset_id[:8]}.csv"
            
            return StreamingResponse(
                iter([csv_buffer.getvalue()]),
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )
        except Exception as e:
            logger.error(f"Export failed: {e}")
            raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


# =============================================================================
# NL2SQL Query (unified across datasets and extracted_invoices)
# =============================================================================

@router.post("/query")
async def run_analysis_query(request: QueryRequest) -> dict:
    """
    Run a natural language query against datasets or extracted_invoices.
    
    If dataset_id is provided, queries that specific dataset.
    Otherwise, queries the default extracted_invoices table.
    """
    import time
    from services.llm.do_agent import DoAgentClient
    
    pool = await get_db_pool()
    if not pool:
        raise HTTPException(status_code=503, detail="Database unavailable")
    
    start_time = time.time()
    
    max_limit = min(max(request.limit, 1), 1000)

    # Build schema context
    async with pool.acquire() as conn:
        if request.dataset_id:
            # Query specific dataset - load from file
            dataset = await conn.fetchrow(
                "SELECT * FROM datasets WHERE id = $1 AND status = 'ready'",
                request.dataset_id
            )
            if not dataset:
                raise HTTPException(status_code=404, detail="Dataset not found or not ready")
            
            schema_info = f"""
Dataset: {dataset['name']}
Table: {dataset['table_name']}
Columns: {json.dumps(dataset['columns'], indent=2)}
Row count: {dataset['row_count']}
"""
            # For datasets, we need to load data into a temp table
            # For now, use the extracted_invoices as the default
            table_name = "extracted_invoices"  # Fallback for now
        else:
            # Default: query extracted_invoices
            schema = await conn.fetch("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'extracted_invoices'
                ORDER BY ordinal_position
            """)
            schema_info = "Table: extracted_invoices\nColumns:\n"
            for col in schema:
                schema_info += f"  - {col['column_name']}: {col['data_type']}\n"
            
            # Get sample data
            sample = await conn.fetch(
                "SELECT * FROM extracted_invoices LIMIT 3"
            )
            if sample:
                schema_info += "\nSample data (first 3 rows):\n"
                for row in sample:
                    schema_info += f"  {dict(row)}\n"
            
            table_name = "extracted_invoices"
    
    # Generate SQL using LLM
    llm = DoAgentClient()
    
    prompt = f"""You are a SQL expert. Convert the following natural language question to a PostgreSQL query.

Schema:
{schema_info}

Question: {request.question}

Rules:
1. Return ONLY the SQL query, no explanation
2. Use proper PostgreSQL syntax
3. Limit results to {max_limit} rows
4. For Vietnamese text, use ILIKE for case-insensitive search
5. Format dates properly (YYYY-MM-DD)
6. Use aggregate functions (SUM, COUNT, AVG) when appropriate
7. Do NOT use DROP, DELETE, UPDATE, INSERT, or any data modification statements

SQL:"""

    try:
        sql_response = await llm.generate(prompt, max_tokens=500)
        sql = sql_response.strip()
        
        # Clean up SQL
        sql = sql.replace("```sql", "").replace("```", "").strip()
        if sql.lower().startswith("sql:"):
            sql = sql[4:].strip()
        
        allowed_tables = {
            "extracted_invoices",
            "documents",
            "approvals",
            "journal_proposals",
            "datasets",
            "vendors",
            "accounts",
            "ledger_entries",
            "ledger_lines",
            "journal_entries",
            table_name,
        }
        sql, guard_error = _enforce_sql_guard(sql, allowed_tables, max_limit)
        if guard_error:
            raise HTTPException(status_code=400, detail=guard_error)
        
        # Execute query
        timeout_ms = int(os.getenv("ANALYTICS_QUERY_TIMEOUT_MS", "30000"))
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(f"SET LOCAL statement_timeout = {timeout_ms}")
                rows = await conn.fetch(sql)
                results = [dict(row) for row in rows]
            
            # Convert special types to strings
            for row in results:
                for key, value in row.items():
                    if isinstance(value, (datetime,)):
                        row[key] = value.isoformat()
                    elif hasattr(value, '__str__') and not isinstance(value, (str, int, float, bool, type(None))):
                        row[key] = str(value)
        
        execution_time = (time.time() - start_time) * 1000
        
        # Audit log (best-effort)
        try:
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO audit_events (entity_type, entity_id, action, actor, details, created_at)
                    VALUES ('analytics_query', $1, 'executed', 'analyze', $2, NOW())
                    """,
                    str(uuid.uuid4()),
                    {
                        "module": "analyze",
                        "dataset_id": request.dataset_id,
                        "row_count": len(results),
                        "execution_time_ms": round(execution_time, 2),
                    }
                )
        except Exception:
            pass
        
        return {
            "success": True,
            "sql": sql,
            "results": results,
            "row_count": len(results),
            "execution_time_ms": round(execution_time, 2)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Query failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "sql": sql if 'sql' in locals() else None
        }


# =============================================================================
# Pre-built Reports
# =============================================================================

REPORT_TEMPLATES = {
    "monthly_summary": {
        "name": "Monthly Summary",
        "description": "Total invoices and amounts by month",
        "sql": """
            SELECT 
                DATE_TRUNC('month', invoice_date) as month,
                COUNT(*) as invoice_count,
                SUM(total_amount) as total_amount,
                SUM(tax_amount) as total_tax,
                AVG(total_amount) as avg_amount
            FROM extracted_invoices
            WHERE invoice_date IS NOT NULL
            GROUP BY DATE_TRUNC('month', invoice_date)
            ORDER BY month DESC
        """
    },
    "vendor_summary": {
        "name": "Vendor Summary",
        "description": "Total amounts by vendor",
        "sql": """
            SELECT 
                vendor_name,
                vendor_tax_id,
                COUNT(*) as invoice_count,
                SUM(total_amount) as total_amount,
                MIN(invoice_date) as first_invoice,
                MAX(invoice_date) as last_invoice
            FROM extracted_invoices
            WHERE vendor_name IS NOT NULL
            GROUP BY vendor_name, vendor_tax_id
            ORDER BY total_amount DESC
            LIMIT 50
        """
    },
    "high_value_invoices": {
        "name": "High Value Invoices",
        "description": "Invoices above 10M VND",
        "sql": """
            SELECT 
                invoice_number, vendor_name, invoice_date, 
                total_amount, tax_amount, currency
            FROM extracted_invoices
            WHERE total_amount > 10000000
            ORDER BY total_amount DESC
            LIMIT 100
        """
    },
    "recent_invoices": {
        "name": "Recent Invoices",
        "description": "Last 30 days of invoices",
        "sql": """
            SELECT 
                invoice_number, vendor_name, invoice_date, 
                total_amount, currency, created_at
            FROM extracted_invoices
            WHERE created_at > NOW() - INTERVAL '30 days'
            ORDER BY created_at DESC
            LIMIT 100
        """
    },
    "approval_status": {
        "name": "Approval Status",
        "description": "Document approval statistics",
        "sql": """
            SELECT 
                a.status,
                COUNT(*) as count,
                SUM(ei.total_amount) as total_amount
            FROM approvals a
            LEFT JOIN extracted_invoices ei ON ei.document_id::text = a.job_id::text
            GROUP BY a.status
            ORDER BY count DESC
        """
    }
}


@router.get("/reports")
async def list_reports() -> dict:
    """List available pre-built reports"""
    reports = []
    for key, template in REPORT_TEMPLATES.items():
        reports.append({
            "id": key,
            "name": template["name"],
            "description": template["description"]
        })
    
    return {"reports": reports}


@router.post("/reports/{report_id}/run")
async def run_report(report_id: str) -> dict:
    """Run a pre-built report"""
    import time
    
    if report_id not in REPORT_TEMPLATES:
        raise HTTPException(status_code=404, detail="Report not found")
    
    template = REPORT_TEMPLATES[report_id]
    sql = template["sql"]
    
    pool = await get_db_pool()
    if not pool:
        raise HTTPException(status_code=503, detail="Database unavailable")
    
    start_time = time.time()
    
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(sql)
            results = [dict(row) for row in rows]
            
            # Convert special types
            for row in results:
                for key, value in row.items():
                    if isinstance(value, datetime):
                        row[key] = value.isoformat()
                    elif hasattr(value, '__str__') and not isinstance(value, (str, int, float, bool, type(None))):
                        row[key] = str(value)
        
        execution_time = (time.time() - start_time) * 1000
        
        return {
            "success": True,
            "report": {
                "id": report_id,
                "name": template["name"],
                "description": template["description"]
            },
            "results": results,
            "row_count": len(results),
            "execution_time_ms": round(execution_time, 2)
        }
        
    except Exception as e:
        logger.error(f"Report failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }
