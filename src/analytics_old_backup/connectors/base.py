"""
Base Connector Interface
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from dataclasses import dataclass


@dataclass
class ColumnInfo:
    """Column metadata"""
    name: str
    data_type: str
    nullable: bool = True
    description: Optional[str] = None
    sample_values: Optional[List[Any]] = None


@dataclass
class TableInfo:
    """Table metadata"""
    name: str
    schema: str = "public"
    columns: List[ColumnInfo] = None
    row_count: Optional[int] = None
    description: Optional[str] = None
    
    def __post_init__(self):
        if self.columns is None:
            self.columns = []


@dataclass
class QueryResult:
    """Result of a query execution"""
    columns: List[str]
    rows: List[Dict[str, Any]]
    row_count: int
    execution_time_ms: float
    sql: Optional[str] = None
    error: Optional[str] = None
    
    @property
    def success(self) -> bool:
        return self.error is None
    
    def to_dict(self) -> dict:
        return {
            "columns": self.columns,
            "rows": self.rows,
            "row_count": self.row_count,
            "execution_time_ms": self.execution_time_ms,
            "sql": self.sql,
            "error": self.error,
            "success": self.success
        }


class BaseConnector(ABC):
    """Abstract base class for data connectors"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Connector name"""
        pass
    
    @property
    @abstractmethod
    def connector_type(self) -> str:
        """Connector type (database, file, api, etc.)"""
        pass
    
    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection"""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection"""
        pass
    
    @abstractmethod
    async def is_connected(self) -> bool:
        """Check if connected"""
        pass
    
    @abstractmethod
    async def execute_query(self, sql: str, params: Optional[List] = None) -> QueryResult:
        """Execute a SQL query"""
        pass
    
    @abstractmethod
    async def get_tables(self) -> List[TableInfo]:
        """List available tables"""
        pass
    
    @abstractmethod
    async def get_table_schema(self, table_name: str) -> Optional[TableInfo]:
        """Get schema for a specific table"""
        pass
    
    async def get_sample_data(self, table_name: str, limit: int = 5) -> QueryResult:
        """Get sample data from a table"""
        return await self.execute_query(f'SELECT * FROM "{table_name}" LIMIT {limit}')
    
    async def get_row_count(self, table_name: str) -> int:
        """Get row count for a table"""
        result = await self.execute_query(f'SELECT COUNT(*) as cnt FROM "{table_name}"')
        if result.success and result.rows:
            return result.rows[0].get("cnt", 0)
        return 0
    
    def get_schema_context(self, tables: List[TableInfo]) -> str:
        """Generate schema context string for LLM"""
        lines = []
        for table in tables:
            lines.append(f"Table: {table.schema}.{table.name}")
            if table.description:
                lines.append(f"  Description: {table.description}")
            for col in table.columns:
                nullable = "NULL" if col.nullable else "NOT NULL"
                lines.append(f"  - {col.name}: {col.data_type} ({nullable})")
            lines.append("")
        return "\n".join(lines)
