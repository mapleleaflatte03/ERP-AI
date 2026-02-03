"""
Forecaster
Time series forecasting with Prophet and scikit-learn
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


@dataclass
class ForecastResult:
    """Result of a forecast prediction"""
    forecast: pd.DataFrame  # ds, yhat, yhat_lower, yhat_upper
    model_name: str
    periods: int
    metrics: Dict[str, float] = field(default_factory=dict)  # MAE, MAPE, RMSE
    components: Optional[pd.DataFrame] = None  # trend, seasonality
    
    def to_dict(self, include_data: bool = True) -> Dict[str, Any]:
        result = {
            "model": self.model_name,
            "periods": self.periods,
            "metrics": self.metrics,
        }
        if include_data:
            result["forecast"] = self.forecast.to_dict(orient="records")
            if self.components is not None:
                result["components"] = self.components.to_dict(orient="records")
        return result
    
    def summary(self) -> Dict[str, Any]:
        """Get forecast summary statistics"""
        return {
            "periods": self.periods,
            "min_forecast": float(self.forecast['yhat'].min()),
            "max_forecast": float(self.forecast['yhat'].max()),
            "mean_forecast": float(self.forecast['yhat'].mean()),
            "total_forecast": float(self.forecast['yhat'].sum()),
            "metrics": self.metrics,
        }


class Forecaster(ABC):
    """Base class for forecasting models"""
    
    def __init__(self, name: str):
        self.name = name
        self._model = None
        self._is_fitted = False
    
    @abstractmethod
    def fit(self, df: pd.DataFrame, date_col: str, value_col: str) -> "Forecaster":
        """Fit the model to historical data"""
        pass
    
    @abstractmethod
    def predict(self, periods: int) -> ForecastResult:
        """Generate forecast for future periods"""
        pass
    
    def fit_predict(
        self, 
        df: pd.DataFrame, 
        date_col: str, 
        value_col: str, 
        periods: int
    ) -> ForecastResult:
        """Fit and predict in one call"""
        self.fit(df, date_col, value_col)
        return self.predict(periods)
    
    @staticmethod
    def calculate_metrics(actual: np.ndarray, predicted: np.ndarray) -> Dict[str, float]:
        """Calculate forecast accuracy metrics"""
        # Remove NaN
        mask = ~(np.isnan(actual) | np.isnan(predicted))
        actual = actual[mask]
        predicted = predicted[mask]
        
        if len(actual) == 0:
            return {}
        
        # MAE - Mean Absolute Error
        mae = np.mean(np.abs(actual - predicted))
        
        # RMSE - Root Mean Square Error
        rmse = np.sqrt(np.mean((actual - predicted) ** 2))
        
        # MAPE - Mean Absolute Percentage Error (avoid division by zero)
        non_zero = actual != 0
        if non_zero.any():
            mape = np.mean(np.abs((actual[non_zero] - predicted[non_zero]) / actual[non_zero])) * 100
        else:
            mape = None
        
        metrics = {
            "mae": float(mae),
            "rmse": float(rmse),
        }
        if mape is not None:
            metrics["mape"] = float(mape)
        
        return metrics
    
    def cross_validate(
        self, 
        df: pd.DataFrame, 
        date_col: str, 
        value_col: str,
        horizon: int = 30,
        initial: int = 365,
        period: int = 30,
    ) -> Dict[str, Any]:
        """
        Perform time series cross-validation.
        
        Args:
            horizon: Forecast horizon for each fold
            initial: Initial training period size
            period: Period between cutoff dates
        """
        df = df.sort_values(date_col).reset_index(drop=True)
        
        if len(df) < initial + horizon:
            return {"error": "Not enough data for cross-validation"}
        
        cutoffs = []
        start = initial
        while start + horizon <= len(df):
            cutoffs.append(start)
            start += period
        
        metrics_list = []
        
        for cutoff in cutoffs[:5]:  # Limit to 5 folds
            train = df.iloc[:cutoff]
            test = df.iloc[cutoff:cutoff + horizon]
            
            try:
                self.fit(train, date_col, value_col)
                result = self.predict(len(test))
                
                # Calculate metrics
                actual = test[value_col].values
                predicted = result.forecast['yhat'].values[:len(actual)]
                metrics = self.calculate_metrics(actual, predicted)
                metrics_list.append(metrics)
            except Exception as e:
                logger.warning(f"CV fold failed: {e}")
        
        if not metrics_list:
            return {"error": "All CV folds failed"}
        
        # Average metrics
        avg_metrics = {}
        for key in metrics_list[0].keys():
            values = [m.get(key) for m in metrics_list if m.get(key) is not None]
            if values:
                avg_metrics[f"cv_{key}"] = float(np.mean(values))
                avg_metrics[f"cv_{key}_std"] = float(np.std(values))
        
        return {
            "folds": len(metrics_list),
            "metrics": avg_metrics,
        }
