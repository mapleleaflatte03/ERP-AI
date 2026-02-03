"""
Metric Aggregation Engine
"""
import logging
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass
from datetime import datetime, date, timedelta

from ..connectors import PostgresConnector, QueryResult
from ..core.exceptions import QueryError

logger = logging.getLogger(__name__)


@dataclass
class MetricValue:
    """A single metric value"""
    name: str
    value: Union[int, float, None]
    change: Optional[float] = None  # Percentage change from previous period
    change_direction: Optional[str] = None  # "up", "down", "stable"
    period: Optional[str] = None
    formatted: Optional[str] = None


@dataclass  
class KPIDashboard:
    """Collection of KPI metrics"""
    metrics: List[MetricValue]
    period: str
    generated_at: str
    
    def to_dict(self) -> dict:
        return {
            "metrics": [
                {
                    "name": m.name,
                    "value": m.value,
                    "change": m.change,
                    "change_direction": m.change_direction,
                    "formatted": m.formatted
                }
                for m in self.metrics
            ],
            "period": self.period,
            "generated_at": self.generated_at
        }


class Aggregator:
    """
    Metric aggregation engine for KPIs and summaries.
    """
    
    # Pre-defined KPI queries
    KPI_QUERIES = {
        "total_revenue": {
            "current": """
                SELECT COALESCE(SUM(total_amount), 0) as value
                FROM extracted_invoices
                WHERE invoice_date >= DATE_TRUNC('month', CURRENT_DATE)
            """,
            "previous": """
                SELECT COALESCE(SUM(total_amount), 0) as value
                FROM extracted_invoices
                WHERE invoice_date >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month')
                  AND invoice_date < DATE_TRUNC('month', CURRENT_DATE)
            """,
            "format": "currency"
        },
        "invoice_count": {
            "current": """
                SELECT COUNT(*) as value
                FROM extracted_invoices
                WHERE created_at >= DATE_TRUNC('month', CURRENT_DATE)
            """,
            "previous": """
                SELECT COUNT(*) as value
                FROM extracted_invoices
                WHERE created_at >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month')
                  AND created_at < DATE_TRUNC('month', CURRENT_DATE)
            """,
            "format": "number"
        },
        "avg_invoice_value": {
            "current": """
                SELECT COALESCE(AVG(total_amount), 0) as value
                FROM extracted_invoices
                WHERE invoice_date >= DATE_TRUNC('month', CURRENT_DATE)
                  AND total_amount > 0
            """,
            "previous": """
                SELECT COALESCE(AVG(total_amount), 0) as value
                FROM extracted_invoices
                WHERE invoice_date >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month')
                  AND invoice_date < DATE_TRUNC('month', CURRENT_DATE)
                  AND total_amount > 0
            """,
            "format": "currency"
        },
        "vendor_count": {
            "current": """
                SELECT COUNT(DISTINCT vendor_name) as value
                FROM extracted_invoices
                WHERE vendor_name IS NOT NULL
                  AND created_at >= DATE_TRUNC('month', CURRENT_DATE)
            """,
            "previous": """
                SELECT COUNT(DISTINCT vendor_name) as value
                FROM extracted_invoices
                WHERE vendor_name IS NOT NULL
                  AND created_at >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month')
                  AND created_at < DATE_TRUNC('month', CURRENT_DATE)
            """,
            "format": "number"
        },
        "pending_approvals": {
            "current": """
                SELECT COUNT(*) as value
                FROM approvals
                WHERE status = 'pending'
            """,
            "previous": None,
            "format": "number"
        },
        "processed_documents": {
            "current": """
                SELECT COUNT(*) as value
                FROM documents
                WHERE status = 'processed'
                  AND created_at >= DATE_TRUNC('month', CURRENT_DATE)
            """,
            "previous": """
                SELECT COUNT(*) as value
                FROM documents
                WHERE status = 'processed'
                  AND created_at >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month')
                  AND created_at < DATE_TRUNC('month', CURRENT_DATE)
            """,
            "format": "number"
        }
    }
    
    KPI_LABELS = {
        "total_revenue": "Tổng doanh thu",
        "invoice_count": "Số hóa đơn",
        "avg_invoice_value": "TB giá trị HĐ",
        "vendor_count": "Số NCC",
        "pending_approvals": "Chờ duyệt",
        "processed_documents": "Tài liệu xử lý"
    }
    
    def __init__(self, connector: Optional[PostgresConnector] = None):
        self._connector = connector or PostgresConnector()
    
    def _format_value(self, value: float, format_type: str) -> str:
        """Format a value for display"""
        if value is None:
            return "-"
        
        if format_type == "currency":
            if value >= 1_000_000_000:
                return f"{value/1_000_000_000:.1f}B"
            elif value >= 1_000_000:
                return f"{value/1_000_000:.1f}M"
            elif value >= 1_000:
                return f"{value/1_000:.1f}K"
            else:
                return f"{value:,.0f}"
        elif format_type == "percentage":
            return f"{value:.1f}%"
        else:
            return f"{value:,.0f}"
    
    def _calculate_change(self, current: float, previous: float) -> tuple[float, str]:
        """Calculate percentage change and direction"""
        if previous == 0:
            return 0.0, "stable"
        
        change = ((current - previous) / previous) * 100
        
        if change > 1:
            direction = "up"
        elif change < -1:
            direction = "down"
        else:
            direction = "stable"
        
        return round(change, 1), direction
    
    async def get_kpi(self, kpi_name: str) -> MetricValue:
        """Get a single KPI metric"""
        if kpi_name not in self.KPI_QUERIES:
            raise QueryError(f"Unknown KPI: {kpi_name}")
        
        await self._connector.connect()
        kpi = self.KPI_QUERIES[kpi_name]
        
        # Get current value
        result = await self._connector.execute_query(kpi["current"])
        current_value = result.rows[0]["value"] if result.rows else 0
        
        # Get previous value if available
        change = None
        direction = None
        if kpi.get("previous"):
            prev_result = await self._connector.execute_query(kpi["previous"])
            prev_value = prev_result.rows[0]["value"] if prev_result.rows else 0
            change, direction = self._calculate_change(current_value, prev_value)
        
        return MetricValue(
            name=self.KPI_LABELS.get(kpi_name, kpi_name),
            value=float(current_value) if current_value else 0,
            change=change,
            change_direction=direction,
            formatted=self._format_value(current_value, kpi["format"])
        )
    
    async def get_kpi_dashboard(self, kpis: Optional[List[str]] = None) -> KPIDashboard:
        """Get dashboard with multiple KPIs"""
        if kpis is None:
            kpis = ["total_revenue", "invoice_count", "avg_invoice_value", "vendor_count", "pending_approvals"]
        
        metrics = []
        for kpi_name in kpis:
            try:
                metric = await self.get_kpi(kpi_name)
                metrics.append(metric)
            except Exception as e:
                logger.error(f"Failed to get KPI {kpi_name}: {e}")
                metrics.append(MetricValue(
                    name=self.KPI_LABELS.get(kpi_name, kpi_name),
                    value=None,
                    formatted="-"
                ))
        
        return KPIDashboard(
            metrics=metrics,
            period="Tháng này",
            generated_at=datetime.now().isoformat()
        )
    
    async def aggregate(
        self,
        table: str,
        metrics: List[str],
        group_by: Optional[List[str]] = None,
        filters: Optional[Dict[str, Any]] = None,
        date_column: Optional[str] = None,
        date_range: Optional[tuple[str, str]] = None,
        limit: int = 100
    ) -> QueryResult:
        """
        Run custom aggregation query.
        
        Args:
            table: Table to aggregate from
            metrics: List of aggregations like "sum:total_amount", "count:*", "avg:value"
            group_by: Columns to group by
            filters: Column filters
            date_column: Column for date filtering
            date_range: Tuple of (start_date, end_date)
            limit: Max rows to return
        """
        # Build SELECT clause
        select_parts = []
        for metric in metrics:
            if ":" in metric:
                func, col = metric.split(":", 1)
                func = func.upper()
                if func in ["SUM", "COUNT", "AVG", "MIN", "MAX"]:
                    if col == "*":
                        select_parts.append(f"{func}(*) as {func.lower()}_all")
                    else:
                        select_parts.append(f"{func}({col}) as {func.lower()}_{col}")
        
        if group_by:
            select_parts = group_by + select_parts
        
        if not select_parts:
            raise QueryError("No valid metrics specified")
        
        # Build WHERE clause
        where_parts = []
        params = []
        param_idx = 1
        
        if filters:
            for col, value in filters.items():
                where_parts.append(f"{col} = ${param_idx}")
                params.append(value)
                param_idx += 1
        
        if date_column and date_range:
            start, end = date_range
            where_parts.append(f"{date_column} >= ${param_idx}")
            params.append(start)
            param_idx += 1
            where_parts.append(f"{date_column} <= ${param_idx}")
            params.append(end)
            param_idx += 1
        
        # Build query
        sql = f"SELECT {', '.join(select_parts)} FROM {table}"
        
        if where_parts:
            sql += f" WHERE {' AND '.join(where_parts)}"
        
        if group_by:
            sql += f" GROUP BY {', '.join(group_by)}"
            sql += f" ORDER BY {group_by[0]}"
        
        sql += f" LIMIT {limit}"
        
        await self._connector.connect()
        return await self._connector.execute_query(sql, params if params else None)
    
    async def get_monthly_summary(self, months: int = 6) -> QueryResult:
        """Get monthly summary for the last N months"""
        sql = f"""
            SELECT 
                DATE_TRUNC('month', invoice_date) as month,
                COUNT(*) as invoice_count,
                SUM(total_amount) as total_revenue,
                AVG(total_amount) as avg_invoice_value,
                COUNT(DISTINCT vendor_name) as vendor_count
            FROM extracted_invoices
            WHERE invoice_date >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '{months} months')
              AND invoice_date IS NOT NULL
            GROUP BY DATE_TRUNC('month', invoice_date)
            ORDER BY month DESC
        """
        
        await self._connector.connect()
        return await self._connector.execute_query(sql)
    
    async def get_top_vendors(self, limit: int = 10) -> QueryResult:
        """Get top vendors by total amount"""
        sql = f"""
            SELECT 
                vendor_name,
                COUNT(*) as invoice_count,
                SUM(total_amount) as total_amount,
                AVG(total_amount) as avg_amount,
                MIN(invoice_date) as first_invoice,
                MAX(invoice_date) as last_invoice
            FROM extracted_invoices
            WHERE vendor_name IS NOT NULL
            GROUP BY vendor_name
            ORDER BY total_amount DESC
            LIMIT {limit}
        """
        
        await self._connector.connect()
        return await self._connector.execute_query(sql)
