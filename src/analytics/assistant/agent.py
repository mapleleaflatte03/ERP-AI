"""
Analytics AI Agent - Enhanced with Tool Execution
"""
import json
import logging
import re
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from .prompts import SYSTEM_PROMPT
from .memory import ConversationMemory, get_memory
from .agent_tools import get_tool_executor, parse_tool_call, get_tools_description
from ..core.config import get_config

logger = logging.getLogger(__name__)


@dataclass
class AgentResponse:
    """Response from the agent"""
    message: str
    tool_calls: List[Dict] = None
    tool_results: List[Dict] = None
    visualizations: List[Dict] = None
    session_id: str = None
    
    def to_dict(self) -> dict:
        return {
            "message": self.message,
            "tool_calls": self.tool_calls,
            "tool_results": self.tool_results,
            "visualizations": self.visualizations,
            "session_id": self.session_id
        }


# Enhanced system prompt with tool instructions
ANALYTICS_SYSTEM_PROMPT = """Bạn là trợ lý phân tích dữ liệu tài chính AI. Bạn có thể:
- Liệt kê và phân tích datasets
- Thực hiện các phép tính thống kê
- Tạo biểu đồ và báo cáo

KHI CẦN DỮ LIỆU, HÃY SỬ DỤNG TOOL THEO FORMAT SAU:

```tool
{"name": "tool_name", "params": {"param1": "value1"}}
```

CÁC TOOLS CÓ SẴN:

1. list_datasets - Liệt kê tất cả datasets
   Ví dụ: ```tool
   {"name": "list_datasets", "params": {}}
   ```

2. load_dataset - Load một dataset theo tên
   Ví dụ: ```tool
   {"name": "load_dataset", "params": {"dataset_name": "FPT Stock Data"}}
   ```

3. describe_dataset - Mô tả thống kê của dataset
   Ví dụ: ```tool
   {"name": "describe_dataset", "params": {"dataset_name": "FPT Stock Data"}}
   ```

4. get_sample - Lấy mẫu dữ liệu
   Ví dụ: ```tool
   {"name": "get_sample", "params": {"dataset_name": "FPT Stock Data", "n": 5}}
   ```

5. aggregate_data - Tính toán aggregate (sum, mean, count, min, max)
   Ví dụ: ```tool
   {"name": "aggregate_data", "params": {"dataset_name": "FPT Stock Data", "group_by": "Ticker", "agg_column": "Volume", "agg_func": "sum"}}
   ```

6. filter_data - Lọc dữ liệu theo điều kiện
   Ví dụ: ```tool
   {"name": "filter_data", "params": {"dataset_name": "FPT Stock Data", "column": "Close", "operator": ">", "value": 100}}
   ```

7. create_chart - Tạo biểu đồ
   Ví dụ: ```tool
   {"name": "create_chart", "params": {"dataset_name": "FPT Stock Data", "chart_type": "line", "x_column": "Date", "y_column": "Close"}}
   ```

LUÔN sử dụng tool khi cần lấy hoặc xử lý dữ liệu. Sau khi nhận kết quả tool, hãy giải thích kết quả cho người dùng."""


class AnalyticsAgent:
    """
    AI Agent for analytics with tool execution.
    """
    
    def __init__(
        self,
        memory: Optional[ConversationMemory] = None
    ):
        self._memory = memory or get_memory()
        self._tool_executor = get_tool_executor()
        self._llm_client = None
        self._config = get_config()
    
    async def _get_llm_client(self):
        """Get LLM client lazily"""
        if self._llm_client is None:
            from src.llm.client import get_llm_client
            self._llm_client = get_llm_client()
        return self._llm_client
    
    async def chat(
        self,
        message: str,
        session_id: Optional[str] = None,
        max_tool_calls: int = 5
    ) -> AgentResponse:
        """
        Process a chat message, execute tools if needed, return response.
        """
        # Get or create session
        session = self._memory.get_or_create_session(session_id)
        
        # Add user message
        session.add_message("user", message)
        
        # Get LLM client
        llm = await self._get_llm_client()
        
        # Build prompt with conversation context
        messages = session.get_messages_for_llm()
        
        prompt = f"""{ANALYTICS_SYSTEM_PROMPT}

CONVERSATION HISTORY:
"""
        for msg in messages[-6:]:  # Last 6 messages for context
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role != "system":
                prompt += f"\n{role.upper()}: {content}"
        
        prompt += f"\n\nUSER: {message}\n\nASSISTANT:"
        
        try:
            # Get LLM response
            response = await llm.generate(prompt, max_tokens=2000)
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # Check for tool calls and execute them
            tool_calls = []
            tool_results = []
            visualizations = []
            
            # Parse and execute tool calls
            parsed = parse_tool_call(response_text)
            call_count = 0
            
            while parsed and call_count < max_tool_calls:
                tool_name, params = parsed
                tool_calls.append({"name": tool_name, "params": params})
                
                # Execute the tool
                result = await self._tool_executor.execute(tool_name, params)
                tool_results.append({
                    "tool": tool_name,
                    "result": result
                })
                
                # Check for visualizations
                if result.get("chart"):
                    visualizations.append(result["chart"])
                
                call_count += 1
                
                # If tool was executed, get follow-up response
                if result.get("success"):
                    result_summary = self._summarize_result(result)
                    
                    # Ask LLM to explain the result
                    followup_prompt = f"""{ANALYTICS_SYSTEM_PROMPT}

Tool {tool_name} đã được thực thi với kết quả:
{result_summary}

Hãy giải thích kết quả này cho người dùng một cách ngắn gọn và dễ hiểu.
USER: {message}
ASSISTANT:"""
                    
                    followup = await llm.generate(followup_prompt, max_tokens=1000)
                    response_text = followup.content if hasattr(followup, 'content') else str(followup)
                    
                    # Check for more tool calls in followup
                    parsed = parse_tool_call(response_text)
                else:
                    # Tool failed, include error in response
                    response_text = f"Đã xảy ra lỗi khi thực hiện {tool_name}: {result.get('error', 'Unknown error')}"
                    parsed = None
            
            # Add assistant response to session
            session.add_message("assistant", response_text)
            
            return AgentResponse(
                message=response_text,
                tool_calls=tool_calls if tool_calls else None,
                tool_results=tool_results if tool_results else None,
                visualizations=visualizations if visualizations else None,
                session_id=session.id
            )
            
        except Exception as e:
            logger.error(f"Agent error: {e}", exc_info=True)
            return AgentResponse(
                message=f"Xin lỗi, đã xảy ra lỗi: {str(e)}",
                session_id=session.id
            )
    
    def _summarize_result(self, result: Dict) -> str:
        """Create a summary of tool result for LLM context"""
        if not result.get("success"):
            return f"Error: {result.get('error')}"
        
        parts = []
        
        if "datasets" in result:
            datasets = result["datasets"]
            parts.append(f"Có {len(datasets)} datasets:")
            for ds in datasets[:5]:
                parts.append(f"  - {ds.get('name')}: {ds.get('row_count', 0)} rows")
        
        if "data" in result:
            data = result["data"]
            if isinstance(data, list):
                parts.append(f"Dữ liệu: {len(data)} rows")
                if data:
                    parts.append(f"Sample: {json.dumps(data[0], ensure_ascii=False)[:200]}")
        
        if "statistics" in result:
            stats = result["statistics"]
            parts.append(f"Thống kê: {json.dumps(stats, ensure_ascii=False)[:300]}")
        
        if "aggregation" in result:
            agg = result["aggregation"]
            parts.append(f"Kết quả: {json.dumps(agg, ensure_ascii=False)[:300]}")
        
        if "chart" in result:
            chart = result["chart"]
            parts.append(f"Biểu đồ: {chart.get('type')} chart created")
        
        return "\n".join(parts) if parts else json.dumps(result, ensure_ascii=False)[:500]
    
    def get_session_history(self, session_id: str) -> Optional[Dict]:
        """Get conversation history for a session"""
        session = self._memory.get_session(session_id)
        if session:
            return session.to_dict()
        return None
    
    def list_sessions(self, limit: int = 20) -> List[Dict]:
        """List recent sessions"""
        return self._memory.list_sessions(limit)
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a session"""
        return self._memory.delete_session(session_id)


# Singleton agent instance
_agent_instance = None


def get_agent() -> AnalyticsAgent:
    """Get singleton agent instance"""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = AnalyticsAgent()
    return _agent_instance
