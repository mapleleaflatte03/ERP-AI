"""
Conversation Memory for Analytics Assistant
"""
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import json
import uuid

logger = logging.getLogger(__name__)


@dataclass
class Message:
    """A single message in conversation"""
    role: str  # "user", "assistant", "system", "tool"
    content: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    tool_calls: Optional[List[Dict]] = None
    tool_call_id: Optional[str] = None
    name: Optional[str] = None  # For tool messages
    
    def to_openai_format(self) -> Dict:
        """Convert to OpenAI message format"""
        msg = {"role": self.role, "content": self.content}
        if self.tool_calls:
            msg["tool_calls"] = self.tool_calls
        if self.tool_call_id:
            msg["tool_call_id"] = self.tool_call_id
        if self.name:
            msg["name"] = self.name
        return msg


@dataclass
class ConversationSession:
    """A conversation session"""
    id: str
    messages: List[Message] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict = field(default_factory=dict)
    
    def add_message(self, role: str, content: str, **kwargs) -> Message:
        """Add a message to the conversation"""
        msg = Message(role=role, content=content, **kwargs)
        self.messages.append(msg)
        self.updated_at = datetime.now().isoformat()
        return msg
    
    def get_messages_for_llm(self, max_messages: int = 20) -> List[Dict]:
        """Get messages in OpenAI format for LLM"""
        # Get last N messages, but always include system message if present
        messages = []
        
        # Find system message
        system_msg = None
        other_msgs = []
        for msg in self.messages:
            if msg.role == "system":
                system_msg = msg
            else:
                other_msgs.append(msg)
        
        # Build result
        if system_msg:
            messages.append(system_msg.to_openai_format())
        
        # Add recent messages
        recent = other_msgs[-max_messages:] if len(other_msgs) > max_messages else other_msgs
        messages.extend([m.to_openai_format() for m in recent])
        
        return messages
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "messages": [
                {
                    "role": m.role,
                    "content": m.content,
                    "timestamp": m.timestamp
                }
                for m in self.messages if m.role != "system"
            ],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata
        }


class ConversationMemory:
    """
    In-memory conversation storage.
    For production, replace with Redis or database storage.
    """
    
    def __init__(self, max_sessions: int = 100):
        self._sessions: Dict[str, ConversationSession] = {}
        self._max_sessions = max_sessions
    
    def create_session(self, session_id: Optional[str] = None) -> ConversationSession:
        """Create a new conversation session"""
        if session_id is None:
            session_id = str(uuid.uuid4())
        
        session = ConversationSession(id=session_id)
        self._sessions[session_id] = session
        
        # Cleanup old sessions if needed
        self._cleanup_if_needed()
        
        return session
    
    def get_session(self, session_id: str) -> Optional[ConversationSession]:
        """Get an existing session"""
        return self._sessions.get(session_id)
    
    def get_or_create_session(self, session_id: Optional[str] = None) -> ConversationSession:
        """Get existing session or create new one"""
        if session_id and session_id in self._sessions:
            return self._sessions[session_id]
        return self.create_session(session_id)
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a session"""
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False
    
    def list_sessions(self, limit: int = 20) -> List[Dict]:
        """List recent sessions"""
        sessions = sorted(
            self._sessions.values(),
            key=lambda s: s.updated_at,
            reverse=True
        )[:limit]
        
        return [
            {
                "id": s.id,
                "message_count": len([m for m in s.messages if m.role != "system"]),
                "created_at": s.created_at,
                "updated_at": s.updated_at,
                "preview": self._get_preview(s)
            }
            for s in sessions
        ]
    
    def _get_preview(self, session: ConversationSession) -> str:
        """Get a preview of the conversation"""
        user_msgs = [m for m in session.messages if m.role == "user"]
        if user_msgs:
            return user_msgs[-1].content[:100]
        return ""
    
    def _cleanup_if_needed(self) -> None:
        """Remove oldest sessions if exceeding max"""
        if len(self._sessions) <= self._max_sessions:
            return
        
        # Sort by updated_at and remove oldest
        sorted_sessions = sorted(
            self._sessions.items(),
            key=lambda x: x[1].updated_at
        )
        
        to_remove = len(self._sessions) - self._max_sessions
        for session_id, _ in sorted_sessions[:to_remove]:
            del self._sessions[session_id]


# Global memory instance
_memory: Optional[ConversationMemory] = None


def get_memory() -> ConversationMemory:
    """Get or create the global memory instance"""
    global _memory
    if _memory is None:
        _memory = ConversationMemory()
    return _memory
