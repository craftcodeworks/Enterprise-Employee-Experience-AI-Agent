"""
Base MCP (Model Context Protocol) server implementation.

Provides the foundation for creating MCP servers that expose
tools for LangChain agents to interact with backend services.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class MCPToolResultStatus(Enum):
    """Status of an MCP tool execution."""
    SUCCESS = "success"
    ERROR = "error"
    PARTIAL = "partial"


@dataclass
class MCPToolResult:
    """Result from an MCP tool execution."""
    
    status: MCPToolResultStatus
    data: Any = None
    error: Optional[str] = None
    metadata: dict = field(default_factory=dict)
    
    @property
    def is_success(self) -> bool:
        """Check if the result indicates success."""
        return self.status == MCPToolResultStatus.SUCCESS
    
    def to_dict(self) -> dict:
        """Convert to dictionary representation."""
        return {
            "status": self.status.value,
            "data": self.data,
            "error": self.error,
            "metadata": self.metadata,
        }
    
    @classmethod
    def success(cls, data: Any, **metadata) -> "MCPToolResult":
        """Create a successful result."""
        return cls(
            status=MCPToolResultStatus.SUCCESS,
            data=data,
            metadata=metadata,
        )
    
    @classmethod
    def error(cls, error: str, **metadata) -> "MCPToolResult":
        """Create an error result."""
        return cls(
            status=MCPToolResultStatus.ERROR,
            error=error,
            metadata=metadata,
        )


@dataclass
class MCPToolParameter:
    """Definition of a tool parameter."""
    
    name: str
    description: str
    type: str  # "string", "integer", "boolean", "number", "array", "object"
    required: bool = True
    default: Any = None
    enum: Optional[list] = None
    
    def to_json_schema(self) -> dict:
        """Convert to JSON Schema representation."""
        schema = {
            "type": self.type,
            "description": self.description,
        }
        if self.enum:
            schema["enum"] = self.enum
        if self.default is not None:
            schema["default"] = self.default
        return schema


@dataclass
class MCPTool:
    """Definition of an MCP tool."""
    
    name: str
    description: str
    parameters: list[MCPToolParameter]
    handler: Callable[..., MCPToolResult]
    
    def to_openai_function(self) -> dict:
        """
        Convert to OpenAI function calling format.
        
        This format is compatible with LangChain's tool system.
        """
        properties = {}
        required = []
        
        for param in self.parameters:
            properties[param.name] = param.to_json_schema()
            if param.required:
                required.append(param.name)
        
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        }
    
    async def execute(self, **kwargs) -> MCPToolResult:
        """
        Execute the tool with given parameters.
        
        Args:
            **kwargs: Tool parameters
            
        Returns:
            MCPToolResult with execution outcome
        """
        try:
            logger.debug(f"Executing MCP tool: {self.name}")
            result = await self.handler(**kwargs)
            return result
        except Exception as e:
            logger.error(f"MCP tool {self.name} failed: {e}")
            return MCPToolResult.error(str(e))


class MCPServer(ABC):
    """
    Base class for MCP (Model Context Protocol) servers.
    
    MCP servers provide a standardized interface for exposing
    backend services as tools that LangChain agents can use.
    
    Subclasses should implement the _register_tools method
    to define available tools.
    """
    
    def __init__(self, name: str, description: str):
        """
        Initialize the MCP server.
        
        Args:
            name: Server name
            description: Server description
        """
        self.name = name
        self.description = description
        self.tools: dict[str, MCPTool] = {}
        self._register_tools()
    
    @abstractmethod
    def _register_tools(self) -> None:
        """
        Register tools provided by this server.
        
        Subclasses must implement this method to register their tools
        using the register_tool method.
        """
        pass
    
    def register_tool(
        self,
        name: str,
        description: str,
        parameters: list[MCPToolParameter],
        handler: Callable[..., MCPToolResult],
    ) -> None:
        """
        Register a tool with the server.
        
        Args:
            name: Tool name (should be unique within the server)
            description: Human-readable tool description
            parameters: List of parameter definitions
            handler: Async function to handle tool execution
        """
        tool = MCPTool(
            name=f"{self.name}.{name}",
            description=description,
            parameters=parameters,
            handler=handler,
        )
        self.tools[tool.name] = tool
        logger.debug(f"Registered MCP tool: {tool.name}")
    
    def get_tool(self, name: str) -> Optional[MCPTool]:
        """
        Get a tool by name.
        
        Args:
            name: Full tool name (server.tool_name)
            
        Returns:
            MCPTool if found, None otherwise
        """
        return self.tools.get(name)
    
    def list_tools(self) -> list[MCPTool]:
        """Get all registered tools."""
        return list(self.tools.values())
    
    def get_tools_schema(self) -> list[dict]:
        """
        Get OpenAI function calling schema for all tools.
        
        Returns:
            List of tool schemas in OpenAI format
        """
        return [tool.to_openai_function() for tool in self.tools.values()]
    
    async def execute_tool(self, name: str, **kwargs) -> MCPToolResult:
        """
        Execute a tool by name.
        
        Args:
            name: Tool name
            **kwargs: Tool parameters
            
        Returns:
            MCPToolResult with execution outcome
        """
        tool = self.get_tool(name)
        if not tool:
            return MCPToolResult.error(f"Tool not found: {name}")
        
        return await tool.execute(**kwargs)
    
    def to_dict(self) -> dict:
        """Get server information as dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "tools": [t.to_openai_function() for t in self.tools.values()],
        }
