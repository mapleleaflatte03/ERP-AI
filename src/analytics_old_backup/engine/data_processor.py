"""
Data Processor Service
Xử lý datasets với các thao tác: filter, aggregate, transform, pivot
"""
import logging
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, field
import pandas as pd
import numpy as np
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class ProcessingResult:
    """Result of data processing"""
    success: bool
    data: Optional[pd.DataFrame] = None
    summary: Optional[Dict] = None
    error: Optional[str] = None
    row_count: int = 0
    columns: List[str] = field(default_factory=list)


class DataProcessor:
    """
    Process datasets with various operations.
    Designed to be called by the Agent.
    """
    
    def __init__(self):
        self._datasets: Dict[str, pd.DataFrame] = {}
        self._processing_history: List[Dict] = []
    
    def load_dataset(self, name: str, df: pd.DataFrame) -> ProcessingResult:
        """Load a dataset into memory for processing"""
        try:
            self._datasets[name] = df.copy()
            return ProcessingResult(
                success=True,
                data=df,
                row_count=len(df),
                columns=list(df.columns),
                summary=self._get_summary(df)
            )
        except Exception as e:
            return ProcessingResult(success=False, error=str(e))
    
    def get_dataset(self, name: str) -> Optional[pd.DataFrame]:
        """Get a loaded dataset"""
        return self._datasets.get(name)
    
    def list_datasets(self) -> List[str]:
        """List loaded datasets"""
        return list(self._datasets.keys())
    
    def describe(self, name: str) -> ProcessingResult:
        """Get statistical description of a dataset"""
        df = self._datasets.get(name)
        if df is None:
            return ProcessingResult(success=False, error=f"Dataset '{name}' not found")
        
        try:
            desc = df.describe(include='all').to_dict()
            return ProcessingResult(
                success=True,
                summary={
                    "shape": df.shape,
                    "columns": list(df.columns),
                    "dtypes": df.dtypes.astype(str).to_dict(),
                    "null_counts": df.isnull().sum().to_dict(),
                    "statistics": desc
                },
                row_count=len(df),
                columns=list(df.columns)
            )
        except Exception as e:
            return ProcessingResult(success=False, error=str(e))
    
    def filter_data(
        self,
        name: str,
        conditions: List[Dict],
        output_name: Optional[str] = None
    ) -> ProcessingResult:
        """
        Filter dataset based on conditions.
        
        conditions: [{"column": "price", "operator": ">", "value": 100}]
        """
        df = self._datasets.get(name)
        if df is None:
            return ProcessingResult(success=False, error=f"Dataset '{name}' not found")
        
        try:
            result = df.copy()
            for cond in conditions:
                col = cond["column"]
                op = cond["operator"]
                val = cond["value"]
                
                if op == "==":
                    result = result[result[col] == val]
                elif op == "!=":
                    result = result[result[col] != val]
                elif op == ">":
                    result = result[result[col] > val]
                elif op == ">=":
                    result = result[result[col] >= val]
                elif op == "<":
                    result = result[result[col] < val]
                elif op == "<=":
                    result = result[result[col] <= val]
                elif op == "contains":
                    result = result[result[col].astype(str).str.contains(str(val), case=False, na=False)]
                elif op == "in":
                    result = result[result[col].isin(val)]
            
            # Save result
            save_name = output_name or f"{name}_filtered"
            self._datasets[save_name] = result
            
            return ProcessingResult(
                success=True,
                data=result,
                row_count=len(result),
                columns=list(result.columns),
                summary={"original_rows": len(df), "filtered_rows": len(result)}
            )
        except Exception as e:
            return ProcessingResult(success=False, error=str(e))
    
    def aggregate(
        self,
        name: str,
        group_by: List[str],
        aggregations: Dict[str, Union[str, List[str]]],
        output_name: Optional[str] = None
    ) -> ProcessingResult:
        """
        Aggregate dataset.
        
        aggregations: {"price": ["sum", "mean"], "volume": "sum"}
        """
        df = self._datasets.get(name)
        if df is None:
            return ProcessingResult(success=False, error=f"Dataset '{name}' not found")
        
        try:
            # Normalize aggregations
            agg_dict = {}
            for col, agg in aggregations.items():
                if isinstance(agg, str):
                    agg_dict[col] = [agg]
                else:
                    agg_dict[col] = agg
            
            result = df.groupby(group_by).agg(agg_dict).reset_index()
            
            # Flatten column names
            result.columns = ['_'.join(col).strip('_') if isinstance(col, tuple) else col 
                            for col in result.columns.values]
            
            save_name = output_name or f"{name}_aggregated"
            self._datasets[save_name] = result
            
            return ProcessingResult(
                success=True,
                data=result,
                row_count=len(result),
                columns=list(result.columns),
                summary=self._get_summary(result)
            )
        except Exception as e:
            return ProcessingResult(success=False, error=str(e))
    
    def calculate_column(
        self,
        name: str,
        new_column: str,
        expression: str,
        output_name: Optional[str] = None
    ) -> ProcessingResult:
        """
        Calculate a new column using expression.
        
        expression: "price * volume" or "close - open"
        """
        df = self._datasets.get(name)
        if df is None:
            return ProcessingResult(success=False, error=f"Dataset '{name}' not found")
        
        try:
            result = df.copy()
            # Safe eval with only pandas/numpy functions
            result[new_column] = result.eval(expression)
            
            save_name = output_name or name
            self._datasets[save_name] = result
            
            return ProcessingResult(
                success=True,
                data=result,
                row_count=len(result),
                columns=list(result.columns)
            )
        except Exception as e:
            return ProcessingResult(success=False, error=str(e))
    
    def sort_data(
        self,
        name: str,
        by: List[str],
        ascending: Union[bool, List[bool]] = True,
        output_name: Optional[str] = None
    ) -> ProcessingResult:
        """Sort dataset"""
        df = self._datasets.get(name)
        if df is None:
            return ProcessingResult(success=False, error=f"Dataset '{name}' not found")
        
        try:
            result = df.sort_values(by=by, ascending=ascending)
            save_name = output_name or name
            self._datasets[save_name] = result
            
            return ProcessingResult(
                success=True,
                data=result,
                row_count=len(result),
                columns=list(result.columns)
            )
        except Exception as e:
            return ProcessingResult(success=False, error=str(e))
    
    def top_n(
        self,
        name: str,
        n: int,
        by: str,
        ascending: bool = False
    ) -> ProcessingResult:
        """Get top N rows by a column"""
        df = self._datasets.get(name)
        if df is None:
            return ProcessingResult(success=False, error=f"Dataset '{name}' not found")
        
        try:
            result = df.nlargest(n, by) if not ascending else df.nsmallest(n, by)
            return ProcessingResult(
                success=True,
                data=result,
                row_count=len(result),
                columns=list(result.columns)
            )
        except Exception as e:
            return ProcessingResult(success=False, error=str(e))
    
    def pivot_table(
        self,
        name: str,
        index: Union[str, List[str]],
        columns: Optional[Union[str, List[str]]] = None,
        values: Optional[Union[str, List[str]]] = None,
        aggfunc: str = "mean",
        output_name: Optional[str] = None
    ) -> ProcessingResult:
        """Create pivot table"""
        df = self._datasets.get(name)
        if df is None:
            return ProcessingResult(success=False, error=f"Dataset '{name}' not found")
        
        try:
            result = pd.pivot_table(
                df,
                index=index,
                columns=columns,
                values=values,
                aggfunc=aggfunc,
                fill_value=0
            ).reset_index()
            
            save_name = output_name or f"{name}_pivot"
            self._datasets[save_name] = result
            
            return ProcessingResult(
                success=True,
                data=result,
                row_count=len(result),
                columns=list(result.columns)
            )
        except Exception as e:
            return ProcessingResult(success=False, error=str(e))
    
    def time_series_resample(
        self,
        name: str,
        date_column: str,
        freq: str,  # 'D', 'W', 'M', 'Q', 'Y'
        aggregations: Dict[str, str],
        output_name: Optional[str] = None
    ) -> ProcessingResult:
        """Resample time series data"""
        df = self._datasets.get(name)
        if df is None:
            return ProcessingResult(success=False, error=f"Dataset '{name}' not found")
        
        try:
            result = df.copy()
            result[date_column] = pd.to_datetime(result[date_column])
            result = result.set_index(date_column)
            result = result.resample(freq).agg(aggregations).reset_index()
            
            save_name = output_name or f"{name}_resampled"
            self._datasets[save_name] = result
            
            return ProcessingResult(
                success=True,
                data=result,
                row_count=len(result),
                columns=list(result.columns)
            )
        except Exception as e:
            return ProcessingResult(success=False, error=str(e))
    
    def get_sample(self, name: str, n: int = 10) -> ProcessingResult:
        """Get sample rows from dataset"""
        df = self._datasets.get(name)
        if df is None:
            return ProcessingResult(success=False, error=f"Dataset '{name}' not found")
        
        try:
            sample = df.head(n)
            return ProcessingResult(
                success=True,
                data=sample,
                row_count=n,
                columns=list(df.columns)
            )
        except Exception as e:
            return ProcessingResult(success=False, error=str(e))
    
    def _get_summary(self, df: pd.DataFrame) -> Dict:
        """Get quick summary of dataframe"""
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        return {
            "rows": len(df),
            "columns": len(df.columns),
            "numeric_columns": numeric_cols,
            "memory_mb": df.memory_usage(deep=True).sum() / 1024 / 1024
        }


# Singleton
_processor: Optional[DataProcessor] = None

def get_processor() -> DataProcessor:
    global _processor
    if _processor is None:
        _processor = DataProcessor()
    return _processor
