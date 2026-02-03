"""
Analytics AI Agent
"""
import json
import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from .tools import ToolExecutor, TOOL_DEFINITIONS
from .prompts import SYSTEM_PROMPT
from .memory import ConversationMemory, ConversationSession, get_memory
from ..core.config import get_config
from ..core.exceptions import ToolExecutionError

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


class AnalyticsAgent:
    """
    AI Agent for analytics queries and analysis.
    Uses function calling to execute tools.
    """
    
    def __init__(
        self,
        memory: Optional[ConversationMemory] = None,
        tool_executor: Optional[ToolExecutor] = None
    ):
        self._memory = memory or get_memory()
        self._tool_executor = tool_executor or ToolExecutor()
        self._llm_client = None
        self._config = get_config()
    
    async def _get_llm_client(self):
        """Get LLM client lazily"""
        if self._llm_client is None:
            try:
                # Try to use OpenAI directly for function calling
                import openai
                self._llm_client = openai.AsyncOpenAI(
                    api_key=self._config.llm.api_key
                )
            except ImportError:
                raise ToolExecutionError("OpenAI library not available")
        return self._llm_client
    
    async def chat(
        self,
        message: str,
        session_id: Optional[str] = None,
        max_tool_calls: int = 5
    ) -> AgentResponse:
        """
        Process a chat message and return a response.
        
        Args:
            message: User's message
            session_id: Optional session ID for conversation continuity
            max_tool_calls: Maximum number of tool calls per turn
            
        Returns:
            AgentResponse with message and any tool results
        """
        # Get or create session
        session = self._memory.get_or_create_session(session_id)
        
        # Add system prompt if this is a new conversation
        if not session.messages:
            session.add_message("system", SYSTEM_PROMPT)
        
        # Add user message
        session.add_message("user", message)
        
        # Get LLM client
        client = await self._get_llm_client()
        
        # Track tool calls and results
        all_tool_calls = []
        all_tool_results = []
        visualizations = []
        
        # Loop for potential multi-turn tool usage
        for _ in range(max_tool_calls):
            # Get messages for LLM
            messages = session.get_messages_for_llm()
            
            # Call LLM with tools
            try:
                response = await client.chat.completions.create(
                    model=self._config.llm.model,
                    messages=messages,
                    tools=TOOL_DEFINITIONS,
                    tool_choice="auto",
                    temperature=self._config.llm.temperature,
                    max_tokens=self._config.llm.max_tokens
                )
            except Exception as e:
                logger.error(f"LLM call failed: {e}")
                return AgentResponse(
                    message=f"Xin lỗi, đã xảy ra lỗi khi xử lý yêu cầu: {str(e)}",
                    session_id=session.id
                )
            
            choice = response.choices[0]
            assistant_message = choice.message
            
            # Check if there are tool calls
            if assistant_message.tool_calls:
                # Add assistant message with tool calls
                session.add_message(
                    "assistant",
                    assistant_message.content or "",
                    tool_calls=[
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        }
                        for tc in assistant_message.tool_calls
                    ]
                )
                
                # Execute each tool call
                for tool_call in assistant_message.tool_calls:
                    tool_name = tool_call.function.name
                    try:
                        arguments = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError:
                        arguments = {}
                    
                    logger.info(f"Executing tool: {tool_name} with args: {arguments}")
                    
                    # Execute tool
                    try:
                        result = await self._tool_executor.execute(tool_name, arguments)
                    except Exception as e:
                        result = {"error": str(e)}
                    
                    # Track results
                    all_tool_calls.append({
                        "name": tool_name,
                        "arguments": arguments
                    })
                    all_tool_results.append({
                        "tool": tool_name,
                        "result": result
                    })
                    
                    # Check for visualizations
                    if result.get("type") == "chart":
                        visualizations.append(result.get("config"))
                    
                    # Add tool result to conversation
                    session.add_message(
                        "tool",
                        json.dumps(result, ensure_ascii=False, default=str),
                        tool_call_id=tool_call.id,
                        name=tool_name
                    )
                
                # Continue loop to get final response
                continue
            
            # No more tool calls - we have the final response
            final_message = assistant_message.content or "Đã xử lý xong yêu cầu của bạn."
            session.add_message("assistant", final_message)
            
            return AgentResponse(
                message=final_message,
                tool_calls=all_tool_calls if all_tool_calls else None,
                tool_results=all_tool_results if all_tool_results else None,
                visualizations=visualizations if visualizations else None,
                session_id=session.id
            )
        
        # Exceeded max tool calls
        return AgentResponse(
            message="Đã thực hiện quá nhiều công cụ. Vui lòng thử lại với câu hỏi đơn giản hơn.",
            tool_calls=all_tool_calls,
            tool_results=all_tool_results,
            visualizations=visualizations,
            session_id=session.id
        )
    
    def get_session_history(self, session_id: str) -> Optional[Dict]:
        """Get conversation history for a session"""
        session = self._memory.get_session(session_id)
        if session:
            return session.to_dict()
        return None
    
    def list_sessions(self, limit: int = 20) -> List[Dict]:
        """List recent conversation sessions"""
        return self._memory.list_sessions(limit)
    
    def clear_session(self, session_id: str) -> bool:
        """Clear a conversation session"""
        return self._memory.delete_session(session_id)


# Singleton instance
_agent: Optional[AnalyticsAgent] = None


def get_agent() -> AnalyticsAgent:
    """Get or create the global agent instance"""
    global _agent
    if _agent is None:
        _agent = AnalyticsAgent()
    return _agent
