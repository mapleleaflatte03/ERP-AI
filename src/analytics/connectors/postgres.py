"""
PostgreSQL Data Connector
"""
import asyncio
import time
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, date
from decimal import Decimal
import asyncpg

from .base import BaseConnector, ColumnInfo, TableInfo, QueryResult
from ..core.config import get_config, DatabaseConfig
from ..core.exceptions import ConnectorError, QueryError

logger = logging.getLogger(__name__)


class PostgresConnector(BaseConnector):
    """PostgreSQL database connector"""
    
    def __init__(self, config: Optional[DatabaseConfig] = None):
        self._config = config or get_config().database
        self._pool: Optional[asyncpg.Pool] = None
        self._connected = False
    
    @property
    def name(self) -> str:
        return "postgresql"
    
    @property
    def connector_type(self) -> str:
        return "database"
    
    async def connect(self) -> bool:
        """Establish connection pool"""
        if self._pool is not None:
            return True
        
        try:
            self._pool = await asyncpg.create_pool(
                host=self._config.host,
                port=self._config.port,
                database=self._config.database,
                user=self._config.user,
                password=self._config.password,
                min_size=2,
                max_size=10,
                command_timeout=get_config().query_timeout_seconds
            )
            self._connected = True
            logger.info(f"Connected to PostgreSQL: {self._config.database}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            raise ConnectorError(f"Failed to connect: {e}")
    
    async def disconnect(self) -> None:
        """Close connection pool"""
        if self._pool:
            await self._pool.close()
            self._pool = None
            self._connected = False
            logger.info("Disconnected from PostgreSQL")
    
    async def is_connected(self) -> bool:
        """Check connection status"""
        if not self._pool:
            return False
        try:
            async with self._pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return True
        except:
            return False
    
    def _serialize_value(self, value: Any) -> Any:
        """Convert database values to JSON-serializable format"""
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, date):
            return value.isoformat()
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, (list, tuple)):
            return [self._serialize_value(v) for v in value]
        if isinstance(value, dict):
            return {k: self._serialize_value(v) for k, v in value.items()}
        return value
    
    async def execute_query(self, sql: str, params: Optional[List] = None) -> QueryResult:
        """Execute a SQL query"""
        if not self._pool:
            await self.connect()
        
        start_time = time.time()
        
        # Security check - only allow SELECT
        sql_upper = sql.strip().upper()
        if not sql_upper.startswith("SELECT") and not sql_upper.startswith("WITH"):
            return QueryResult(
                columns=[],
                rows=[],
                row_count=0,
                execution_time_ms=0,
                sql=sql,
                error="Only SELECT queries are allowed"
            )
        
        # Block dangerous keywords
        dangerous = ["DROP", "DELETE", "UPDATE", "INSERT", "TRUNCATE", "ALTER", "CREATE", "GRANT", "REVOKE"]
        for kw in dangerous:
            if kw in sql_upper:
                return QueryResult(
                    columns=[],
                    rows=[],
                    row_count=0,
                    execution_time_ms=0,
                    sql=sql,
                    error=f"Query contains forbidden keyword: {kw}"
                )
        
        try:
            timeout_ms = int(get_config().query_timeout_seconds * 1000)
            async with self._pool.acquire() as conn:
                async with conn.transaction():
                    await conn.execute(f"SET LOCAL statement_timeout = {timeout_ms}")
                    if params:
                        rows = await conn.fetch(sql, *params)
                    else:
                        rows = await conn.fetch(sql)
                
                execution_time = (time.time() - start_time) * 1000
                
                if not rows:
                    return QueryResult(
                        columns=[],
                        rows=[],
                        row_count=0,
                        execution_time_ms=execution_time,
                        sql=sql
                    )
                
                columns = list(rows[0].keys())
                result_rows = [
                    {k: self._serialize_value(v) for k, v in dict(row).items()}
                    for row in rows
                ]
                
                return QueryResult(
                    columns=columns,
                    rows=result_rows,
                    row_count=len(result_rows),
                    execution_time_ms=round(execution_time, 2),
                    sql=sql
                )
                
        except asyncpg.PostgresError as e:
            execution_time = (time.time() - start_time) * 1000
            logger.error(f"Query error: {e}")
            return QueryResult(
                columns=[],
                rows=[],
                row_count=0,
                execution_time_ms=round(execution_time, 2),
                sql=sql,
                error=str(e)
            )
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            logger.error(f"Unexpected query error: {e}")
            return QueryResult(
                columns=[],
                rows=[],
                row_count=0,
                execution_time_ms=round(execution_time, 2),
                sql=sql,
                error=f"Query failed: {str(e)}"
            )
    
    async def get_tables(self) -> List[TableInfo]:
        """List all tables in the database"""
        if not self._pool:
            await self.connect()
        
        sql = """
            SELECT 
                table_schema,
                table_name,
                obj_description((quote_ident(table_schema) || '.' || quote_ident(table_name))::regclass) as description
            FROM information_schema.tables 
            WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
              AND table_type = 'BASE TABLE'
            ORDER BY table_schema, table_name
        """
        
        result = await self.execute_query(sql)
        tables = []
        
        for row in result.rows:
            tables.append(TableInfo(
                name=row["table_name"],
                schema=row["table_schema"],
                description=row.get("description")
            ))
        
        return tables
    
    async def get_table_schema(self, table_name: str, schema: str = "public") -> Optional[TableInfo]:
        """Get detailed schema for a table"""
        if not self._pool:
            await self.connect()
        
        # Get columns
        sql = """
            SELECT 
                column_name,
                data_type,
                is_nullable,
                column_default,
                character_maximum_length
            FROM information_schema.columns
            WHERE table_schema = $1 AND table_name = $2
            ORDER BY ordinal_position
        """
        
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(sql, schema, table_name)
        
        if not rows:
            return None
        
        columns = []
        for row in rows:
            data_type = row["data_type"]
            if row.get("character_maximum_length"):
                data_type = f"{data_type}({row['character_maximum_length']})"
            
            columns.append(ColumnInfo(
                name=row["column_name"],
                data_type=data_type,
                nullable=row["is_nullable"] == "YES"
            ))
        
        # Get row count
        count_result = await self.execute_query(f'SELECT COUNT(*) as cnt FROM "{schema}"."{table_name}"')
        row_count = count_result.rows[0]["cnt"] if count_result.rows else 0
        
        # Get sample values for each column
        sample_result = await self.execute_query(f'SELECT * FROM "{schema}"."{table_name}" LIMIT 3')
        if sample_result.rows:
            for col in columns:
                col.sample_values = [row.get(col.name) for row in sample_result.rows[:3]]
        
        return TableInfo(
            name=table_name,
            schema=schema,
            columns=columns,
            row_count=row_count
        )
    
    async def get_analytics_tables(self) -> List[TableInfo]:
        """Get tables commonly used for analytics"""
        priority_tables = [
            "extracted_invoices",
            "journal_entries", 
            "accounts",
            "documents",
            "vendors",
            "approvals",
            "datasets"
        ]
        
        all_tables = await self.get_tables()
        analytics_tables = []
        
        # First add priority tables in order
        for pt in priority_tables:
            for t in all_tables:
                if t.name == pt:
                    schema = await self.get_table_schema(t.name, t.schema)
                    if schema:
                        analytics_tables.append(schema)
                    break
        
        return analytics_tables
    
    async def get_schema_summary(self) -> str:
        """Get a summary of database schema for LLM context"""
        tables = await self.get_analytics_tables()
        return self.get_schema_context(tables)
