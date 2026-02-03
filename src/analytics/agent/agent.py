"""
Analytics AI Agent
LLM-powered agent with tool execution for data analysis
"""
import json
import re
import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

from ..core.registry import get_registry
from ..core.exceptions import ToolExecutionError
from .memory import ConversationMemory

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """Bạn là trợ lý phân tích dữ liệu tài chính AI chuyên nghiệp.

KHẢN NĂNG CỦA BẠN:
1. Truy vấn và phân tích dữ liệu từ datasets
2. Tạo báo cáo thống kê mô tả
3. Dự báo xu hướng tài chính
4. Kiểm tra chất lượng dữ liệu
5. Tạo biểu đồ và trực quan hóa

CÁCH SỬ DỤNG TOOL:
Khi cần lấy hoặc xử lý dữ liệu, gọi tool bằng format JSON:

```tool
{"name": "tool_name", "params": {"param1": "value1"}}
```

{tools_description}

QUY TẮC QUAN TRỌNG:
1. LUÔN đọc kỹ kết quả tool trước khi trả lời
2. Trích dẫn số liệu CHÍNH XÁC từ tool_results
3. Nếu không có dữ liệu, nói rõ và đề xuất giải pháp
4. Giải thích kết quả dễ hiểu cho người dùng
5. Khi so sánh, luôn load cả hai datasets trước

VÍ DỤ:
User: "Liệt kê các datasets"
Assistant: Để liệt kê datasets, tôi sẽ gọi tool:
```tool
{"name": "list_datasets", "params": {}}
```

User: "Phân tích FPT Stock Data"
Assistant: Tôi sẽ load và mô tả dataset:
```tool
{"name": "describe_dataset", "params": {"dataset_name": "FPT Stock Data"}}
```
"""


@dataclass
class ToolCall:
    """Represents a tool call parsed from LLM response"""
    name: str
    params: Dict[str, Any]
    raw: str = ""


@dataclass
class ToolResult:
    """Result of tool execution"""
    tool: str
    success: bool
    result: Any
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool": self.tool,
            "success": self.success,
            "result": self.result,
            "error": self.error,
        }


@dataclass
class AgentResponse:
    """Complete agent response"""
    message: str
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    tool_results: List[Dict[str, Any]] = field(default_factory=list)
    visualizations: List[Dict[str, Any]] = field(default_factory=list)
    session_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "message": self.message,
            "tool_calls": self.tool_calls,
            "tool_results": self.tool_results,
            "visualizations": self.visualizations,
            "session_id": self.session_id,
        }


class AnalyticsAgent:
    """
    AI-powered analytics agent.
    
    Features:
    - Natural language understanding
    - Tool execution for data operations
    - Conversation memory
    - Multi-turn interactions
    
    Usage:
        agent = AnalyticsAgent()
        response = await agent.chat("List all datasets")
        print(response.message)
    """
    
    def __init__(
        self,
        llm_provider: str = "openai",
        model: str = "gpt-4o-mini",
        memory: Optional[ConversationMemory] = None,
    ):
        self.llm_provider = llm_provider
        self.model = model
        self.memory = memory or ConversationMemory()
        self.registry = get_registry()
        self._llm_client = None
    
    def _get_llm_client(self):
        """Get or create LLM client"""
        if self._llm_client is None:
            if self.llm_provider == "openai":
                from openai import OpenAI
                self._llm_client = OpenAI()
            else:
                raise ValueError(f"Unsupported LLM provider: {self.llm_provider}")
        return self._llm_client
    
    def _build_system_prompt(self) -> str:
        """Build system prompt with available tools"""
        tools_desc = self.registry.get_tools_prompt()
        return SYSTEM_PROMPT.format(tools_description=tools_desc)
    
    def _parse_tool_calls(self, text: str) -> List[ToolCall]:
        """Parse tool calls from LLM response"""
        tool_calls = []
        
        # Pattern: ```tool\n{...}\n```
        pattern = r'```tool\s*\n?\s*(\{[^`]+\})\s*\n?```'
        matches = re.findall(pattern, text, re.DOTALL)
        
        for match in matches:
            try:
                data = json.loads(match.strip())
                if isinstance(data, dict) and 'name' in data:
                    tool_calls.append(ToolCall(
                        name=data['name'],
                        params=data.get('params', {}),
                        raw=match,
                    ))
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse tool call: {e}")
        
        return tool_calls
    
    async def _execute_tool(self, tool_call: ToolCall) -> ToolResult:
        """Execute a single tool"""
        try:
            result = await self.registry.execute(tool_call.name, tool_call.params)
            return ToolResult(
                tool=tool_call.name,
                success=True,
                result=result,
            )
        except Exception as e:
            logger.error(f"Tool execution failed: {tool_call.name} - {e}")
            return ToolResult(
                tool=tool_call.name,
                success=False,
                result=None,
                error=str(e),
            )
    
    def _call_llm(self, messages: List[Dict[str, str]]) -> str:
        """Call LLM and get response"""
        client = self._get_llm_client()
        
        response = client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.1,
            max_tokens=4096,
        )
        
        return response.choices[0].message.content
    
    async def chat(
        self, 
        message: str, 
        session_id: Optional[str] = None
    ) -> AgentResponse:
        """
        Process user message and return response.
        
        Args:
            message: User's message
            session_id: Session ID for conversation continuity
            
        Returns:
            AgentResponse with message, tool calls, and results
        """
        # Build conversation context
        system_prompt = self._build_system_prompt()
        
        messages = [
            {"role": "system", "content": system_prompt}
        ]
        
        # Add conversation history
        if session_id:
            history = self.memory.get_history(session_id)
            for entry in history[-10:]:  # Last 10 messages
                if entry["role"] != "system":
                    messages.append(entry)
        
        # Add current user message
        messages.append({"role": "user", "content": message})
        
        # Get initial LLM response
        llm_response = self._call_llm(messages)
        
        # Parse and execute tool calls
        tool_calls = self._parse_tool_calls(llm_response)
        tool_results: List[ToolResult] = []
        
        if tool_calls:
            for tc in tool_calls:
                result = await self._execute_tool(tc)
                tool_results.append(result)
            
            # Get follow-up response with tool results
            tool_results_text = "\n".join([
                f"Tool: {r.tool}\nResult: {json.dumps(r.result, default=str, ensure_ascii=False)}"
                for r in tool_results
            ])
            
            messages.append({"role": "assistant", "content": llm_response})
            messages.append({
                "role": "user",
                "content": f"Đây là kết quả tool:\n{tool_results_text}\n\nHãy giải thích kết quả cho người dùng."
            })
            
            final_response = self._call_llm(messages)
        else:
            final_response = llm_response
        
        # Extract visualizations if any
        visualizations = []
        for r in tool_results:
            if r.success and r.result and isinstance(r.result, dict):
                if 'chart' in r.result or 'visualization' in r.result:
                    visualizations.append(r.result)
        
        # Save to memory
        new_session_id = session_id or self.memory.new_session()
        self.memory.add_message(new_session_id, "user", message)
        self.memory.add_message(new_session_id, "assistant", final_response)
        
        return AgentResponse(
            message=final_response,
            tool_calls=[{"name": tc.name, "params": tc.params} for tc in tool_calls],
            tool_results=[r.to_dict() for r in tool_results],
            visualizations=visualizations,
            session_id=new_session_id,
        )
    
    def clear_memory(self, session_id: str = None) -> None:
        """Clear conversation memory"""
        if session_id:
            self.memory.clear_session(session_id)
        else:
            self.memory.clear_all()
