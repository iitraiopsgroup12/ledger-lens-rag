"""Pytest configuration and shared fixtures."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from rag_mcp.config import Settings
from rag_mcp.embeddings.base import Embedder
from rag_mcp.llm.base import LLMBackend
from rag_mcp.mcp.base import MCPClient
from rag_mcp.retrieval.vector_store import VectorStore


@pytest.fixture
def mock_settings() -> Settings:
    """Create mock settings for tests.

    Returns:
        Settings: Mock settings object.
    """
    return Settings(
        ise_mcp_base_url="http://localhost:8000",
        ise_api_key="test_key",
        anthropic_api_key="test_anthropic_key",
        openai_api_key="test_openai_key",
        log_level="DEBUG",
    )


@pytest.fixture
def mock_mcp_client() -> AsyncMock:
    """Create mock MCP client.

    Returns:
        AsyncMock: Mock MCP client.
    """
    client = AsyncMock(spec=MCPClient)
    client.call_tool = AsyncMock(
        return_value=MagicMock(
            result={"data": "test_data"},
            error=None,
        )
    )
    client.list_tools = AsyncMock(return_value=[])
    client.health_check = AsyncMock(return_value=True)
    return client


@pytest.fixture
def mock_embedder() -> AsyncMock:
    """Create mock embedder.

    Returns:
        AsyncMock: Mock embedder.
    """
    embedder = AsyncMock(spec=Embedder)
    embedder.embed = AsyncMock(
        return_value=[[0.1, 0.2, 0.3, 0.4, 0.5]]
    )
    return embedder


@pytest.fixture
def mock_vector_store() -> AsyncMock:
    """Create mock vector store.

    Returns:
        AsyncMock: Mock vector store.
    """
    store = AsyncMock(spec=VectorStore)
    store.add = AsyncMock()
    store.search = AsyncMock(return_value=[])
    return store


@pytest.fixture
def mock_llm() -> AsyncMock:
    """Create mock LLM backend.

    Returns:
        AsyncMock: Mock LLM backend.
    """
    llm = AsyncMock(spec=LLMBackend)
    llm.complete = AsyncMock(return_value="Test response from LLM")
    return llm

