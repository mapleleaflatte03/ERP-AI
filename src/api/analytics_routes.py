"""
Analytics API Routes
=====================
New unified analytics API replacing the old analyze module.

Endpoints:
- POST /v1/analytics/chat - Chat with AI assistant
- GET  /v1/analytics/sessions - List conversation sessions
- GET  /v1/analytics/sessions/{id} - Get session history
- DELETE /v1/analytics/sessions/{id} - Delete session

- POST /v1/analytics/query - Execute NL2SQL query
- GET  /v1/analytics/schema - Get database schema
- POST /v1/analytics/datasets - Upload dataset
- GET  /v1/analytics/datasets - List datasets
- DELETE /v1/analytics/datasets/{id} - Delete dataset

- GET  /v1/analytics/kpis - Get KPI dashboard
- POST /v1/analytics/forecast - Run forecasting
- GET  /v1/analytics/monthly-summary - Get monthly summary
- GET  /v1/analytics/top-vendors - Get top vendors

- GET  /v1/analytics/reports - List report templates
- POST /v1/analytics/reports/{id}/run - Run a report
"""

import logging
import json
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, File, UploadFile, Form
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analytics", tags=["Analytics"])


# =============================================================================
# Request/Response Models
# =============================================================================

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    message: str
    tool_calls: Optional[List[dict]] = None
    tool_results: Optional[List[dict]] = None
    visualizations: Optional[List[dict]] = None
    session_id: str


class QueryRequest(BaseModel):
    question: str
    execute: bool = True
    limit: int = 100


class ForecastRequest(BaseModel):
    metric: str
    horizon: int = 30
    model: str = "linear"  # "prophet" or "linear"


# =============================================================================
# Chat / Assistant Endpoints
# =============================================================================

@router.post("/chat", response_model=ChatResponse)
async def chat_with_assistant(request: ChatRequest):
    """
    Chat with the analytics AI assistant.
    
    The assistant can:
    - Answer questions about your data
    - Generate reports and visualizations
    - Create forecasts
    - Execute queries
    """
    from src.analytics.assistant import get_agent
    
    try:
        agent = get_agent()
        response = await agent.chat(
            message=request.message,
            session_id=request.session_id
        )
        return ChatResponse(**response.to_dict())
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions")
async def list_sessions(limit: int = Query(20, ge=1, le=100)):
    """List recent conversation sessions"""
    from src.analytics.assistant import get_agent
    
    agent = get_agent()
    sessions = agent.list_sessions(limit)
    return {"sessions": sessions}


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """Get conversation history for a session"""
    from src.analytics.assistant import get_agent
    
    agent = get_agent()
    history = agent.get_session_history(session_id)
    
    if not history:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return history


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a conversation session"""
    from src.analytics.assistant import get_agent
    
    agent = get_agent()
    success = agent.clear_session(session_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {"success": True, "message": "Session deleted"}


# =============================================================================
# Query Endpoints
# =============================================================================

@router.post("/query")
async def run_query(request: QueryRequest):
    """
    Execute a natural language query.
    
    Converts the question to SQL and optionally executes it.
    """
    from src.analytics.engine import NL2SQLEngine
    
    try:
        engine = NL2SQLEngine()
        result = await engine.query(
            question=request.question,
            execute=request.execute,
            limit=request.limit
        )
        return result.to_dict()
    except Exception as e:
        logger.error(f"Query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/schema")
async def get_schema():
    """Get database schema information"""
    from src.analytics.connectors import PostgresConnector
    
    try:
        connector = PostgresConnector()
        await connector.connect()
        tables = await connector.get_analytics_tables()
        
        return {
            "tables": [
                {
                    "name": t.name,
                    "schema": t.schema,
                    "row_count": t.row_count,
                    "columns": [
                        {
                            "name": c.name,
                            "type": c.data_type,
                            "nullable": c.nullable
                        }
                        for c in t.columns
                    ]
                }
                for t in tables
            ]
        }
    except Exception as e:
        logger.error(f"Schema error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/suggest-queries")
async def suggest_queries():
    """Get suggested queries based on available data"""
    from src.analytics.engine import NL2SQLEngine
    
    try:
        engine = NL2SQLEngine()
        suggestions = await engine.suggest_queries()
        return {"suggestions": suggestions}
    except Exception as e:
        logger.error(f"Suggestion error: {e}")
        return {"suggestions": [
            "Tổng doanh thu theo tháng",
            "Top 10 nhà cung cấp theo số tiền",
            "Số lượng hóa đơn theo trạng thái"
        ]}


# =============================================================================
# Dataset Endpoints
# =============================================================================

@router.post("/datasets")
async def upload_dataset(
    file: UploadFile = File(...),
    name: str = Form(None),
    description: str = Form(None)
):
    """Upload a CSV or Excel file as a dataset"""
    from src.analytics.connectors import DatasetConnector
    
    filename = file.filename or "dataset"
    if not filename.endswith(('.csv', '.xlsx', '.xls')):
        raise HTTPException(
            status_code=400, 
            detail="Only CSV and Excel files are supported"
        )
    
    try:
        content = await file.read()
        connector = DatasetConnector()
        await connector.connect()
        
        result = await connector.upload_dataset(
            file_data=content,
            filename=filename,
            name=name,
            description=description
        )
        
        return {"success": True, "dataset": result}
    except Exception as e:
        logger.error(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/datasets")
async def list_datasets(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """List all datasets"""
    from src.analytics.connectors import DatasetConnector
    
    try:
        connector = DatasetConnector()
        await connector.connect()
        tables = await connector.get_tables()
        
        return {
            "datasets": [
                {
                    "name": t.name,
                    "row_count": t.row_count,
                    "column_count": len(t.columns),
                    "description": t.description
                }
                for t in tables
            ],
            "total": len(tables)
        }
    except Exception as e:
        logger.error(f"List datasets error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/datasets/{dataset_id}")
async def delete_dataset(dataset_id: str):
    """Delete a dataset"""
    from src.analytics.connectors import DatasetConnector
    
    try:
        connector = DatasetConnector()
        await connector.connect()
        success = await connector.delete_dataset(dataset_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Dataset not found")
        
        return {"success": True, "message": "Dataset deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete dataset error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# KPI & Aggregation Endpoints  
# =============================================================================

@router.get("/kpis")
async def get_kpis(
    kpis: Optional[str] = Query(None, description="Comma-separated KPI names")
):
    """
    Get KPI dashboard metrics.
    
    Available KPIs:
    - total_revenue
    - invoice_count
    - avg_invoice_value
    - vendor_count
    - pending_approvals
    - processed_documents
    """
    from src.analytics.engine import Aggregator
    
    try:
        aggregator = Aggregator()
        kpi_list = kpis.split(",") if kpis else None
        dashboard = await aggregator.get_kpi_dashboard(kpi_list)
        return dashboard.to_dict()
    except Exception as e:
        logger.error(f"KPI error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/monthly-summary")
async def get_monthly_summary(months: int = Query(6, ge=1, le=24)):
    """Get monthly summary for the last N months"""
    from src.analytics.engine import Aggregator
    
    try:
        aggregator = Aggregator()
        result = await aggregator.get_monthly_summary(months)
        return {
            "columns": result.columns,
            "rows": result.rows,
            "row_count": result.row_count
        }
    except Exception as e:
        logger.error(f"Monthly summary error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/top-vendors")
async def get_top_vendors(limit: int = Query(10, ge=1, le=100)):
    """Get top vendors by total amount"""
    from src.analytics.engine import Aggregator
    
    try:
        aggregator = Aggregator()
        result = await aggregator.get_top_vendors(limit)
        return {
            "columns": result.columns,
            "rows": result.rows,
            "row_count": result.row_count
        }
    except Exception as e:
        logger.error(f"Top vendors error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Forecast Endpoints
# =============================================================================

@router.post("/forecast")
async def run_forecast(request: ForecastRequest):
    """
    Generate a forecast for a metric.
    
    Available metrics:
    - revenue: Daily revenue
    - invoice_count: Daily invoice count
    - avg_invoice_value: Daily average invoice value
    
    Models:
    - linear: Simple linear regression (fast, always available)
    - prophet: Facebook Prophet (more accurate, requires prophet package)
    """
    from src.analytics.engine import Forecaster
    
    try:
        forecaster = Forecaster()
        result = await forecaster.forecast(
            metric=request.metric,
            horizon=request.horizon,
            model=request.model
        )
        return result.to_dict()
    except Exception as e:
        logger.error(f"Forecast error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/forecast/metrics")
async def list_forecast_metrics():
    """List available metrics for forecasting"""
    from src.analytics.engine import Forecaster
    
    forecaster = Forecaster()
    return {"metrics": forecaster.list_metrics()}


# =============================================================================
# Reports Endpoints (for backward compatibility)
# =============================================================================

REPORT_TEMPLATES = {
    "monthly_summary": {
        "name": "Tổng hợp theo tháng",
        "description": "Tổng doanh thu và số hóa đơn theo tháng"
    },
    "vendor_summary": {
        "name": "Tổng hợp theo NCC",
        "description": "Tổng tiền theo nhà cung cấp"
    },
    "high_value_invoices": {
        "name": "Hóa đơn giá trị cao",
        "description": "Các hóa đơn trên 10 triệu VND"
    }
}


@router.get("/reports")
async def list_reports():
    """List available report templates"""
    return {
        "reports": [
            {"id": k, "name": v["name"], "description": v["description"]}
            for k, v in REPORT_TEMPLATES.items()
        ]
    }


@router.post("/reports/{report_id}/run")
async def run_report(report_id: str):
    """Run a pre-built report"""
    from src.analytics.engine import Aggregator
    
    if report_id not in REPORT_TEMPLATES:
        raise HTTPException(status_code=404, detail="Report not found")
    
    try:
        aggregator = Aggregator()
        
        if report_id == "monthly_summary":
            result = await aggregator.get_monthly_summary(12)
        elif report_id == "vendor_summary":
            result = await aggregator.get_top_vendors(50)
        elif report_id == "high_value_invoices":
            from src.analytics.connectors import PostgresConnector
            connector = PostgresConnector()
            await connector.connect()
            result = await connector.execute_query("""
                SELECT invoice_number, vendor_name, invoice_date, 
                       total_amount, tax_amount, currency
                FROM extracted_invoices
                WHERE total_amount > 10000000
                ORDER BY total_amount DESC
                LIMIT 100
            """)
        else:
            raise HTTPException(status_code=404, detail="Report not found")
        
        return {
            "success": True,
            "report": REPORT_TEMPLATES[report_id],
            "columns": result.columns,
            "rows": result.rows,
            "row_count": result.row_count
        }
    except Exception as e:
        logger.error(f"Report error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
