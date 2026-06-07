"""Tests for HTTP MCP client."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from rag_mcp.mcp.clients.http_client import HTTPMCPClient, MCPClientError
from rag_mcp.mcp.models import MCPRequest, MCPResponse


@pytest.mark.asyncio
async def test_http_client_call_tool_success() -> None:
    """Test successful tool call."""
    client = HTTPMCPClient(
        base_url="http://localhost:8000",
        api_key="test_key",
    )

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "jsonrpc": "2.0",
        "result": {"data": "test"},
        "error": None,
        "id": 1,
    }

    with patch("rag_mcp.mcp.clients.http_client.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=mock_response
        )

        response = await client.call_tool("test_tool", {"arg": "value"})

        assert response.result == {"data": "test"}
        assert response.error is None


@pytest.mark.asyncio
async def test_http_client_call_tool_error() -> None:
    """Test tool call with error response."""
    client = HTTPMCPClient(
        base_url="http://localhost:8000",
        api_key="test_key",
    )

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "jsonrpc": "2.0",
        "result": None,
        "error": {"code": -1, "message": "Tool not found"},
        "id": 1,
    }

    with patch("rag_mcp.mcp.clients.http_client.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=mock_response
        )

        with pytest.raises(MCPClientError):
            await client.call_tool("nonexistent_tool", {})


@pytest.mark.asyncio
async def test_http_client_health_check_success() -> None:
    """Test successful health check."""
    client = HTTPMCPClient(
        base_url="http://localhost:8000",
        api_key="test_key",
    )

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "jsonrpc": "2.0",
        "result": {"status": "ok"},
        "error": None,
        "id": 1,
    }

    with patch("rag_mcp.mcp.clients.http_client.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=mock_response
        )

        result = await client.health_check()
        assert result is True


@pytest.mark.asyncio
async def test_http_client_health_check_failure() -> None:
    """Test health check failure."""
    client = HTTPMCPClient(
        base_url="http://localhost:8000",
        api_key="test_key",
    )

    with patch("rag_mcp.mcp.clients.http_client.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            side_effect=httpx.HTTPError("Connection failed")
        )

        result = await client.health_check()
        assert result is False


@pytest.mark.asyncio
async def test_http_client_list_tools() -> None:
    """Test listing tools."""
    client = HTTPMCPClient(
        base_url="http://localhost:8000",
        api_key="test_key",
    )

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "jsonrpc": "2.0",
        "result": {
            "tools": [
                {
                    "name": "get_stock_data",
                    "description": "Get stock data",
                    "input_schema": {},
                }
            ]
        },
        "error": None,
        "id": 1,
    }

    with patch("rag_mcp.mcp.clients.http_client.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=mock_response
        )

        tools = await client.list_tools()

        assert len(tools) == 1
        assert tools[0].name == "get_stock_data"

