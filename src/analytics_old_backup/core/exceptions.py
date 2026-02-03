"""
Custom Exceptions for Analytics Module
"""


class AnalyticsError(Exception):
    """Base exception for analytics module"""
    pass


class ConnectorError(AnalyticsError):
    """Error in data connector"""
    pass


class QueryError(AnalyticsError):
    """Error executing query"""
    pass


class ValidationError(AnalyticsError):
    """Data validation error"""
    pass


class ForecastError(AnalyticsError):
    """Error in forecasting"""
    pass


class ConfigurationError(AnalyticsError):
    """Configuration error"""
    pass


class ToolExecutionError(AnalyticsError):
    """Error executing AI tool"""
    pass


class RateLimitError(AnalyticsError):
    """Rate limit exceeded"""
    pass


class PermissionError(AnalyticsError):
    """Insufficient permissions"""
    pass


class DataQualityError(AnalyticsError):
    """Data quality check failed"""
    def __init__(self, message: str, failures: list = None):
        super().__init__(message)
        self.failures = failures or []
