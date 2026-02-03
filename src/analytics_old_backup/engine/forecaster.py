"""
Forecasting Engine using Prophet and scikit-learn
"""
import logging
from typing import Any, Dict, List, Optional, Literal
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json

from ..connectors import PostgresConnector, QueryResult
from ..core.config import get_config
from ..core.exceptions import ForecastError

logger = logging.getLogger(__name__)


@dataclass
class ForecastPoint:
    """A single forecast point"""
    date: str
    value: float
    lower_bound: Optional[float] = None
    upper_bound: Optional[float] = None


@dataclass
class ForecastResult:
    """Result of a forecast"""
    metric: str
    model: str
    horizon: int
    forecast: List[ForecastPoint]
    historical: List[ForecastPoint]
    components: Optional[Dict[str, Any]] = None
    metrics: Optional[Dict[str, float]] = None  # MAE, RMSE, etc.
    
    def to_dict(self) -> dict:
        return {
            "metric": self.metric,
            "model": self.model,
            "horizon": self.horizon,
            "forecast": [
                {
                    "date": p.date,
                    "value": p.value,
                    "lower_bound": p.lower_bound,
                    "upper_bound": p.upper_bound
                }
                for p in self.forecast
            ],
            "historical": [
                {"date": p.date, "value": p.value}
                for p in self.historical
            ],
            "components": self.components,
            "metrics": self.metrics
        }


class Forecaster:
    """
    Time series forecasting using Prophet and scikit-learn.
    """
    
    SUPPORTED_METRICS = {
        "revenue": {
            "sql": """
                SELECT 
                    DATE(invoice_date) as ds,
                    SUM(total_amount) as y
                FROM extracted_invoices
                WHERE invoice_date IS NOT NULL
                GROUP BY DATE(invoice_date)
                ORDER BY ds
            """,
            "description": "Daily revenue"
        },
        "invoice_count": {
            "sql": """
                SELECT 
                    DATE(created_at) as ds,
                    COUNT(*) as y
                FROM extracted_invoices
                GROUP BY DATE(created_at)
                ORDER BY ds
            """,
            "description": "Daily invoice count"
        },
        "avg_invoice_value": {
            "sql": """
                SELECT 
                    DATE(invoice_date) as ds,
                    AVG(total_amount) as y
                FROM extracted_invoices
                WHERE invoice_date IS NOT NULL AND total_amount > 0
                GROUP BY DATE(invoice_date)
                ORDER BY ds
            """,
            "description": "Daily average invoice value"
        }
    }
    
    def __init__(self, connector: Optional[PostgresConnector] = None):
        self._connector = connector or PostgresConnector()
        self._config = get_config().forecast
    
    async def _get_historical_data(self, metric: str) -> List[Dict[str, Any]]:
        """Fetch historical data for a metric"""
        if metric not in self.SUPPORTED_METRICS:
            raise ForecastError(f"Unsupported metric: {metric}")
        
        await self._connector.connect()
        sql = self.SUPPORTED_METRICS[metric]["sql"]
        result = await self._connector.execute_query(sql)
        
        if not result.success:
            raise ForecastError(f"Failed to fetch data: {result.error}")
        
        return result.rows
    
    async def forecast_prophet(
        self,
        metric: str,
        horizon: int = 30,
        include_components: bool = False
    ) -> ForecastResult:
        """
        Generate forecast using Prophet.
        
        Args:
            metric: The metric to forecast
            horizon: Number of days to forecast
            include_components: Whether to include trend/seasonality components
        """
        try:
            from prophet import Prophet
            import pandas as pd
        except ImportError:
            raise ForecastError("Prophet is not installed. Run: pip install prophet")
        
        # Get historical data
        data = await self._get_historical_data(metric)
        
        if len(data) < 10:
            raise ForecastError(f"Insufficient data for forecasting: {len(data)} points (need at least 10)")
        
        # Prepare DataFrame
        df = pd.DataFrame(data)
        df['ds'] = pd.to_datetime(df['ds'])
        df['y'] = pd.to_numeric(df['y'], errors='coerce')
        df = df.dropna()
        
        # Initialize and fit Prophet
        model = Prophet(
            yearly_seasonality=True,
            weekly_seasonality=True,
            daily_seasonality=False,
            interval_width=self._config.confidence_interval
        )
        
        model.fit(df)
        
        # Create future dataframe
        future = model.make_future_dataframe(periods=horizon)
        
        # Generate forecast
        forecast = model.predict(future)
        
        # Extract results
        historical = [
            ForecastPoint(
                date=row['ds'].isoformat()[:10],
                value=float(row['y'])
            )
            for _, row in df.iterrows()
        ]
        
        forecast_points = [
            ForecastPoint(
                date=row['ds'].isoformat()[:10],
                value=float(row['yhat']),
                lower_bound=float(row['yhat_lower']),
                upper_bound=float(row['yhat_upper'])
            )
            for _, row in forecast.tail(horizon).iterrows()
        ]
        
        # Components
        components = None
        if include_components:
            components = {
                "trend": forecast['trend'].tail(horizon).tolist(),
                "weekly": forecast['weekly'].tail(horizon).tolist() if 'weekly' in forecast.columns else None,
                "yearly": forecast['yearly'].tail(horizon).tolist() if 'yearly' in forecast.columns else None
            }
        
        return ForecastResult(
            metric=metric,
            model="prophet",
            horizon=horizon,
            forecast=forecast_points,
            historical=historical,
            components=components
        )
    
    async def forecast_linear(
        self,
        metric: str,
        horizon: int = 30
    ) -> ForecastResult:
        """
        Generate forecast using linear regression (simpler fallback).
        """
        try:
            from sklearn.linear_model import LinearRegression
            import numpy as np
            import pandas as pd
        except ImportError:
            raise ForecastError("scikit-learn is not installed")
        
        # Get historical data
        data = await self._get_historical_data(metric)
        
        if len(data) < 5:
            raise ForecastError(f"Insufficient data for forecasting: {len(data)} points")
        
        df = pd.DataFrame(data)
        df['ds'] = pd.to_datetime(df['ds'])
        df['y'] = pd.to_numeric(df['y'], errors='coerce')
        df = df.dropna().sort_values('ds')
        
        # Create numeric feature (days since start)
        df['x'] = (df['ds'] - df['ds'].min()).dt.days
        
        # Fit model
        X = df['x'].values.reshape(-1, 1)
        y = df['y'].values
        
        model = LinearRegression()
        model.fit(X, y)
        
        # Generate forecast
        last_date = df['ds'].max()
        last_x = df['x'].max()
        
        forecast_points = []
        for i in range(1, horizon + 1):
            future_x = last_x + i
            future_date = last_date + timedelta(days=i)
            predicted = model.predict([[future_x]])[0]
            
            # Simple confidence interval (±10%)
            forecast_points.append(ForecastPoint(
                date=future_date.isoformat()[:10],
                value=float(predicted),
                lower_bound=float(predicted * 0.9),
                upper_bound=float(predicted * 1.1)
            ))
        
        historical = [
            ForecastPoint(
                date=row['ds'].isoformat()[:10],
                value=float(row['y'])
            )
            for _, row in df.iterrows()
        ]
        
        return ForecastResult(
            metric=metric,
            model="linear",
            horizon=horizon,
            forecast=forecast_points,
            historical=historical
        )
    
    async def forecast(
        self,
        metric: str,
        horizon: Optional[int] = None,
        model: Optional[str] = None,
        include_components: bool = False
    ) -> ForecastResult:
        """
        Generate forecast using specified or default model.
        
        Args:
            metric: The metric to forecast
            horizon: Number of days to forecast
            model: Model to use ('prophet' or 'linear')
            include_components: Whether to include components (Prophet only)
        """
        horizon = horizon or self._config.default_horizon
        model = model or self._config.default_model
        
        if model == "prophet":
            try:
                return await self.forecast_prophet(metric, horizon, include_components)
            except ImportError:
                logger.warning("Prophet not available, falling back to linear")
                model = "linear"
        
        if model == "linear":
            return await self.forecast_linear(metric, horizon)
        
        raise ForecastError(f"Unknown model: {model}")
    
    def list_metrics(self) -> List[Dict[str, str]]:
        """List available metrics for forecasting"""
        return [
            {"id": key, "description": value["description"]}
            for key, value in self.SUPPORTED_METRICS.items()
        ]
