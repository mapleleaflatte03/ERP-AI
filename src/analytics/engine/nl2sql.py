"""
Natural Language to SQL Engine
"""
import logging
import re
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from ..connectors import PostgresConnector, QueryResult
from ..core.config import get_config
from ..core.exceptions import QueryError

logger = logging.getLogger(__name__)


@dataclass
class NL2SQLResult:
    """Result of NL2SQL conversion"""
    sql: str
    explanation: Optional[str] = None
    confidence: float = 0.0
    query_result: Optional[QueryResult] = None
    
    def to_dict(self) -> dict:
        result = {
            "sql": self.sql,
            "explanation": self.explanation,
            "confidence": self.confidence
        }
        if self.query_result:
            result["results"] = self.query_result.to_dict()
        return result


class NL2SQLEngine:
    """
    Natural Language to SQL conversion engine.
    Uses LLM to convert questions to SQL queries.
    """
    
    # SQL keywords that indicate potentially unsafe operations
    UNSAFE_KEYWORDS = [
        "DROP", "DELETE", "UPDATE", "INSERT", "TRUNCATE", 
        "ALTER", "CREATE", "GRANT", "REVOKE", "EXECUTE"
    ]
    
    def __init__(self, connector: Optional[PostgresConnector] = None):
        self._connector = connector or PostgresConnector()
        self._schema_cache: Optional[str] = None
        self._llm_client = None
    
    async def _get_llm_client(self):
        """Get LLM client lazily"""
        if self._llm_client is None:
            try:
                from services.llm.do_agent import DoAgentClient
                self._llm_client = DoAgentClient()
            except ImportError:
                from src.llm.client import get_llm_client
                self._llm_client = get_llm_client()
        return self._llm_client
    
    async def _get_schema_context(self) -> str:
        """Get database schema context for the LLM"""
        if self._schema_cache is None:
            await self._connector.connect()
            self._schema_cache = await self._connector.get_schema_summary()
        return self._schema_cache
    
    def _validate_sql(self, sql: str) -> tuple[bool, Optional[str]]:
        """Validate SQL for safety"""
        sql_upper = sql.upper()
        
        # Must start with SELECT or WITH
        if not (sql_upper.strip().startswith("SELECT") or sql_upper.strip().startswith("WITH")):
            return False, "Query must be a SELECT statement"
        
        # Check for unsafe keywords
        for keyword in self.UNSAFE_KEYWORDS:
            # Use word boundary to avoid false positives
            if re.search(rf'\b{keyword}\b', sql_upper):
                return False, f"Query contains forbidden keyword: {keyword}"
        
        return True, None
    
    def _clean_sql(self, sql: str) -> str:
        """Clean up SQL from LLM output"""
        # Remove markdown code blocks
        sql = re.sub(r'```sql\s*', '', sql)
        sql = re.sub(r'```\s*', '', sql)
        
        # Remove leading "SQL:" prefix
        sql = re.sub(r'^SQL:\s*', '', sql, flags=re.IGNORECASE)
        
        # Strip whitespace
        sql = sql.strip()
        
        # Ensure it ends with semicolon (optional, PostgreSQL doesn't require it)
        # sql = sql.rstrip(';') + ';'
        
        return sql
    
    async def convert(
        self, 
        question: str,
        include_sample_data: bool = True,
        additional_context: Optional[str] = None
    ) -> NL2SQLResult:
        """
        Convert a natural language question to SQL.
        
        Args:
            question: The natural language question
            include_sample_data: Whether to include sample data in context
            additional_context: Additional context to include
            
        Returns:
            NL2SQLResult with generated SQL
        """
        llm = await self._get_llm_client()
        schema = await self._get_schema_context()
        config = get_config()
        
        # Build prompt
        prompt = f"""You are an expert PostgreSQL SQL writer. Convert the user's question to a SQL query.

DATABASE SCHEMA:
{schema}

{f'ADDITIONAL CONTEXT: {additional_context}' if additional_context else ''}

USER QUESTION: {question}

RULES:
1. Return ONLY the SQL query, no explanations or markdown
2. Use proper PostgreSQL syntax
3. Limit results to {config.max_query_rows} rows unless specified otherwise
4. Use ILIKE for case-insensitive text search (Vietnamese support)
5. Format dates as YYYY-MM-DD
6. Use aggregate functions (SUM, COUNT, AVG, etc.) when appropriate
7. ONLY write SELECT queries - no data modification
8. Use table aliases for clarity
9. Handle NULL values appropriately with COALESCE when needed
10. For currency/amounts, assume VND unless specified

SQL:"""

        try:
            response = await llm.generate(prompt, max_tokens=1000)
            # Handle both string and LLMResponse object
            if hasattr(response, 'content'):
                response_text = response.content
            else:
                response_text = str(response)
            sql = self._clean_sql(response_text)
            
            # Validate
            is_valid, error = self._validate_sql(sql)
            if not is_valid:
                return NL2SQLResult(
                    sql=sql,
                    explanation=error,
                    confidence=0.0
                )
            
            return NL2SQLResult(
                sql=sql,
                confidence=0.85  # Default confidence
            )
            
        except Exception as e:
            logger.error(f"NL2SQL conversion failed: {e}")
            raise QueryError(f"Failed to convert question to SQL: {e}")
    
    async def query(
        self,
        question: str,
        execute: bool = True,
        limit: Optional[int] = None
    ) -> NL2SQLResult:
        """
        Convert question to SQL and optionally execute it.
        
        Args:
            question: Natural language question
            execute: Whether to execute the query
            limit: Override default row limit
            
        Returns:
            NL2SQLResult with SQL and optionally query results
        """
        # Convert to SQL
        result = await self.convert(question)
        
        if not execute or result.confidence == 0.0:
            return result
        
        # Apply limit if specified
        sql = result.sql
        if limit and "LIMIT" not in sql.upper():
            sql = f"{sql.rstrip(';')} LIMIT {limit}"
        
        # Execute query
        await self._connector.connect()
        query_result = await self._connector.execute_query(sql)
        
        return NL2SQLResult(
            sql=sql,
            explanation=result.explanation,
            confidence=result.confidence,
            query_result=query_result
        )
    
    async def explain_sql(self, sql: str) -> str:
        """Explain what a SQL query does in natural language"""
        llm = await self._get_llm_client()
        
        prompt = f"""Explain this SQL query in simple Vietnamese:

SQL:
{sql}

Explanation (in Vietnamese):"""

        try:
            response = await llm.generate(prompt, max_tokens=500)
            return response.strip()
        except Exception as e:
            logger.error(f"SQL explanation failed: {e}")
            return f"Không thể giải thích câu truy vấn: {e}"
    
    async def suggest_queries(self, context: Optional[str] = None) -> List[str]:
        """Suggest useful queries based on available data"""
        llm = await self._get_llm_client()
        schema = await self._get_schema_context()
        
        prompt = f"""Based on this database schema, suggest 5 useful analytics questions a financial analyst might ask.

SCHEMA:
{schema}

{f'CONTEXT: {context}' if context else ''}

Return as a numbered list in Vietnamese:"""

        try:
            response = await llm.generate(prompt, max_tokens=500)
            # Parse numbered list
            lines = response.strip().split('\n')
            suggestions = []
            for line in lines:
                line = line.strip()
                if line and line[0].isdigit():
                    # Remove number prefix
                    text = re.sub(r'^\d+[\.\)]\s*', '', line)
                    if text:
                        suggestions.append(text)
            return suggestions[:5]
        except Exception as e:
            logger.error(f"Query suggestion failed: {e}")
            return [
                "Tổng doanh thu theo tháng",
                "Top 10 nhà cung cấp theo số tiền",
                "Số lượng hóa đơn theo trạng thái",
                "Trung bình giá trị hóa đơn",
                "Hóa đơn có giá trị cao nhất"
            ]
    
    def invalidate_cache(self) -> None:
        """Invalidate schema cache"""
        self._schema_cache = None
