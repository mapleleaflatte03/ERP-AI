"""
Analytics Module
================

A comprehensive analytics module for ERP-X providing:
- AI-powered chat assistant for data analysis
- Natural Language to SQL (NL2SQL) query engine  
- Time series forecasting (Prophet/sklearn)
- KPI aggregations and dashboards
- Dataset management (CSV/Excel upload)
- Data connectors (PostgreSQL, files)

Usage:
    from src.analytics import get_agent, NL2SQLEngine, Forecaster
    
    # Chat with AI assistant
    agent = get_agent()
    response = await agent.chat("What's the total revenue this month?")
    
    # Run NL2SQL query
    engine = NL2SQLEngine()
    result = await engine.query("Top 10 vendors by amount")
    
    # Generate forecast
    forecaster = Forecaster()
    forecast = await forecaster.forecast("revenue", horizon=30)
"""

from .core.config import get_config, AnalyticsConfig
from .core.exceptions import (
    AnalyticsError,
    ConnectorError, 
    QueryError,
    ForecastError,
    ToolExecutionError
)
from .connectors import (
    PostgresConnector,
    DatasetConnector,
    QueryResult,
    TableInfo,
    ColumnInfo
)
from .engine import (
    NL2SQLEngine,
    NL2SQLResult,
    Forecaster,
    ForecastResult,
    Aggregator,
    KPIDashboard
)
from .assistant import (
    AnalyticsAgent,
    AgentResponse,
    get_agent,
    ToolExecutor
)

__all__ = [
    # Config
    "get_config",
    "AnalyticsConfig",
    
    # Exceptions
    "AnalyticsError",
    "ConnectorError",
    "QueryError", 
    "ForecastError",
    "ToolExecutionError",
    
    # Connectors
    "PostgresConnector",
    "DatasetConnector",
    "QueryResult",
    "TableInfo",
    "ColumnInfo",
    
    # Engine
    "NL2SQLEngine",
    "NL2SQLResult",
    "Forecaster",
    "ForecastResult",
    "Aggregator",
    "KPIDashboard",
    
    # Assistant
    "AnalyticsAgent",
    "AgentResponse",
    "get_agent",
    "ToolExecutor"
]

__version__ = "2.0.0"
