"""
Dashboard Service
Create, save, and manage dashboards with charts and metrics.
"""
import json
import logging
import uuid
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class ChartConfig:
    """Configuration for a chart"""
    chart_id: str
    chart_type: str  # line, bar, pie, scatter, area, heatmap
    title: str
    data: List[Dict]  # Serialized data
    x_field: Optional[str] = None
    y_field: Optional[str] = None
    series_field: Optional[str] = None
    color_scheme: str = "violet"
    options: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class MetricCard:
    """A KPI metric card"""
    metric_id: str
    title: str
    value: Any
    formatted_value: str
    change: Optional[float] = None
    change_direction: Optional[str] = None  # up, down, stable
    icon: str = "chart"
    color: str = "violet"
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class Dashboard:
    """A complete dashboard"""
    dashboard_id: str
    name: str
    description: str
    created_at: str
    updated_at: str
    dataset_name: Optional[str] = None
    charts: List[ChartConfig] = field(default_factory=list)
    metrics: List[MetricCard] = field(default_factory=list)
    layout: Dict = field(default_factory=dict)
    filters: List[Dict] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "dashboard_id": self.dashboard_id,
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "dataset_name": self.dataset_name,
            "charts": [c.to_dict() for c in self.charts],
            "metrics": [m.to_dict() for m in self.metrics],
            "layout": self.layout,
            "filters": self.filters
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "Dashboard":
        charts = [ChartConfig(**c) for c in data.get("charts", [])]
        metrics = [MetricCard(**m) for m in data.get("metrics", [])]
        return cls(
            dashboard_id=data["dashboard_id"],
            name=data["name"],
            description=data.get("description", ""),
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            dataset_name=data.get("dataset_name"),
            charts=charts,
            metrics=metrics,
            layout=data.get("layout", {}),
            filters=data.get("filters", [])
        )


class DashboardService:
    """
    Service for creating and managing dashboards.
    Dashboards are saved to disk as JSON files.
    """
    
    def __init__(self, storage_path: str = "/root/erp-ai/data/dashboards"):
        self._storage_path = Path(storage_path)
        self._storage_path.mkdir(parents=True, exist_ok=True)
        self._cache: Dict[str, Dashboard] = {}
        self._load_all()
    
    def _load_all(self):
        """Load all dashboards from storage"""
        for f in self._storage_path.glob("*.json"):
            try:
                with open(f, "r") as fp:
                    data = json.load(fp)
                    dashboard = Dashboard.from_dict(data)
                    self._cache[dashboard.dashboard_id] = dashboard
            except Exception as e:
                logger.error(f"Failed to load dashboard {f}: {e}")
    
    def _save_dashboard(self, dashboard: Dashboard):
        """Save dashboard to disk"""
        path = self._storage_path / f"{dashboard.dashboard_id}.json"
        with open(path, "w") as f:
            json.dump(dashboard.to_dict(), f, ensure_ascii=False, indent=2)
    
    def create_dashboard(
        self,
        name: str,
        description: str = "",
        dataset_name: Optional[str] = None
    ) -> Dashboard:
        """Create a new dashboard"""
        now = datetime.utcnow().isoformat()
        dashboard = Dashboard(
            dashboard_id=str(uuid.uuid4()),
            name=name,
            description=description,
            created_at=now,
            updated_at=now,
            dataset_name=dataset_name
        )
        self._cache[dashboard.dashboard_id] = dashboard
        self._save_dashboard(dashboard)
        return dashboard
    
    def get_dashboard(self, dashboard_id: str) -> Optional[Dashboard]:
        """Get a dashboard by ID"""
        return self._cache.get(dashboard_id)
    
    def list_dashboards(self) -> List[Dict]:
        """List all dashboards (summary only)"""
        return [
            {
                "dashboard_id": d.dashboard_id,
                "name": d.name,
                "description": d.description,
                "created_at": d.created_at,
                "updated_at": d.updated_at,
                "chart_count": len(d.charts),
                "metric_count": len(d.metrics)
            }
            for d in self._cache.values()
        ]
    
    def delete_dashboard(self, dashboard_id: str) -> bool:
        """Delete a dashboard"""
        if dashboard_id in self._cache:
            del self._cache[dashboard_id]
            path = self._storage_path / f"{dashboard_id}.json"
            if path.exists():
                path.unlink()
            return True
        return False
    
    def add_chart(
        self,
        dashboard_id: str,
        chart_type: str,
        title: str,
        data: pd.DataFrame,
        x_field: Optional[str] = None,
        y_field: Optional[str] = None,
        series_field: Optional[str] = None,
        options: Optional[Dict] = None
    ) -> Optional[ChartConfig]:
        """Add a chart to a dashboard"""
        dashboard = self._cache.get(dashboard_id)
        if not dashboard:
            return None
        
        # Serialize dataframe to records
        data_records = data.to_dict(orient="records")
        
        chart = ChartConfig(
            chart_id=str(uuid.uuid4()),
            chart_type=chart_type,
            title=title,
            data=data_records,
            x_field=x_field,
            y_field=y_field,
            series_field=series_field,
            options=options or {}
        )
        
        dashboard.charts.append(chart)
        dashboard.updated_at = datetime.utcnow().isoformat()
        self._save_dashboard(dashboard)
        
        return chart
    
    def add_metric(
        self,
        dashboard_id: str,
        title: str,
        value: Any,
        formatted_value: str,
        change: Optional[float] = None,
        change_direction: Optional[str] = None,
        icon: str = "chart",
        color: str = "violet"
    ) -> Optional[MetricCard]:
        """Add a metric card to a dashboard"""
        dashboard = self._cache.get(dashboard_id)
        if not dashboard:
            return None
        
        metric = MetricCard(
            metric_id=str(uuid.uuid4()),
            title=title,
            value=value,
            formatted_value=formatted_value,
            change=change,
            change_direction=change_direction,
            icon=icon,
            color=color
        )
        
        dashboard.metrics.append(metric)
        dashboard.updated_at = datetime.utcnow().isoformat()
        self._save_dashboard(dashboard)
        
        return metric
    
    def create_chart_from_data(
        self,
        df: pd.DataFrame,
        chart_type: str,
        title: str,
        x_field: str,
        y_field: str,
        series_field: Optional[str] = None,
        limit: int = 100
    ) -> Dict:
        """Create a chart configuration from DataFrame (without saving)"""
        # Limit data for performance
        data = df.head(limit).to_dict(orient="records")
        
        return {
            "chart_type": chart_type,
            "title": title,
            "data": data,
            "x_field": x_field,
            "y_field": y_field,
            "series_field": series_field
        }
    
    def auto_create_dashboard(
        self,
        name: str,
        df: pd.DataFrame,
        dataset_name: str,
        date_column: Optional[str] = None
    ) -> Dashboard:
        """
        Automatically create a dashboard from a DataFrame.
        Detects column types and creates appropriate charts.
        """
        dashboard = self.create_dashboard(name, f"Auto-generated from {dataset_name}", dataset_name)
        
        # Detect column types
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        date_cols = df.select_dtypes(include=['datetime64']).columns.tolist()
        categorical_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
        
        # Add metrics for numeric columns
        for col in numeric_cols[:5]:  # Max 5 metrics
            value = df[col].sum() if df[col].dtype in ['int64', 'float64'] else df[col].mean()
            formatted = self._format_number(value)
            self.add_metric(
                dashboard.dashboard_id,
                title=col,
                value=float(value),
                formatted_value=formatted
            )
        
        # Create time series chart if date column exists
        if date_column and date_column in df.columns and numeric_cols:
            try:
                time_df = df[[date_column, numeric_cols[0]]].dropna()
                time_df = time_df.sort_values(date_column)
                self.add_chart(
                    dashboard.dashboard_id,
                    chart_type="line",
                    title=f"{numeric_cols[0]} over time",
                    data=time_df,
                    x_field=date_column,
                    y_field=numeric_cols[0]
                )
            except Exception as e:
                logger.warning(f"Failed to create time series chart: {e}")
        
        # Create bar chart for categorical vs numeric
        if categorical_cols and numeric_cols:
            try:
                cat_col = categorical_cols[0]
                num_col = numeric_cols[0]
                agg_df = df.groupby(cat_col)[num_col].sum().reset_index()
                agg_df = agg_df.nlargest(10, num_col)  # Top 10
                self.add_chart(
                    dashboard.dashboard_id,
                    chart_type="bar",
                    title=f"{num_col} by {cat_col}",
                    data=agg_df,
                    x_field=cat_col,
                    y_field=num_col
                )
            except Exception as e:
                logger.warning(f"Failed to create bar chart: {e}")
        
        return dashboard
    
    def _format_number(self, value: float) -> str:
        """Format number for display"""
        if abs(value) >= 1e9:
            return f"{value/1e9:.1f}B"
        elif abs(value) >= 1e6:
            return f"{value/1e6:.1f}M"
        elif abs(value) >= 1e3:
            return f"{value/1e3:.1f}K"
        else:
            return f"{value:.2f}"


# Singleton
_service: Optional[DashboardService] = None

def get_dashboard_service() -> DashboardService:
    global _service
    if _service is None:
        _service = DashboardService()
    return _service
