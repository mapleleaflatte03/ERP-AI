"""
Registry for Analytics Tools and Connectors
"""
from typing import Dict, Type, Callable, Any, Optional
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class ToolDefinition:
    """Definition of an AI tool"""
    name: str
    description: str
    parameters: Dict[str, Any]
    handler: Callable
    requires_confirmation: bool = False
    category: str = "general"
    
    def to_openai_tool(self) -> dict:
        """Convert to OpenAI function calling format"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters
            }
        }


class ToolRegistry:
    """Registry for managing AI tools"""
    _instance: Optional["ToolRegistry"] = None
    _tools: Dict[str, ToolDefinition] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._tools = {}
        return cls._instance
    
    def register(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        handler: Callable,
        requires_confirmation: bool = False,
        category: str = "general"
    ) -> None:
        """Register a new tool"""
        self._tools[name] = ToolDefinition(
            name=name,
            description=description,
            parameters=parameters,
            handler=handler,
            requires_confirmation=requires_confirmation,
            category=category
        )
        logger.info(f"Registered tool: {name}")
    
    def get(self, name: str) -> Optional[ToolDefinition]:
        """Get a tool by name"""
        return self._tools.get(name)
    
    def list_tools(self, category: Optional[str] = None) -> list[ToolDefinition]:
        """List all registered tools"""
        tools = list(self._tools.values())
        if category:
            tools = [t for t in tools if t.category == category]
        return tools
    
    def get_openai_tools(self, category: Optional[str] = None) -> list[dict]:
        """Get tools in OpenAI format"""
        return [t.to_openai_tool() for t in self.list_tools(category)]
    
    def unregister(self, name: str) -> bool:
        """Unregister a tool"""
        if name in self._tools:
            del self._tools[name]
            return True
        return False
    
    def clear(self) -> None:
        """Clear all tools (for testing)"""
        self._tools.clear()


def tool(
    name: str,
    description: str,
    parameters: Dict[str, Any],
    requires_confirmation: bool = False,
    category: str = "general"
):
    """Decorator to register a function as a tool"""
    def decorator(func: Callable):
        registry = ToolRegistry()
        registry.register(
            name=name,
            description=description,
            parameters=parameters,
            handler=func,
            requires_confirmation=requires_confirmation,
            category=category
        )
        return func
    return decorator


# Connector registry for data sources
class ConnectorRegistry:
    """Registry for data source connectors"""
    _instance: Optional["ConnectorRegistry"] = None
    _connectors: Dict[str, Any] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._connectors = {}
        return cls._instance
    
    def register(self, name: str, connector_class: Type) -> None:
        """Register a connector class"""
        self._connectors[name] = connector_class
        logger.info(f"Registered connector: {name}")
    
    def get(self, name: str) -> Optional[Type]:
        """Get a connector class by name"""
        return self._connectors.get(name)
    
    def list_connectors(self) -> list[str]:
        """List all registered connector names"""
        return list(self._connectors.keys())
    
    def create(self, name: str, **kwargs) -> Any:
        """Create a connector instance"""
        connector_class = self.get(name)
        if connector_class is None:
            raise ValueError(f"Unknown connector: {name}")
        return connector_class(**kwargs)


# Global instances
_tool_registry: Optional[ToolRegistry] = None
_connector_registry: Optional[ConnectorRegistry] = None


def get_tool_registry() -> ToolRegistry:
    global _tool_registry
    if _tool_registry is None:
        _tool_registry = ToolRegistry()
    return _tool_registry


def get_connector_registry() -> ConnectorRegistry:
    global _connector_registry
    if _connector_registry is None:
        _connector_registry = ConnectorRegistry()
    return _connector_registry
