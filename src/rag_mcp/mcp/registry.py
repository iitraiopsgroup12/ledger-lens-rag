"""MCP client registry for managing multiple MCP servers."""

import logging
from typing import Any

from rag_mcp import RagMCPError
from rag_mcp.mcp.base import MCPClient


class ServerNotFoundError(RagMCPError):
    """Error raised when a requested MCP server is not found."""

    pass


class MCPClientRegistry:
    """Registry for managing MCP clients."""

    def __init__(self) -> None:
        """Initialize the registry."""
        self._clients: dict[str, MCPClient] = {}
        self.logger = logging.getLogger(__name__)

    def register(self, server_id: str, client: MCPClient) -> None:
        """Register an MCP client.

        Args:
            server_id: Unique identifier for the server.
            client: MCP client instance.
        """
        if server_id in self._clients:
            self.logger.warning("Overwriting existing client for server %s", server_id)
        self._clients[server_id] = client
        self.logger.info("Registered MCP client for server %s", server_id)

    def get(self, server_id: str) -> MCPClient:
        """Get an MCP client by server ID.

        Args:
            server_id: Server identifier.

        Returns:
            MCPClient: The registered client.

        Raises:
            ServerNotFoundError: If server not found.
        """
        if server_id not in self._clients:
            self.logger.error("Server %s not found in registry", server_id)
            raise ServerNotFoundError(f"Server '{server_id}' not found in registry")
        return self._clients[server_id]

    def list_servers(self) -> list[str]:
        """List all registered server IDs.

        Returns:
            list[str]: List of server identifiers.
        """
        return list(self._clients.keys())

    async def close_all(self) -> None:
        """Close all registered clients."""
        self.logger.info("Closing all MCP clients")
        for server_id in self._clients:
            self.logger.debug("Closing client for server %s", server_id)
        self._clients.clear()

    async def __aenter__(self) -> "MCPClientRegistry":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close_all()

