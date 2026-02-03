"""
Conversation Memory
Manages conversation history for the AI agent
"""
import uuid
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict


@dataclass
class Message:
    """A single message in conversation"""
    role: str  # user, assistant, system
    content: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


class ConversationMemory:
    """
    In-memory conversation storage.
    
    Features:
    - Session-based conversations
    - History retrieval
    - Memory limits
    
    For production, this should be backed by Redis or database.
    """
    
    def __init__(self, max_messages_per_session: int = 100):
        self._sessions: Dict[str, List[Message]] = defaultdict(list)
        self._max_messages = max_messages_per_session
    
    def new_session(self) -> str:
        """Create a new conversation session"""
        session_id = str(uuid.uuid4())
        self._sessions[session_id] = []
        return session_id
    
    def add_message(
        self, 
        session_id: str, 
        role: str, 
        content: str,
        metadata: Dict[str, Any] = None
    ) -> None:
        """Add a message to the session"""
        message = Message(
            role=role,
            content=content,
            metadata=metadata or {},
        )
        
        self._sessions[session_id].append(message)
        
        # Trim if exceeds limit
        if len(self._sessions[session_id]) > self._max_messages:
            self._sessions[session_id] = self._sessions[session_id][-self._max_messages:]
    
    def get_history(self, session_id: str) -> List[Dict[str, str]]:
        """Get conversation history for session"""
        messages = self._sessions.get(session_id, [])
        return [{"role": m.role, "content": m.content} for m in messages]
    
    def get_last_messages(self, session_id: str, n: int = 5) -> List[Dict[str, str]]:
        """Get last n messages from session"""
        messages = self._sessions.get(session_id, [])
        return [{"role": m.role, "content": m.content} for m in messages[-n:]]
    
    def clear_session(self, session_id: str) -> None:
        """Clear a specific session"""
        if session_id in self._sessions:
            del self._sessions[session_id]
    
    def clear_all(self) -> None:
        """Clear all sessions"""
        self._sessions.clear()
    
    def get_session_count(self) -> int:
        """Get number of active sessions"""
        return len(self._sessions)
    
    def session_exists(self, session_id: str) -> bool:
        """Check if session exists"""
        return session_id in self._sessions
    
    def get_session_info(self, session_id: str) -> Dict[str, Any]:
        """Get session metadata"""
        if session_id not in self._sessions:
            return {}
        
        messages = self._sessions[session_id]
        return {
            "session_id": session_id,
            "message_count": len(messages),
            "first_message": messages[0].timestamp.isoformat() if messages else None,
            "last_message": messages[-1].timestamp.isoformat() if messages else None,
        }
