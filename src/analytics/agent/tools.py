"""
Agent Tools
Register all available tools for the analytics agent
"""
import pandas as pd
from typing import Any, Dict, List, Optional
import logging

from ..core.registry import tool, get_registry
from ..connectors.dataset import DatasetConnector
from ..connectors.postgres import PostgresConnector
from ..quality.validator import DataValidator
from ..forecast.models import ProphetForecaster, LinearForecaster

logger = logging.getLogger(__name__)

# Shared connectors
_dataset_connector: Optional[DatasetConnector] = None
_postgres_connector: Optional[PostgresConnector] = None


async def get_dataset_connector() -> DatasetConnector:
    """Get or create dataset connector"""
    global _dataset_connector
    if _dataset_connector is None:
        _dataset_connector = DatasetConnector()
        await _dataset_connector.connect()
    return _dataset_connector


async def get_postgres_connector() -> PostgresConnector:
    """Get or create postgres connector"""
    global _postgres_connector
    if _postgres_connector is None:
        _postgres_connector = PostgresConnector()
        await _postgres_connector.connect()
    return _postgres_connector


# =============================================================================
# DATA TOOLS
# =============================================================================

@tool(
    description="Liệt kê tất cả datasets có sẵn trong hệ thống với số lượng rows và columns",
    category="data",
    examples=["list_datasets()"]
)
async def list_datasets() -> Dict[str, Any]:
    """List all available datasets"""
    connector = await get_dataset_connector()
    datasets = await connector.list_datasets()
    
    return {
        "success": True,
        "count": len(datasets),
        "datasets": [
            {
                "name": ds["name"],
                "rows": ds["row_count"],
                "columns": ds["column_count"],
                "column_names": ds["columns"][:5],
            }
            for ds in datasets
        ],
    }


@tool(
    description="Load một dataset vào bộ nhớ để xử lý. Cần gọi trước khi phân tích",
    category="data",
    examples=["load_dataset(dataset_name='FPT Stock Data')"]
)
async def load_dataset(dataset_name: str) -> Dict[str, Any]:
    """Load a dataset into memory"""
    connector = await get_dataset_connector()
    
    try:
        df = await connector.load_dataset(dataset_name)
        return {
            "success": True,
            "dataset": dataset_name,
            "rows": len(df),
            "columns": list(df.columns),
            "dtypes": {col: str(df[col].dtype) for col in df.columns},
            "memory_mb": round(df.memory_usage(deep=True).sum() / 1024 / 1024, 2),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@tool(
    description="Xem thống kê mô tả của dataset: mean, min, max, std, etc.",
    category="data",
    examples=["describe_dataset(dataset_name='FPT Stock Data')"]
)
async def describe_dataset(dataset_name: str) -> Dict[str, Any]:
    """Get statistical description of a dataset"""
    connector = await get_dataset_connector()
    
    try:
        description = await connector.describe_dataset(dataset_name)
        return {
            "success": True,
            **description,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@tool(
    description="Lấy mẫu n dòng dữ liệu từ dataset để xem preview",
    category="data",
    examples=["get_sample(dataset_name='FPT Stock Data', n=5)"]
)
async def get_sample(dataset_name: str, n: int = 10) -> Dict[str, Any]:
    """Get sample rows from a dataset"""
    connector = await get_dataset_connector()
    
    try:
        result = await connector.get_sample(dataset_name, n=min(n, 20))
        return {
            "success": True,
            "dataset": dataset_name,
            "sample_size": result.row_count,
            "columns": result.columns,
            "rows": result.data.to_dict(orient="records"),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@tool(
    description="Lọc dữ liệu theo điều kiện. Operators: =, !=, >, <, >=, <=, contains",
    category="data",
    examples=["filter_data(dataset_name='FPT Stock Data', column='Close', operator='>', value=100)"]
)
async def filter_data(
    dataset_name: str, 
    column: str, 
    operator: str, 
    value: Any
) -> Dict[str, Any]:
    """Filter dataset by condition"""
    connector = await get_dataset_connector()
    
    try:
        df = await connector.load_dataset(dataset_name)
        
        if column not in df.columns:
            return {"success": False, "error": f"Column '{column}' not found"}
        
        # Apply filter
        if operator == "=":
            mask = df[column] == value
        elif operator == "!=":
            mask = df[column] != value
        elif operator == ">":
            mask = df[column] > float(value)
        elif operator == "<":
            mask = df[column] < float(value)
        elif operator == ">=":
            mask = df[column] >= float(value)
        elif operator == "<=":
            mask = df[column] <= float(value)
        elif operator == "contains":
            mask = df[column].astype(str).str.contains(str(value), case=False)
        else:
            return {"success": False, "error": f"Unknown operator: {operator}"}
        
        filtered = df[mask]
        
        return {
            "success": True,
            "original_rows": len(df),
            "filtered_rows": len(filtered),
            "filter": f"{column} {operator} {value}",
            "sample": filtered.head(10).to_dict(orient="records"),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@tool(
    description="Tính toán aggregate: sum, mean, count, min, max. Có thể group by",
    category="data",
    examples=["aggregate_data(dataset_name='FPT', agg_column='Volume', agg_func='sum', group_by='Ticker')"]
)
async def aggregate_data(
    dataset_name: str,
    agg_column: str,
    agg_func: str = "sum",
    group_by: str = None,
) -> Dict[str, Any]:
    """Aggregate data with optional grouping"""
    connector = await get_dataset_connector()
    
    try:
        df = await connector.load_dataset(dataset_name)
        
        if agg_column not in df.columns:
            return {"success": False, "error": f"Column '{agg_column}' not found"}
        
        valid_funcs = ["sum", "mean", "count", "min", "max", "std"]
        if agg_func not in valid_funcs:
            return {"success": False, "error": f"Invalid function. Use: {valid_funcs}"}
        
        if group_by:
            if group_by not in df.columns:
                return {"success": False, "error": f"Group column '{group_by}' not found"}
            
            result = df.groupby(group_by)[agg_column].agg(agg_func).reset_index()
            result.columns = [group_by, f"{agg_func}_{agg_column}"]
            
            return {
                "success": True,
                "aggregation": f"{agg_func}({agg_column}) GROUP BY {group_by}",
                "result": result.to_dict(orient="records"),
            }
        else:
            value = getattr(df[agg_column], agg_func)()
            return {
                "success": True,
                "aggregation": f"{agg_func}({agg_column})",
                "result": float(value) if hasattr(value, '__float__') else value,
            }
    except Exception as e:
        return {"success": False, "error": str(e)}


# =============================================================================
# DATABASE TOOLS
# =============================================================================

@tool(
    description="Liệt kê các bảng trong database với số lượng rows",
    category="database",
    examples=["list_tables()"]
)
async def list_tables() -> Dict[str, Any]:
    """List database tables"""
    connector = await get_postgres_connector()
    
    try:
        tables = await connector.get_tables()
        return {
            "success": True,
            "count": len(tables),
            "tables": [
                {
                    "name": t.name,
                    "rows": t.row_count,
                    "columns": len(t.columns),
                }
                for t in tables
            ],
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@tool(
    description="Thực thi SQL query trực tiếp trên database",
    category="database",
    examples=["execute_query(sql='SELECT * FROM invoices LIMIT 10')"]
)
async def execute_query(sql: str) -> Dict[str, Any]:
    """Execute SQL query"""
    connector = await get_postgres_connector()
    
    # Safety check - only allow SELECT
    sql_upper = sql.strip().upper()
    if not sql_upper.startswith("SELECT"):
        return {"success": False, "error": "Only SELECT queries are allowed"}
    
    try:
        result = await connector.execute(sql)
        return {
            "success": True,
            "rows": result.row_count,
            "columns": result.columns,
            "data": result.data.head(100).to_dict(orient="records"),
            "execution_time_ms": result.execution_time_ms,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# =============================================================================
# FORECAST TOOLS
# =============================================================================

@tool(
    description="Dự báo xu hướng cho dataset có cột ngày và cột giá trị số",
    category="forecast",
    examples=["forecast(dataset_name='FPT Stock Data', date_column='Date', value_column='Close', periods=30)"]
)
async def forecast(
    dataset_name: str,
    date_column: str,
    value_column: str,
    periods: int = 30,
    model: str = "linear",
) -> Dict[str, Any]:
    """Generate forecast for time series data"""
    connector = await get_dataset_connector()
    
    try:
        df = await connector.load_dataset(dataset_name)
        
        if date_column not in df.columns:
            return {"success": False, "error": f"Date column '{date_column}' not found"}
        if value_column not in df.columns:
            return {"success": False, "error": f"Value column '{value_column}' not found"}
        
        # Select forecaster
        if model == "prophet":
            try:
                forecaster = ProphetForecaster()
            except ImportError:
                forecaster = LinearForecaster()
        else:
            forecaster = LinearForecaster()
        
        # Fit and predict
        result = forecaster.fit_predict(df, date_column, value_column, periods)
        
        return {
            "success": True,
            "model": result.model_name,
            "periods": periods,
            "metrics": result.metrics,
            "forecast": result.forecast.to_dict(orient="records"),
            "summary": result.summary(),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# =============================================================================
# QUALITY TOOLS
# =============================================================================

@tool(
    description="Kiểm tra chất lượng dữ liệu của dataset",
    category="quality",
    examples=["validate_data(dataset_name='FPT Stock Data')"]
)
async def validate_data(dataset_name: str) -> Dict[str, Any]:
    """Validate data quality of a dataset"""
    connector = await get_dataset_connector()
    
    try:
        df = await connector.load_dataset(dataset_name)
        
        # Create validator with basic rules
        validator = DataValidator(dataset_name)
        
        # Add checks for each column
        for col in df.columns:
            validator.expect_column_to_exist(col)
            validator.expect_column_values_not_null(col, threshold=0.5)  # Allow up to 50% nulls
        
        # Run validation
        suite = validator.validate(df)
        
        return {
            "success": True,
            "dataset": dataset_name,
            "validation_passed": suite.success,
            "passed_rules": suite.passed_count,
            "failed_rules": suite.failed_count,
            "details": [r.to_dict() for r in suite.results if not r.success],
            "statistics": suite.statistics,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# =============================================================================
# VISUALIZATION TOOLS
# =============================================================================

@tool(
    description="Tạo dữ liệu cho biểu đồ. Chart types: line, bar, scatter, pie",
    category="visualization",
    examples=["create_chart(dataset_name='FPT Stock Data', chart_type='line', x_column='Date', y_column='Close')"]
)
async def create_chart(
    dataset_name: str,
    chart_type: str,
    x_column: str,
    y_column: str,
    title: str = None,
) -> Dict[str, Any]:
    """Create chart data for visualization"""
    connector = await get_dataset_connector()
    
    try:
        df = await connector.load_dataset(dataset_name)
        
        if x_column not in df.columns:
            return {"success": False, "error": f"X column '{x_column}' not found"}
        if y_column not in df.columns:
            return {"success": False, "error": f"Y column '{y_column}' not found"}
        
        valid_types = ["line", "bar", "scatter", "pie", "area"]
        if chart_type not in valid_types:
            return {"success": False, "error": f"Invalid chart type. Use: {valid_types}"}
        
        # Prepare data (limit to 500 points for performance)
        chart_df = df[[x_column, y_column]].dropna().head(500)
        
        return {
            "success": True,
            "chart": {
                "type": chart_type,
                "title": title or f"{y_column} by {x_column}",
                "x_label": x_column,
                "y_label": y_column,
                "data": {
                    "x": chart_df[x_column].tolist(),
                    "y": chart_df[y_column].tolist(),
                },
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def register_all_tools():
    """Register all tools with the global registry"""
    # Tools are automatically registered via @tool decorator
    registry = get_registry()
    logger.info(f"Registered {len(registry.list_tools())} analytics tools")
    return registry


# Auto-register on import
register_all_tools()
