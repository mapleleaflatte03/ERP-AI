"""
File Connector
Handle CSV, Excel, Parquet files from local filesystem or MinIO
"""
import pandas as pd
import io
from typing import Any, Dict, List, Optional
from pathlib import Path
import time
import logging

from .base import DataConnector, TableSchema, QueryResult
from ..core.config import get_config, MinIOConfig
from ..core.exceptions import DataConnectionError, DataNotFoundError

logger = logging.getLogger(__name__)


class FileConnector(DataConnector):
    """
    File-based data connector.
    Supports CSV, Excel, Parquet files from local filesystem or MinIO.
    """
    
    SUPPORTED_EXTENSIONS = {'.csv', '.xlsx', '.xls', '.parquet', '.json'}
    
    def __init__(self, name: str = "files"):
        super().__init__(name)
        self._minio_client = None
        self._files_cache: Dict[str, pd.DataFrame] = {}
    
    async def connect(self) -> None:
        """Initialize MinIO client if configured"""
        try:
            from minio import Minio
            config = get_config().minio
            self._minio_client = Minio(
                config.endpoint,
                access_key=config.access_key,
                secret_key=config.secret_key,
                secure=config.secure,
            )
            self._connected = True
            logger.info(f"FileConnector connected to MinIO: {config.endpoint}")
        except Exception as e:
            logger.warning(f"MinIO not available, using local files only: {e}")
            self._connected = True
    
    async def disconnect(self) -> None:
        """Clear cache and disconnect"""
        self._files_cache.clear()
        self._minio_client = None
        self._connected = False
    
    def load_file(self, path: str) -> pd.DataFrame:
        """Load a file from local path or MinIO"""
        # Check cache first
        if path in self._files_cache:
            return self._files_cache[path]
        
        try:
            # Determine if MinIO path (bucket/key format) or local
            if '/' in path and self._minio_client:
                parts = path.split('/', 1)
                if len(parts) == 2:
                    bucket, key = parts
                    try:
                        response = self._minio_client.get_object(bucket, key)
                        file_bytes = response.read()
                        response.close()
                        df = self._parse_bytes(file_bytes, key)
                        self._files_cache[path] = df
                        return df
                    except Exception as e:
                        logger.debug(f"MinIO load failed, trying local: {e}")
            
            # Try local file
            local_path = Path(path)
            if local_path.exists():
                df = self._parse_file(local_path)
                self._files_cache[path] = df
                return df
            
            raise DataNotFoundError(f"File not found: {path}")
            
        except DataNotFoundError:
            raise
        except Exception as e:
            raise DataConnectionError(f"Failed to load file {path}: {e}")
    
    def _parse_file(self, path: Path) -> pd.DataFrame:
        """Parse a local file into DataFrame"""
        suffix = path.suffix.lower()
        
        if suffix == '.csv':
            return pd.read_csv(path)
        elif suffix in ('.xlsx', '.xls'):
            return pd.read_excel(path)
        elif suffix == '.parquet':
            return pd.read_parquet(path)
        elif suffix == '.json':
            return pd.read_json(path)
        else:
            raise ValueError(f"Unsupported file format: {suffix}")
    
    def _parse_bytes(self, data: bytes, filename: str) -> pd.DataFrame:
        """Parse bytes into DataFrame based on filename extension"""
        suffix = Path(filename).suffix.lower()
        
        if suffix == '.csv':
            return pd.read_csv(io.BytesIO(data))
        elif suffix in ('.xlsx', '.xls'):
            return pd.read_excel(io.BytesIO(data))
        elif suffix == '.parquet':
            return pd.read_parquet(io.BytesIO(data))
        elif suffix == '.json':
            return pd.read_json(io.BytesIO(data))
        else:
            # Try CSV as default
            return pd.read_csv(io.BytesIO(data))
    
    async def execute(self, query: str, params: Dict[str, Any] = None) -> QueryResult:
        """
        Execute a query on loaded files.
        Query format: SELECT * FROM 'path/to/file.csv' WHERE ...
        Uses pandasql for SQL queries on DataFrames.
        """
        start_time = time.time()
        
        try:
            import pandasql as ps
            
            # Extract file paths from query and load them
            # Simple implementation - assumes query references loaded DataFrames
            if params and 'dataframe' in params:
                df = params['dataframe']
            else:
                # For now, return empty result if no specific handling
                return QueryResult(
                    data=pd.DataFrame(),
                    row_count=0,
                    columns=[],
                    execution_time_ms=0,
                    query=query,
                )
            
            result = ps.sqldf(query, {'df': df})
            execution_time = (time.time() - start_time) * 1000
            
            return QueryResult(
                data=result,
                row_count=len(result),
                columns=list(result.columns),
                execution_time_ms=execution_time,
                query=query,
            )
        except ImportError:
            logger.warning("pandasql not installed, SQL queries on files not supported")
            return QueryResult(
                data=pd.DataFrame(),
                row_count=0,
                columns=[],
                execution_time_ms=0,
                query=query,
            )
        except Exception as e:
            raise DataConnectionError(f"Query execution failed: {e}")
    
    async def get_tables(self) -> List[TableSchema]:
        """List loaded files as tables"""
        tables = []
        for path, df in self._files_cache.items():
            tables.append(TableSchema(
                name=path,
                columns=[{"name": c, "type": str(df[c].dtype)} for c in df.columns],
                row_count=len(df),
            ))
        return tables
    
    async def get_table_schema(self, table_name: str) -> TableSchema:
        """Get schema for a loaded file"""
        if table_name not in self._files_cache:
            # Try to load it
            df = self.load_file(table_name)
        else:
            df = self._files_cache[table_name]
        
        return TableSchema(
            name=table_name,
            columns=[
                {
                    "name": col,
                    "type": str(df[col].dtype),
                    "nullable": df[col].isnull().any(),
                    "unique_count": df[col].nunique(),
                }
                for col in df.columns
            ],
            row_count=len(df),
            size_bytes=df.memory_usage(deep=True).sum(),
        )
    
    def get_dataframe(self, path: str) -> pd.DataFrame:
        """Get DataFrame for a file path"""
        return self.load_file(path)
    
    def clear_cache(self) -> None:
        """Clear the file cache"""
        self._files_cache.clear()
