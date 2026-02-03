"""
Analytics Service
Main entry point for analytics functionality
"""
from typing import Any, Dict, List, Optional
import logging

from .config import get_config
from ..connectors import DatasetConnector, PostgresConnector
from ..agent import AnalyticsAgent
from ..forecast import ProphetForecaster, LinearForecaster
from ..quality import DataValidator
from ..transform import TransformRunner

logger = logging.getLogger(__name__)


class AnalyticsService:
    """
    Main analytics service providing unified access to all features.
    
    Usage:
        service = AnalyticsService()
        await service.initialize()
        
        # Chat with agent
        response = await service.chat("List all datasets")
        
        # Direct data access
        datasets = await service.list_datasets()
        df = await service.load_dataset("FPT Stock Data")
        
        # Forecasting
        forecast = await service.forecast("FPT Stock Data", "Date", "Close", 30)
    """
    
    def __init__(self):
        self._initialized = False
        self._dataset_connector: Optional[DatasetConnector] = None
        self._postgres_connector: Optional[PostgresConnector] = None
        self._agent: Optional[AnalyticsAgent] = None
        self._transform_runner: Optional[TransformRunner] = None
    
    async def initialize(self) -> None:
        """Initialize all services"""
        if self._initialized:
            return
        
        config = get_config()
        
        # Initialize connectors
        self._dataset_connector = DatasetConnector()
        await self._dataset_connector.connect()
        
        self._postgres_connector = PostgresConnector()
        await self._postgres_connector.connect()
        
        # Initialize agent
        self._agent = AnalyticsAgent(
            llm_provider=config.llm.provider,
            model=config.llm.model,
        )
        
        # Initialize transform runner
        self._transform_runner = TransformRunner()
        
        self._initialized = True
        logger.info("AnalyticsService initialized")
    
    async def shutdown(self) -> None:
        """Cleanup resources"""
        if self._dataset_connector:
            await self._dataset_connector.disconnect()
        if self._postgres_connector:
            await self._postgres_connector.disconnect()
        self._initialized = False
        logger.info("AnalyticsService shutdown")
    
    # =========================================================================
    # Chat Interface
    # =========================================================================
    
    async def chat(
        self, 
        message: str, 
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Chat with the analytics agent"""
        if not self._initialized:
            await self.initialize()
        
        response = await self._agent.chat(message, session_id)
        return response.to_dict()
    
    # =========================================================================
    # Dataset Operations
    # =========================================================================
    
    async def list_datasets(self) -> List[Dict[str, Any]]:
        """List all available datasets"""
        if not self._initialized:
            await self.initialize()
        return await self._dataset_connector.list_datasets()
    
    async def get_dataset(self, name: str) -> Optional[Dict[str, Any]]:
        """Get dataset metadata by name"""
        if not self._initialized:
            await self.initialize()
        return await self._dataset_connector.get_dataset(name)
    
    async def load_dataset(self, name: str):
        """Load dataset into DataFrame"""
        if not self._initialized:
            await self.initialize()
        return await self._dataset_connector.load_dataset(name)
    
    async def describe_dataset(self, name: str) -> Dict[str, Any]:
        """Get statistical description of dataset"""
        if not self._initialized:
            await self.initialize()
        return await self._dataset_connector.describe_dataset(name)
    
    # =========================================================================
    # Database Operations
    # =========================================================================
    
    async def list_tables(self) -> List[Dict[str, Any]]:
        """List database tables"""
        if not self._initialized:
            await self.initialize()
        tables = await self._postgres_connector.get_tables()
        return [t.to_dict() for t in tables]
    
    async def execute_query(self, sql: str) -> Dict[str, Any]:
        """Execute SQL query"""
        if not self._initialized:
            await self.initialize()
        result = await self._postgres_connector.execute(sql)
        return result.to_dict()
    
    # =========================================================================
    # Forecasting
    # =========================================================================
    
    async def forecast(
        self,
        dataset_name: str,
        date_column: str,
        value_column: str,
        periods: int = 30,
        model: str = "linear",
    ) -> Dict[str, Any]:
        """Generate forecast for time series data"""
        if not self._initialized:
            await self.initialize()
        
        df = await self._dataset_connector.load_dataset(dataset_name)
        
        # Select forecaster
        if model == "prophet":
            try:
                forecaster = ProphetForecaster()
            except ImportError:
                forecaster = LinearForecaster()
        else:
            forecaster = LinearForecaster()
        
        result = forecaster.fit_predict(df, date_column, value_column, periods)
        return result.to_dict()
    
    # =========================================================================
    # Data Quality
    # =========================================================================
    
    async def validate_dataset(
        self, 
        dataset_name: str,
        schema: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """Validate dataset quality"""
        if not self._initialized:
            await self.initialize()
        
        df = await self._dataset_connector.load_dataset(dataset_name)
        
        if schema:
            validator = DataValidator.from_schema(dataset_name, schema)
        else:
            # Basic validation
            validator = DataValidator(dataset_name)
            for col in df.columns:
                validator.expect_column_to_exist(col)
                validator.expect_column_values_not_null(col, threshold=0.5)
        
        suite = validator.validate(df)
        return suite.to_dict()
    
    # =========================================================================
    # KPIs
    # =========================================================================
    
    async def get_kpis(self) -> Dict[str, Any]:
        """Get key performance indicators"""
        if not self._initialized:
            await self.initialize()
        
        kpis = {}
        
        try:
            # Total documents
            result = await self._postgres_connector.execute(
                "SELECT COUNT(*) as count FROM documents"
            )
            kpis["total_documents"] = int(result.data['count'].iloc[0])
        except:
            kpis["total_documents"] = None
        
        try:
            # Total datasets
            datasets = await self._dataset_connector.list_datasets()
            kpis["total_datasets"] = len(datasets)
            kpis["total_data_rows"] = sum(ds.get("row_count", 0) for ds in datasets)
        except:
            kpis["total_datasets"] = None
        
        try:
            # Recent invoices total
            result = await self._postgres_connector.execute(
                "SELECT SUM(total_amount) as total FROM invoices WHERE created_at >= NOW() - INTERVAL '30 days'"
            )
            total = result.data['total'].iloc[0]
            kpis["monthly_invoice_total"] = float(total) if total else 0
        except:
            kpis["monthly_invoice_total"] = None
        
        return {
            "success": True,
            "kpis": kpis,
        }


# Singleton instance
_service: Optional[AnalyticsService] = None


def get_service() -> AnalyticsService:
    """Get singleton service instance"""
    global _service
    if _service is None:
        _service = AnalyticsService()
    return _service
