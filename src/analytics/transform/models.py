"""
Transform Models
dbt-inspired data transformation models
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union
from enum import Enum
import pandas as pd
import logging

logger = logging.getLogger(__name__)


class MaterializationType(Enum):
    """How to persist the model output"""
    VIEW = "view"           # Database view (computed on read)
    TABLE = "table"         # Persisted table (replaced on run)
    INCREMENTAL = "incremental"  # Append/merge new data
    EPHEMERAL = "ephemeral"      # Not persisted (CTE)


@dataclass
class ModelConfig:
    """Configuration for a transformation model"""
    name: str
    description: str = ""
    materialization: MaterializationType = MaterializationType.TABLE
    schema: str = "analytics"
    tags: List[str] = field(default_factory=list)
    depends_on: List[str] = field(default_factory=list)  # Model dependencies
    unique_key: Optional[str] = None  # For incremental
    partition_by: Optional[str] = None
    cluster_by: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "materialization": self.materialization.value,
            "schema": self.schema,
            "tags": self.tags,
            "depends_on": self.depends_on,
        }


@dataclass
class ModelResult:
    """Result of running a model"""
    name: str
    success: bool
    rows_affected: int
    execution_time_ms: float
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "success": self.success,
            "rows_affected": self.rows_affected,
            "execution_time_ms": self.execution_time_ms,
            "error": self.error,
        }


class Model(ABC):
    """
    Base class for transformation models.
    Inspired by dbt models but works with both SQL and Python.
    """
    
    def __init__(self, config: ModelConfig):
        self.config = config
    
    @property
    def name(self) -> str:
        return self.config.name
    
    @abstractmethod
    async def run(self, context: Dict[str, Any]) -> ModelResult:
        """Execute the model transformation"""
        pass
    
    @abstractmethod
    def get_sql(self) -> Optional[str]:
        """Get SQL representation if applicable"""
        pass


class SQLModel(Model):
    """
    SQL-based transformation model.
    Similar to dbt SQL models.
    
    Usage:
        model = SQLModel(
            config=ModelConfig(name="monthly_revenue"),
            sql=\"\"\"
                SELECT 
                    DATE_TRUNC('month', date) as month,
                    SUM(amount) as revenue
                FROM {{ ref('invoices') }}
                GROUP BY 1
            \"\"\"
        )
    """
    
    def __init__(self, config: ModelConfig, sql: str):
        super().__init__(config)
        self.sql = sql
    
    def get_sql(self) -> str:
        return self.sql
    
    def _resolve_refs(self, sql: str, context: Dict[str, Any]) -> str:
        """
        Resolve {{ ref('model_name') }} references.
        Replaces with actual table names from context.
        """
        import re
        
        def replace_ref(match):
            model_name = match.group(1)
            # Look up actual table name from context
            tables = context.get('tables', {})
            return tables.get(model_name, model_name)
        
        pattern = r"\{\{\s*ref\(['\"](\w+)['\"]\)\s*\}\}"
        return re.sub(pattern, replace_ref, sql)
    
    async def run(self, context: Dict[str, Any]) -> ModelResult:
        """Execute the SQL model"""
        import time
        start_time = time.time()
        
        try:
            connector = context.get('connector')
            if not connector:
                raise ValueError("No database connector in context")
            
            # Resolve references
            resolved_sql = self._resolve_refs(self.sql, context)
            
            # Execute based on materialization
            if self.config.materialization == MaterializationType.VIEW:
                create_sql = f"CREATE OR REPLACE VIEW {self.config.schema}.{self.name} AS {resolved_sql}"
            elif self.config.materialization == MaterializationType.TABLE:
                # Drop and recreate
                drop_sql = f"DROP TABLE IF EXISTS {self.config.schema}.{self.name}"
                await connector.execute(drop_sql)
                create_sql = f"CREATE TABLE {self.config.schema}.{self.name} AS {resolved_sql}"
            else:
                create_sql = resolved_sql
            
            result = await connector.execute(create_sql)
            execution_time = (time.time() - start_time) * 1000
            
            return ModelResult(
                name=self.name,
                success=True,
                rows_affected=result.row_count,
                execution_time_ms=execution_time,
            )
            
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            logger.error(f"Model '{self.name}' failed: {e}")
            return ModelResult(
                name=self.name,
                success=False,
                rows_affected=0,
                execution_time_ms=execution_time,
                error=str(e),
            )


class PythonModel(Model):
    """
    Python-based transformation model.
    Uses pandas/polars for transformations.
    
    Usage:
        def transform_revenue(context):
            invoices = context['ref']('invoices')
            result = invoices.groupby(invoices['date'].dt.to_period('M')).agg(
                revenue=('amount', 'sum')
            ).reset_index()
            return result
        
        model = PythonModel(
            config=ModelConfig(name="monthly_revenue"),
            transform_fn=transform_revenue
        )
    """
    
    def __init__(self, config: ModelConfig, transform_fn):
        super().__init__(config)
        self.transform_fn = transform_fn
    
    def get_sql(self) -> None:
        return None
    
    async def run(self, context: Dict[str, Any]) -> ModelResult:
        """Execute the Python transformation"""
        import time
        start_time = time.time()
        
        try:
            # Add ref function to context
            def ref(model_name: str) -> pd.DataFrame:
                dataframes = context.get('dataframes', {})
                if model_name not in dataframes:
                    raise ValueError(f"Model '{model_name}' not found in context")
                return dataframes[model_name]
            
            context['ref'] = ref
            
            # Execute transformation
            result_df = self.transform_fn(context)
            
            # Persist result based on materialization
            connector = context.get('connector')
            if connector and self.config.materialization != MaterializationType.EPHEMERAL:
                # Write to database
                # (Implementation depends on connector type)
                pass
            
            # Store in context for downstream models
            context.setdefault('dataframes', {})[self.name] = result_df
            
            execution_time = (time.time() - start_time) * 1000
            
            return ModelResult(
                name=self.name,
                success=True,
                rows_affected=len(result_df),
                execution_time_ms=execution_time,
            )
            
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            logger.error(f"Python model '{self.name}' failed: {e}")
            return ModelResult(
                name=self.name,
                success=False,
                rows_affected=0,
                execution_time_ms=execution_time,
                error=str(e),
            )
