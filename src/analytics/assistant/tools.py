"""
AI Assistant Tools for Analytics
"""
import logging
import json
import re
import uuid
from typing import Any, Dict, List, Optional

from ..connectors import PostgresConnector, DatasetConnector, QueryResult
from ..engine import NL2SQLEngine, Forecaster, Aggregator
from ..core.config import get_config
from ..core.exceptions import ToolExecutionError

logger = logging.getLogger(__name__)


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


# Tool definitions for OpenAI function calling
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "query_data",
            "description": "Execute a natural language query against the database. Use this to answer questions about invoices, vendors, amounts, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "The question to answer, e.g., 'Total revenue this month' or 'Top 10 vendors by amount'"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of rows to return",
                        "default": 100
                    }
                },
                "required": ["question"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_kpis",
            "description": "Get KPI dashboard metrics like total revenue, invoice count, average values, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "kpis": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of KPIs to retrieve. Available: total_revenue, invoice_count, avg_invoice_value, vendor_count, pending_approvals, processed_documents"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_forecast",
            "description": "Generate a forecast for a metric. Useful for predicting future revenue, invoice counts, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "metric": {
                        "type": "string",
                        "enum": ["revenue", "invoice_count", "avg_invoice_value"],
                        "description": "The metric to forecast"
                    },
                    "horizon": {
                        "type": "integer",
                        "description": "Number of days to forecast (default: 30)",
                        "default": 30
                    },
                    "model": {
                        "type": "string",
                        "enum": ["prophet", "linear"],
                        "description": "Forecasting model to use",
                        "default": "linear"
                    }
                },
                "required": ["metric"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_tables",
            "description": "List all available database tables and datasets",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "describe_table",
            "description": "Get detailed schema and sample data for a specific table",
            "parameters": {
                "type": "object",
                "properties": {
                    "table_name": {
                        "type": "string",
                        "description": "Name of the table to describe"
                    }
                },
                "required": ["table_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_monthly_summary",
            "description": "Get monthly summary of revenue, invoice counts, and vendor metrics",
            "parameters": {
                "type": "object",
                "properties": {
                    "months": {
                        "type": "integer",
                        "description": "Number of months to include (default: 6)",
                        "default": 6
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_top_vendors",
            "description": "Get top vendors ranked by total invoice amount",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Number of vendors to return (default: 10)",
                        "default": 10
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_sql",
            "description": "Execute a raw SQL query. Only SELECT queries are allowed. Use this when you need precise control over the query.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "The SQL query to execute (SELECT only)"
                    }
                },
                "required": ["sql"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_visualization",
            "description": "Create a visualization configuration for the data. Returns a chart config that can be rendered by the UI.",
            "parameters": {
                "type": "object",
                "properties": {
                    "chart_type": {
                        "type": "string",
                        "enum": ["bar", "line", "pie", "area", "scatter"],
                        "description": "Type of chart"
                    },
                    "title": {
                        "type": "string",
                        "description": "Chart title"
                    },
                    "data": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "Data to visualize"
                    },
                    "x_field": {
                        "type": "string",
                        "description": "Field for X axis"
                    },
                    "y_field": {
                        "type": "string",
                        "description": "Field for Y axis"
                    },
                    "color_field": {
                        "type": "string",
                        "description": "Optional field for color grouping"
                    }
                },
                "required": ["chart_type", "title", "data", "x_field", "y_field"]
            }
        }
    }
]


class ToolExecutor:
    """
    Executes AI assistant tools.
    """
    
    def __init__(self):
        self._pg_connector = PostgresConnector()
        self._dataset_connector = DatasetConnector()
        self._nl2sql = NL2SQLEngine(self._pg_connector)
        self._forecaster = Forecaster(self._pg_connector)
        self._aggregator = Aggregator(self._pg_connector)
    
    async def execute(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool by name with given arguments"""
        tool_handlers = {
            "query_data": self._query_data,
            "get_kpis": self._get_kpis,
            "run_forecast": self._run_forecast,
            "list_tables": self._list_tables,
            "describe_table": self._describe_table,
            "get_monthly_summary": self._get_monthly_summary,
            "get_top_vendors": self._get_top_vendors,
            "execute_sql": self._execute_sql,
            "create_visualization": self._create_visualization,
        }
        
        handler = tool_handlers.get(tool_name)
        if not handler:
            raise ToolExecutionError(f"Unknown tool: {tool_name}")
        
        try:
            return await handler(**arguments)
        except Exception as e:
            logger.error(f"Tool {tool_name} failed: {e}")
            return {"error": str(e)}
    
    async def _query_data(self, question: str, limit: int = 100) -> Dict[str, Any]:
        """Execute natural language query"""
        result = await self._nl2sql.query(question, execute=True, limit=limit)
        return result.to_dict()
    
    async def _get_kpis(self, kpis: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get KPI dashboard"""
        dashboard = await self._aggregator.get_kpi_dashboard(kpis)
        return dashboard.to_dict()
    
    async def _run_forecast(
        self, 
        metric: str, 
        horizon: int = 30,
        model: str = "linear"
    ) -> Dict[str, Any]:
        """Run forecasting"""
        result = await self._forecaster.forecast(
            metric=metric,
            horizon=horizon,
            model=model
        )
        return result.to_dict()
    
    async def _list_tables(self) -> Dict[str, Any]:
        """List available tables"""
        await self._pg_connector.connect()
        tables = await self._pg_connector.get_analytics_tables()
        
        return {
            "tables": [
                {
                    "name": t.name,
                    "schema": t.schema,
                    "row_count": t.row_count,
                    "column_count": len(t.columns)
                }
                for t in tables
            ]
        }
    
    async def _describe_table(self, table_name: str) -> Dict[str, Any]:
        """Get table details"""
        await self._pg_connector.connect()
        table = await self._pg_connector.get_table_schema(table_name)
        
        if not table:
            return {"error": f"Table not found: {table_name}"}
        
        # Get sample data
        sample = await self._pg_connector.get_sample_data(table_name, limit=5)
        
        return {
            "name": table.name,
            "schema": table.schema,
            "row_count": table.row_count,
            "columns": [
                {
                    "name": c.name,
                    "type": c.data_type,
                    "nullable": c.nullable,
                    "sample_values": c.sample_values
                }
                for c in table.columns
            ],
            "sample_data": sample.rows if sample.success else []
        }
    
    async def _get_monthly_summary(self, months: int = 6) -> Dict[str, Any]:
        """Get monthly summary"""
        result = await self._aggregator.get_monthly_summary(months)
        return {
            "columns": result.columns,
            "rows": result.rows,
            "row_count": result.row_count
        }
    
    async def _get_top_vendors(self, limit: int = 10) -> Dict[str, Any]:
        """Get top vendors"""
        result = await self._aggregator.get_top_vendors(limit)
        return {
            "columns": result.columns,
            "rows": result.rows,
            "row_count": result.row_count
        }
    
    async def _execute_sql(self, sql: str) -> Dict[str, Any]:
        """Execute raw SQL"""
        await self._pg_connector.connect()
        config = get_config()
        tables = await self._pg_connector.get_analytics_tables()
        allowed_tables = {t.name for t in tables}
        sql, guard_error = _enforce_sql_guard(sql, allowed_tables, config.max_query_rows)
        if guard_error:
            raise ToolExecutionError(guard_error)
        result = await self._pg_connector.execute_query(sql)

        # Audit log (best-effort)
        try:
            if self._pg_connector._pool:
                async with self._pg_connector._pool.acquire() as conn:
                    await conn.execute(
                        """
                        INSERT INTO audit_events (entity_type, entity_id, action, actor, details, created_at)
                        VALUES ('analytics_query', $1, 'executed', 'assistant', $2, NOW())
                        """,
                        str(uuid.uuid4()),
                        {
                            "module": "analytics_assistant",
                            "row_count": result.row_count,
                            "sql": result.sql,
                        }
                    )
        except Exception:
            pass

        return result.to_dict()
    
    async def _create_visualization(
        self,
        chart_type: str,
        title: str,
        data: List[Dict],
        x_field: str,
        y_field: str,
        color_field: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create visualization config"""
        return {
            "type": "chart",
            "config": {
                "chart_type": chart_type,
                "title": title,
                "data": data,
                "x_field": x_field,
                "y_field": y_field,
                "color_field": color_field
            }
        }
    
    def get_tool_definitions(self) -> List[Dict]:
        """Get tool definitions for OpenAI"""
        return TOOL_DEFINITIONS
