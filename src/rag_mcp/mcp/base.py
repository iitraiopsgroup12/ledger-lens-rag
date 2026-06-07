"""Abstract base class for MCP clients."""

from abc import ABC, abstractmethod

from rag_mcp.mcp.models import MCPResponse, MCPTool


class MCPClient(ABC):
    """Abstract base class for MCP (Model Context Protocol) clients."""

    @abstractmethod
    async def call_tool(self, tool_name: str, arguments: dict) -> MCPResponse:
        """Call a tool on the MCP server.

        Args:
            tool_name: Name of the tool to call.
            arguments: Tool arguments.

        Returns:
            MCPResponse: Response from the server.

        Raises:
            MCPClientError: If the call fails.
        """
        pass

    @abstractmethod
    async def list_tools(self) -> list[MCPTool]:
        """List all available tools on the MCP server.

        Returns:
            list[MCPTool]: List of available tools.

        Raises:
            MCPClientError: If the call fails.
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the MCP server is healthy.

        Returns:
            bool: True if healthy, False otherwise.
        """
        pass

