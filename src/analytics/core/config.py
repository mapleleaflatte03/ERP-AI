"""
Analytics Module Configuration
"""
import os
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from urllib.parse import urlparse


def parse_database_url() -> Dict[str, Any]:
    """Parse DATABASE_URL environment variable"""
    database_url = os.getenv("DATABASE_URL", "")
    if database_url:
        parsed = urlparse(database_url)
        return {
            "host": parsed.hostname or "localhost",
            "port": parsed.port or 5432,
            "database": parsed.path.lstrip("/") or "erpx",
            "user": parsed.username or "postgres",
            "password": parsed.password or "postgres",
        }
    return {}


@dataclass
class DatabaseConfig:
    """Database connection configuration"""
    host: str = field(default_factory=lambda: parse_database_url().get("host") or os.getenv("POSTGRES_HOST", "localhost"))
    port: int = field(default_factory=lambda: int(parse_database_url().get("port") or os.getenv("POSTGRES_PORT", "5432")))
    database: str = field(default_factory=lambda: parse_database_url().get("database") or os.getenv("POSTGRES_DB", "erpx"))
    user: str = field(default_factory=lambda: parse_database_url().get("user") or os.getenv("POSTGRES_USER", "postgres"))
    password: str = field(default_factory=lambda: parse_database_url().get("password") or os.getenv("POSTGRES_PASSWORD", "postgres"))
    
    @property
    def dsn(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"
    
    @property
    def async_dsn(self) -> str:
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"


@dataclass
class LLMConfig:
    """LLM configuration for AI assistant"""
    provider: str = field(default_factory=lambda: os.getenv("LLM_PROVIDER", "openai"))
    model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "gpt-4o-mini"))
    api_key: Optional[str] = field(default_factory=lambda: os.getenv("OPENAI_API_KEY"))
    temperature: float = 0.1
    max_tokens: int = 4000


@dataclass
class MetabaseConfig:
    """Metabase BI integration configuration"""
    enabled: bool = field(default_factory=lambda: os.getenv("METABASE_ENABLED", "false").lower() == "true")
    url: str = field(default_factory=lambda: os.getenv("METABASE_URL", "http://metabase:3000"))
    username: str = field(default_factory=lambda: os.getenv("METABASE_USERNAME", "admin@erpx.local"))
    password: str = field(default_factory=lambda: os.getenv("METABASE_PASSWORD", ""))
    secret_key: str = field(default_factory=lambda: os.getenv("METABASE_SECRET_KEY", ""))


@dataclass
class ForecastConfig:
    """Forecasting configuration"""
    default_horizon: int = 30  # days
    default_model: str = "prophet"  # prophet, linear, arima
    confidence_interval: float = 0.95


@dataclass
class AnalyticsConfig:
    """Main analytics configuration"""
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    metabase: MetabaseConfig = field(default_factory=MetabaseConfig)
    forecast: ForecastConfig = field(default_factory=ForecastConfig)
    
    # Query limits
    max_query_rows: int = 10000
    query_timeout_seconds: int = 30
    
    # Feature flags
    enable_forecasting: bool = True
    enable_data_quality: bool = True
    enable_dbt: bool = False  # Enable when dbt is setup
    
    @classmethod
    def from_env(cls) -> "AnalyticsConfig":
        """Create config from environment variables"""
        return cls()


# Global config instance
_config: Optional[AnalyticsConfig] = None


def get_config() -> AnalyticsConfig:
    """Get or create the analytics configuration"""
    global _config
    if _config is None:
        _config = AnalyticsConfig.from_env()
    return _config


def set_config(config: AnalyticsConfig) -> None:
    """Set the analytics configuration (for testing)"""
    global _config
    _config = config
