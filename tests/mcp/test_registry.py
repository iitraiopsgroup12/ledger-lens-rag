"""Tests for MCP client registry."""

import pytest

from rag_mcp.mcp.registry import MCPClientRegistry, ServerNotFoundError


@pytest.mark.asyncio
async def test_registry_register_and_get(mock_mcp_client: object) -> None:
    """Test registering and retrieving clients."""
    registry = MCPClientRegistry()

    registry.register("ise", mock_mcp_client)
    retrieved = registry.get("ise")

    assert retrieved == mock_mcp_client


@pytest.mark.asyncio
async def test_registry_server_not_found() -> None:
    """Test error when server not found."""
    registry = MCPClientRegistry()

    with pytest.raises(ServerNotFoundError):
        registry.get("nonexistent")


@pytest.mark.asyncio
async def test_registry_list_servers(mock_mcp_client: object) -> None:
    """Test listing registered servers."""
    registry = MCPClientRegistry()

    registry.register("ise", mock_mcp_client)
    registry.register("nse", mock_mcp_client)

    servers = registry.list_servers()
    assert len(servers) == 2
    assert "ise" in servers
    assert "nse" in servers


@pytest.mark.asyncio
async def test_registry_context_manager() -> None:
    """Test registry as async context manager."""
    registry = MCPClientRegistry()

    async with registry as reg:
        assert reg == registry

    # After exiting context, should still be usable
    assert registry.list_servers() == []


@pytest.mark.asyncio
async def test_registry_overwrite_warning(mock_mcp_client: object) -> None:
    """Test warning when overwriting existing client."""
    registry = MCPClientRegistry()

    registry.register("ise", mock_mcp_client)
    registry.register("ise", mock_mcp_client)  # Should log warning

    # Should have only one client
    assert len(registry.list_servers()) == 1

