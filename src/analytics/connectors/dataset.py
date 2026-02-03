"""
Dataset (CSV/Excel) Data Connector
"""
import io
import json
import logging
import time
from typing import Any, Dict, List, Optional
from datetime import datetime
import uuid

from .base import BaseConnector, ColumnInfo, TableInfo, QueryResult
from ..core.config import get_config
from ..core.exceptions import ConnectorError

logger = logging.getLogger(__name__)


def detect_column_type(series) -> str:
    """Detect column type from pandas series"""
    dtype = str(series.dtype)
    
    if 'int' in dtype:
        return 'integer'
    elif 'float' in dtype:
        return 'numeric'
    elif 'datetime' in dtype:
        return 'timestamp'
    elif 'date' in dtype:
        return 'date'
    elif 'bool' in dtype:
        return 'boolean'
    else:
        return 'text'


class DatasetConnector(BaseConnector):
    """Connector for uploaded CSV/Excel datasets"""
    
    def __init__(self, db_pool=None):
        self._db_pool = db_pool
        self._dataframes: Dict[str, Any] = {}  # Cache loaded dataframes
    
    @property
    def name(self) -> str:
        return "dataset"
    
    @property
    def connector_type(self) -> str:
        return "file"
    
    async def connect(self) -> bool:
        """Initialize - get DB pool for metadata"""
        if self._db_pool is None:
            try:
                from src.db import get_pool
                self._db_pool = await get_pool()
            except Exception as e:
                logger.error(f"Failed to get DB pool: {e}")
                return False
        return True
    
    async def disconnect(self) -> None:
        """Clear cached dataframes"""
        self._dataframes.clear()
    
    async def is_connected(self) -> bool:
        return self._db_pool is not None
    
    async def _load_dataset(self, dataset_id: str):
        """Load dataset from storage into a pandas DataFrame"""
        import pandas as pd
        from src.storage import get_document
        
        # Get dataset metadata
        async with self._db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM datasets WHERE id = $1",
                dataset_id
            )
        
        if not row:
            raise ConnectorError(f"Dataset not found: {dataset_id}")
        
        # Check cache
        if dataset_id in self._dataframes:
            return self._dataframes[dataset_id], row
        
        # Load from MinIO
        bucket = row["minio_bucket"]
        key = row["minio_key"]
        filename = row["filename"]
        
        try:
            file_data = get_document(bucket, key)
            
            if filename.endswith('.csv'):
                df = pd.read_csv(io.BytesIO(file_data))
            else:
                df = pd.read_excel(io.BytesIO(file_data))
            
            # Cache it
            self._dataframes[dataset_id] = df
            return df, row
            
        except Exception as e:
            logger.error(f"Failed to load dataset {dataset_id}: {e}")
            raise ConnectorError(f"Failed to load dataset: {e}")
    
    async def execute_query(self, sql: str, params: Optional[List] = None) -> QueryResult:
        """
        Execute query against a dataset using pandasql.
        Note: This is limited - for complex queries, consider duckdb.
        """
        # This connector doesn't support direct SQL
        # Queries should go through the NL2SQL engine which will
        # either convert to pandas operations or use the postgres connector
        return QueryResult(
            columns=[],
            rows=[],
            row_count=0,
            execution_time_ms=0,
            error="Direct SQL not supported on datasets. Use NL2SQL engine."
        )
    
    async def query_dataset(
        self, 
        dataset_id: str, 
        operations: Dict[str, Any]
    ) -> QueryResult:
        """
        Execute pandas operations on a dataset
        
        Operations format:
        {
            "select": ["col1", "col2"],  # columns to select
            "filter": {"col": "value"},   # filters
            "group_by": ["col"],          # grouping
            "agg": {"col": "sum"},        # aggregations
            "sort_by": "col",             # sorting
            "limit": 100                  # row limit
        }
        """
        import pandas as pd
        start_time = time.time()
        
        try:
            df, metadata = await self._load_dataset(dataset_id)
            result_df = df.copy()
            
            # Apply filters
            if "filter" in operations:
                for col, value in operations["filter"].items():
                    if col in result_df.columns:
                        result_df = result_df[result_df[col] == value]
            
            # Apply grouping and aggregation
            if "group_by" in operations and "agg" in operations:
                result_df = result_df.groupby(operations["group_by"]).agg(operations["agg"]).reset_index()
            
            # Select columns
            if "select" in operations:
                cols = [c for c in operations["select"] if c in result_df.columns]
                if cols:
                    result_df = result_df[cols]
            
            # Sort
            if "sort_by" in operations:
                sort_col = operations["sort_by"]
                ascending = operations.get("ascending", True)
                if sort_col in result_df.columns:
                    result_df = result_df.sort_values(sort_col, ascending=ascending)
            
            # Limit
            limit = operations.get("limit", 1000)
            result_df = result_df.head(limit)
            
            # Convert to result
            execution_time = (time.time() - start_time) * 1000
            
            # Handle NaN values
            result_df = result_df.fillna('')
            
            return QueryResult(
                columns=list(result_df.columns),
                rows=result_df.to_dict('records'),
                row_count=len(result_df),
                execution_time_ms=round(execution_time, 2)
            )
            
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            return QueryResult(
                columns=[],
                rows=[],
                row_count=0,
                execution_time_ms=round(execution_time, 2),
                error=str(e)
            )
    
    async def get_tables(self) -> List[TableInfo]:
        """List all available datasets as 'tables'"""
        if not self._db_pool:
            await self.connect()
        
        async with self._db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, name, filename, columns, row_count, table_name
                FROM datasets
                WHERE status = 'ready'
                ORDER BY created_at DESC
                """
            )
        
        tables = []
        for row in rows:
            columns_data = row.get("columns") or []
            if isinstance(columns_data, str):
                columns_data = json.loads(columns_data)
            
            columns = [
                ColumnInfo(
                    name=col.get("name", ""),
                    data_type=col.get("type", "text"),
                    nullable=col.get("nullable", True),
                    sample_values=col.get("sample_values", [])
                )
                for col in columns_data
            ]
            
            tables.append(TableInfo(
                name=row["table_name"] or row["name"],
                schema="datasets",
                columns=columns,
                row_count=row.get("row_count", 0),
                description=f"Uploaded dataset: {row['filename']}"
            ))
        
        return tables
    
    async def get_table_schema(self, table_name: str) -> Optional[TableInfo]:
        """Get schema for a specific dataset"""
        if not self._db_pool:
            await self.connect()
        
        async with self._db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, name, filename, columns, row_count, table_name
                FROM datasets
                WHERE table_name = $1 OR name = $1 OR id::text = $1
                """,
                table_name
            )
        
        if not row:
            return None
        
        columns_data = row.get("columns") or []
        if isinstance(columns_data, str):
            columns_data = json.loads(columns_data)
        
        columns = [
            ColumnInfo(
                name=col.get("name", ""),
                data_type=col.get("type", "text"),
                nullable=col.get("nullable", True),
                sample_values=col.get("sample_values", [])
            )
            for col in columns_data
        ]
        
        return TableInfo(
            name=row["table_name"] or row["name"],
            schema="datasets",
            columns=columns,
            row_count=row.get("row_count", 0),
            description=f"Uploaded dataset: {row['filename']}"
        )
    
    async def upload_dataset(
        self,
        file_data: bytes,
        filename: str,
        name: Optional[str] = None,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """Upload and register a new dataset"""
        import pandas as pd
        from src.storage import upload_document_v2
        
        if not self._db_pool:
            await self.connect()
        
        # Parse file
        try:
            if filename.endswith('.csv'):
                df = pd.read_csv(io.BytesIO(file_data))
                content_type = 'text/csv'
            else:
                df = pd.read_excel(io.BytesIO(file_data))
                content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        except Exception as e:
            raise ConnectorError(f"Failed to parse file: {e}")
        
        # Detect columns
        columns = []
        for col in df.columns:
            col_type = detect_column_type(df[col])
            sample_values = df[col].dropna().head(3).tolist()
            columns.append({
                "name": str(col),
                "type": col_type,
                "nullable": bool(df[col].isna().any()),
                "sample_values": [str(v) for v in sample_values]
            })
        
        # Generate IDs and names
        dataset_id = str(uuid.uuid4())
        dataset_name = name or filename.rsplit('.', 1)[0]
        
        # Sanitize table name
        import re
        table_name = re.sub(r'[^a-zA-Z0-9_]', '_', dataset_name.lower())[:60]
        if table_name and table_name[0].isdigit():
            table_name = 'ds_' + table_name
        
        # Upload to storage
        bucket = "erpx-documents"
        key = f"datasets/{dataset_id}/{filename}"
        
        try:
            upload_document_v2(file_data, filename, content_type, "default", dataset_id)
        except Exception as e:
            raise ConnectorError(f"Failed to store file: {e}")
        
        # Save metadata
        async with self._db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO datasets 
                (id, name, description, filename, content_type, file_size,
                 minio_bucket, minio_key, columns, row_count, table_name, status)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, 'ready')
                """,
                dataset_id,
                dataset_name,
                description,
                filename,
                content_type,
                len(file_data),
                bucket,
                key,
                json.dumps(columns),
                len(df),
                table_name
            )
        
        return {
            "id": dataset_id,
            "name": dataset_name,
            "filename": filename,
            "row_count": len(df),
            "columns": columns,
            "table_name": table_name,
            "status": "ready"
        }
    
    async def delete_dataset(self, dataset_id: str) -> bool:
        """Delete a dataset"""
        from src.storage import delete_document
        
        if not self._db_pool:
            await self.connect()
        
        async with self._db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT minio_bucket, minio_key FROM datasets WHERE id = $1",
                dataset_id
            )
            
            if not row:
                return False
            
            # Delete from storage
            try:
                if row["minio_bucket"] and row["minio_key"]:
                    delete_document(row["minio_bucket"], row["minio_key"])
            except Exception as e:
                logger.warning(f"Failed to delete from storage: {e}")
            
            # Delete from database
            await conn.execute("DELETE FROM datasets WHERE id = $1", dataset_id)
            
            # Clear from cache
            if dataset_id in self._dataframes:
                del self._dataframes[dataset_id]
        
        return True
