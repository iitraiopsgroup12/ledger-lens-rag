"""HTTP JSON-RPC implementation of MCPClient."""

import json
import logging
from typing import Any

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
)

from rag_mcp import RagMCPError
from rag_mcp.mcp.base import MCPClient
from rag_mcp.mcp.models import MCPRequest, MCPResponse, MCPTool


class MCPClientError(RagMCPError):
    """Error raised by MCP client."""

    pass


class HTTPMCPClient(MCPClient):
    """HTTP-based JSON-RPC 2.0 MCP client."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: float = 30.0,
    ):
        """Initialize HTTP MCP client.

        Args:
            base_url: Base URL of MCP server.
            api_key: API key for authentication.
            timeout: Request timeout in seconds.
        """
        self.base_url = base_url
        self.api_key = api_key
        self.timeout = timeout
        self.logger = logging.getLogger(__name__)
        self._request_id = 0

    def _get_next_id(self) -> int:
        """Get next request ID."""
        self._request_id += 1
        return self._request_id

    async def _send_request(self, request: MCPRequest) -> MCPResponse:
        """Send a JSON-RPC request to the server.

        Args:
            request: JSON-RPC request.

        Returns:
            MCPResponse: Parsed response.

        Raises:
            MCPClientError: If request fails or server returns error.
        """
        headers = {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
        ) as client:
            try:
                response = await client.post(
                    "/rpc",
                    json=request.model_dump(exclude_none=True),
                    headers=headers,
                )
                response.raise_for_status()
            except httpx.HTTPError as e:
                self.logger.error(
                    "HTTP error calling MCP server: %s",
                    e,
                )
                raise MCPClientError(f"HTTP error: {e}") from e

        try:
            data = response.json()
            mcp_response = MCPResponse(**data)
        except (json.JSONDecodeError, ValueError) as e:
            self.logger.error("Invalid JSON response from MCP server: %s", e)
            raise MCPClientError(f"Invalid JSON response: {e}") from e

        if mcp_response.error:
            error_msg = mcp_response.error.get(
                "message",
                "Unknown error",
            )
            self.logger.error("MCP server error: %s", error_msg)
            raise MCPClientError(f"MCP error: {error_msg}")

        return mcp_response

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def call_tool(self, tool_name: str, arguments: dict) -> MCPResponse:
        """Call a tool on the MCP server.

        Args:
            tool_name: Name of the tool to call.
            arguments: Tool arguments.

        Returns:
            MCPResponse: Response from the server.

        Raises:
            MCPClientError: If the call fails after retries.
        """
        request_id = self._get_next_id()
        request = MCPRequest(
            method=tool_name,
            params=arguments,
            id=request_id,
        )

        self.logger.debug(
            "Calling MCP tool %s with arguments %s",
            tool_name,
            arguments,
        )

        return await self._send_request(request)

    async def list_tools(self) -> list[MCPTool]:
        """List all available tools on the MCP server.

        Returns:
            list[MCPTool]: List of available tools.

        Raises:
            MCPClientError: If the call fails.
        """
        request_id = self._get_next_id()
        request = MCPRequest(
            method="tools/list",
            params={},
            id=request_id,
        )

        self.logger.debug("Listing available MCP tools")

        response = await self._send_request(request)

        tools = []
        if response.result and "tools" in response.result:
            for tool_data in response.result["tools"]:
                tools.append(MCPTool(**tool_data))

        self.logger.debug("Found %d available tools", len(tools))
        return tools

    async def health_check(self) -> bool:
        """Check if the MCP server is healthy.

        Returns:
            bool: True if healthy, False otherwise.
        """
        try:
            request_id = self._get_next_id()
            request = MCPRequest(
                method="health",
                params={},
                id=request_id,
            )

            self.logger.debug("Checking MCP server health")

            response = await self._send_request(request)
            is_healthy = response.result is not None and response.error is None

            self.logger.debug("Health check result: %s", is_healthy)
            return is_healthy
        except MCPClientError as e:
            self.logger.warning("Health check failed: %s", e)
            return False

