"""
Forecast Models
Implementations of different forecasting algorithms
"""
import pandas as pd
import numpy as np
from typing import Optional
from datetime import timedelta
import logging

from .forecaster import Forecaster, ForecastResult

logger = logging.getLogger(__name__)


class ProphetForecaster(Forecaster):
    """
    Facebook Prophet forecasting model.
    Best for: Daily data with seasonality, holidays.
    
    Usage:
        forecaster = ProphetForecaster()
        forecaster.fit(df, 'date', 'revenue')
        result = forecaster.predict(30)  # 30 days
    """
    
    def __init__(
        self,
        seasonality_mode: str = "multiplicative",
        yearly_seasonality: bool = True,
        weekly_seasonality: bool = True,
        daily_seasonality: bool = False,
        changepoint_prior_scale: float = 0.05,
    ):
        super().__init__("prophet")
        self.seasonality_mode = seasonality_mode
        self.yearly_seasonality = yearly_seasonality
        self.weekly_seasonality = weekly_seasonality
        self.daily_seasonality = daily_seasonality
        self.changepoint_prior_scale = changepoint_prior_scale
        self._history = None
    
    def fit(self, df: pd.DataFrame, date_col: str, value_col: str) -> "ProphetForecaster":
        """Fit Prophet model"""
        try:
            from prophet import Prophet
        except ImportError:
            raise ImportError("Prophet not installed. Install with: pip install prophet")
        
        # Prepare data in Prophet format
        prophet_df = df[[date_col, value_col]].copy()
        prophet_df.columns = ['ds', 'y']
        prophet_df['ds'] = pd.to_datetime(prophet_df['ds'])
        prophet_df = prophet_df.dropna()
        
        self._history = prophet_df
        
        # Create and fit model
        self._model = Prophet(
            seasonality_mode=self.seasonality_mode,
            yearly_seasonality=self.yearly_seasonality,
            weekly_seasonality=self.weekly_seasonality,
            daily_seasonality=self.daily_seasonality,
            changepoint_prior_scale=self.changepoint_prior_scale,
        )
        
        # Suppress Stan output
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self._model.fit(prophet_df)
        
        self._is_fitted = True
        logger.info(f"Prophet model fitted with {len(prophet_df)} data points")
        return self
    
    def predict(self, periods: int) -> ForecastResult:
        """Generate forecast"""
        if not self._is_fitted:
            raise ValueError("Model not fitted. Call fit() first.")
        
        # Create future dataframe
        future = self._model.make_future_dataframe(periods=periods)
        
        # Predict
        forecast = self._model.predict(future)
        
        # Get only future predictions
        forecast_future = forecast.tail(periods)[['ds', 'yhat', 'yhat_lower', 'yhat_upper']].copy()
        
        # Calculate metrics on training data
        train_predictions = forecast.head(len(self._history))
        metrics = self.calculate_metrics(
            self._history['y'].values,
            train_predictions['yhat'].values
        )
        
        # Get components
        components = forecast[['ds', 'trend']].copy()
        if 'yearly' in forecast.columns:
            components['yearly'] = forecast['yearly']
        if 'weekly' in forecast.columns:
            components['weekly'] = forecast['weekly']
        
        return ForecastResult(
            forecast=forecast_future,
            model_name=self.name,
            periods=periods,
            metrics=metrics,
            components=components.tail(periods),
        )


class LinearForecaster(Forecaster):
    """
    Simple linear regression forecasting.
    Best for: Short-term trends without seasonality.
    
    Uses scikit-learn LinearRegression.
    """
    
    def __init__(self):
        super().__init__("linear")
        self._date_col = None
        self._last_date = None
        self._freq = None
    
    def fit(self, df: pd.DataFrame, date_col: str, value_col: str) -> "LinearForecaster":
        """Fit linear regression model"""
        from sklearn.linear_model import LinearRegression
        
        df = df[[date_col, value_col]].copy()
        df[date_col] = pd.to_datetime(df[date_col])
        df = df.dropna().sort_values(date_col)
        
        self._date_col = date_col
        self._last_date = df[date_col].max()
        
        # Infer frequency
        if len(df) > 1:
            diff = (df[date_col].iloc[1] - df[date_col].iloc[0]).days
            self._freq = timedelta(days=max(1, diff))
        else:
            self._freq = timedelta(days=1)
        
        # Convert dates to numeric (days since first date)
        first_date = df[date_col].min()
        X = (df[date_col] - first_date).dt.days.values.reshape(-1, 1)
        y = df[value_col].values
        
        self._model = LinearRegression()
        self._model.fit(X, y)
        
        self._first_date = first_date
        self._y_train = y
        self._X_train = X
        
        self._is_fitted = True
        logger.info(f"Linear model fitted: y = {self._model.coef_[0]:.2f}x + {self._model.intercept_:.2f}")
        return self
    
    def predict(self, periods: int) -> ForecastResult:
        """Generate linear forecast"""
        if not self._is_fitted:
            raise ValueError("Model not fitted. Call fit() first.")
        
        # Generate future dates
        future_dates = pd.date_range(
            start=self._last_date + self._freq,
            periods=periods,
            freq=self._freq
        )
        
        # Convert to numeric
        X_future = ((future_dates - self._first_date).days).values.reshape(-1, 1)
        
        # Predict
        y_pred = self._model.predict(X_future)
        
        # Simple confidence interval (based on residual std)
        train_pred = self._model.predict(self._X_train)
        residual_std = np.std(self._y_train - train_pred)
        
        forecast = pd.DataFrame({
            'ds': future_dates,
            'yhat': y_pred,
            'yhat_lower': y_pred - 1.96 * residual_std,
            'yhat_upper': y_pred + 1.96 * residual_std,
        })
        
        # Calculate training metrics
        metrics = self.calculate_metrics(self._y_train, train_pred)
        metrics['r2'] = float(self._model.score(self._X_train, self._y_train))
        
        return ForecastResult(
            forecast=forecast,
            model_name=self.name,
            periods=periods,
            metrics=metrics,
        )


class ARIMAForecaster(Forecaster):
    """
    ARIMA (AutoRegressive Integrated Moving Average) forecasting.
    Best for: Stationary time series data.
    
    Uses statsmodels ARIMA with auto parameter selection.
    """
    
    def __init__(self, order: tuple = None, seasonal_order: tuple = None):
        super().__init__("arima")
        self.order = order  # (p, d, q)
        self.seasonal_order = seasonal_order  # (P, D, Q, s)
        self._last_date = None
        self._freq = None
    
    def fit(self, df: pd.DataFrame, date_col: str, value_col: str) -> "ARIMAForecaster":
        """Fit ARIMA model"""
        try:
            from statsmodels.tsa.arima.model import ARIMA
        except ImportError:
            raise ImportError("statsmodels not installed. Install with: pip install statsmodels")
        
        df = df[[date_col, value_col]].copy()
        df[date_col] = pd.to_datetime(df[date_col])
        df = df.dropna().sort_values(date_col)
        
        self._last_date = df[date_col].max()
        
        # Infer frequency
        if len(df) > 1:
            diff = (df[date_col].iloc[1] - df[date_col].iloc[0]).days
            self._freq = timedelta(days=max(1, diff))
        else:
            self._freq = timedelta(days=1)
        
        y = df[value_col].values
        self._y_train = y
        
        # Auto-select order if not specified
        if self.order is None:
            self.order = (1, 1, 1)  # Default ARIMA(1,1,1)
        
        # Fit model
        model = ARIMA(y, order=self.order)
        self._model = model.fit()
        
        self._is_fitted = True
        logger.info(f"ARIMA{self.order} model fitted, AIC: {self._model.aic:.2f}")
        return self
    
    def predict(self, periods: int) -> ForecastResult:
        """Generate ARIMA forecast"""
        if not self._is_fitted:
            raise ValueError("Model not fitted. Call fit() first.")
        
        # Forecast
        forecast_result = self._model.get_forecast(steps=periods)
        y_pred = forecast_result.predicted_mean
        conf_int = forecast_result.conf_int()
        
        # Generate future dates
        future_dates = pd.date_range(
            start=self._last_date + self._freq,
            periods=periods,
            freq=self._freq
        )
        
        forecast = pd.DataFrame({
            'ds': future_dates,
            'yhat': y_pred,
            'yhat_lower': conf_int.iloc[:, 0],
            'yhat_upper': conf_int.iloc[:, 1],
        })
        
        # Calculate in-sample metrics
        fitted = self._model.fittedvalues
        metrics = self.calculate_metrics(self._y_train[1:], fitted[1:])  # Skip first NaN
        metrics['aic'] = float(self._model.aic)
        metrics['bic'] = float(self._model.bic)
        
        return ForecastResult(
            forecast=forecast,
            model_name=self.name,
            periods=periods,
            metrics=metrics,
        )


class ExponentialSmoothingForecaster(Forecaster):
    """
    Holt-Winters Exponential Smoothing.
    Best for: Data with trend and seasonality.
    """
    
    def __init__(
        self,
        trend: str = "add",
        seasonal: str = "add",
        seasonal_periods: int = 12,
    ):
        super().__init__("exponential_smoothing")
        self.trend = trend
        self.seasonal = seasonal
        self.seasonal_periods = seasonal_periods
    
    def fit(self, df: pd.DataFrame, date_col: str, value_col: str) -> "ExponentialSmoothingForecaster":
        """Fit Exponential Smoothing model"""
        try:
            from statsmodels.tsa.holtwinters import ExponentialSmoothing
        except ImportError:
            raise ImportError("statsmodels not installed")
        
        df = df[[date_col, value_col]].copy()
        df[date_col] = pd.to_datetime(df[date_col])
        df = df.dropna().sort_values(date_col)
        
        self._last_date = df[date_col].max()
        if len(df) > 1:
            diff = (df[date_col].iloc[1] - df[date_col].iloc[0]).days
            self._freq = timedelta(days=max(1, diff))
        else:
            self._freq = timedelta(days=1)
        
        y = df[value_col].values
        self._y_train = y
        
        # Fit model
        model = ExponentialSmoothing(
            y,
            trend=self.trend,
            seasonal=self.seasonal if len(y) >= 2 * self.seasonal_periods else None,
            seasonal_periods=self.seasonal_periods if len(y) >= 2 * self.seasonal_periods else None,
        )
        self._model = model.fit()
        
        self._is_fitted = True
        return self
    
    def predict(self, periods: int) -> ForecastResult:
        """Generate forecast"""
        if not self._is_fitted:
            raise ValueError("Model not fitted")
        
        y_pred = self._model.forecast(periods)
        
        future_dates = pd.date_range(
            start=self._last_date + self._freq,
            periods=periods,
            freq=self._freq
        )
        
        # Estimate confidence interval
        residuals = self._y_train - self._model.fittedvalues
        std = np.std(residuals)
        
        forecast = pd.DataFrame({
            'ds': future_dates,
            'yhat': y_pred,
            'yhat_lower': y_pred - 1.96 * std,
            'yhat_upper': y_pred + 1.96 * std,
        })
        
        metrics = self.calculate_metrics(self._y_train, self._model.fittedvalues)
        
        return ForecastResult(
            forecast=forecast,
            model_name=self.name,
            periods=periods,
            metrics=metrics,
        )
