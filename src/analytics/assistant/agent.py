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
        Process a chat message and return a response.
        Uses existing LLM client instead of OpenAI directly.
        
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
        llm = await self._get_llm_client()
        
        # Build conversation context
        messages = session.get_messages_for_llm()
        
        # Simple approach: use generate with tool descriptions in prompt
        tool_descriptions = self._build_tool_descriptions()
        
        prompt = f"""{SYSTEM_PROMPT}

AVAILABLE TOOLS:
{tool_descriptions}

CONVERSATION:
"""
        for msg in messages[-10:]:  # Last 10 messages for context
            role = msg.get("role", "user")
            content = msg.get("content", "")
            prompt += f"\n{role.upper()}: {content}"
        
        prompt += f"\n\nUSER: {message}\n\nASSISTANT:"
        
        try:
            response = await llm.generate(prompt, max_tokens=2000)
            # Handle LLMResponse object
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # Add assistant response to session
            session.add_message("assistant", response_text)
            
            return AgentResponse(
                message=response_text,
                tool_calls=None,
                tool_results=None,
                visualizations=None,
                session_id=session.id
            )
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return AgentResponse(
                message=f"Xin lỗi, đã xảy ra lỗi khi xử lý yêu cầu: {str(e)}",
                session_id=session.id
            )
    
    def _build_tool_descriptions(self) -> str:
        """Build tool descriptions for prompt"""
        descriptions = []
        for tool in TOOL_DEFINITIONS:
            func = tool.get("function", {})
            name = func.get("name", "")
            desc = func.get("description", "")
            descriptions.append(f"- {name}: {desc}")
        return "\n".join(descriptions)
    
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
