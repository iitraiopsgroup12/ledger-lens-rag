"""Tests for RAG pipeline."""

from unittest.mock import AsyncMock

import pytest

from rag_mcp.pipeline.context_builder import ContextBuilder
from rag_mcp.pipeline.rag_pipeline import RAGPipeline, PipelineResult
from rag_mcp.mcp.registry import MCPClientRegistry
from rag_mcp.retrieval.vector_store import ScoredDocument


@pytest.mark.asyncio
async def test_rag_pipeline_query_success(
    mock_mcp_client: object,
    mock_embedder: AsyncMock,
    mock_vector_store: AsyncMock,
    mock_llm: AsyncMock,
    mock_settings: object,
) -> None:
    """Test successful pipeline query."""
    registry = MCPClientRegistry()
    registry.register("ise", mock_mcp_client)

    context_builder = ContextBuilder()
    pipeline = RAGPipeline(
        mcp_registry=registry,
        embedder=mock_embedder,
        vector_store=mock_vector_store,
        llm=mock_llm,
        context_builder=context_builder,
        settings=mock_settings,
    )

    # Mock vector store search results
    mock_vector_store.search = AsyncMock(
        return_value=[
            ScoredDocument(
                id="1",
                content="Test content",
                metadata={"source": "test_source"},
                score=0.8,
            )
        ]
    )

    result = await pipeline.query("What is the stock price?", server_id="ise")

    assert isinstance(result, PipelineResult)
    assert result.answer == "Test response from LLM"
    assert len(result.sources) > 0


@pytest.mark.asyncio
async def test_rag_pipeline_query_no_documents(
    mock_embedder: AsyncMock,
    mock_vector_store: AsyncMock,
    mock_llm: AsyncMock,
    mock_settings: object,
) -> None:
    """Test pipeline query with no retrieved documents."""
    registry = MCPClientRegistry()

    context_builder = ContextBuilder()
    pipeline = RAGPipeline(
        mcp_registry=registry,
        embedder=mock_embedder,
        vector_store=mock_vector_store,
        llm=mock_llm,
        context_builder=context_builder,
        settings=mock_settings,
    )

    # Mock empty search results
    mock_vector_store.search = AsyncMock(return_value=[])

    result = await pipeline.query("What is the stock price?")

    assert isinstance(result, PipelineResult)
    assert len(result.sources) == 0
    assert result.confidence == 0.0


@pytest.mark.asyncio
async def test_rag_pipeline_embedding_failure(
    mock_embedder: AsyncMock,
    mock_settings: object,
) -> None:
    """Test pipeline handling embedding failure."""
    registry = MCPClientRegistry()

    context_builder = ContextBuilder()
    pipeline = RAGPipeline(
        mcp_registry=registry,
        embedder=mock_embedder,
        vector_store=AsyncMock(),
        llm=AsyncMock(),
        context_builder=context_builder,
        settings=mock_settings,
    )

    # Mock embedding failure
    mock_embedder.embed = AsyncMock(return_value=[])

    from rag_mcp.pipeline.rag_pipeline import PipelineError

    with pytest.raises(PipelineError):
        await pipeline.query("What is the stock price?")


@pytest.mark.asyncio
async def test_rag_pipeline_with_tool_hint(
    mock_mcp_client: object,
    mock_embedder: AsyncMock,
    mock_vector_store: AsyncMock,
    mock_llm: AsyncMock,
    mock_settings: object,
) -> None:
    """Test pipeline with tool hint."""
    registry = MCPClientRegistry()
    registry.register("ise", mock_mcp_client)

    context_builder = ContextBuilder()
    pipeline = RAGPipeline(
        mcp_registry=registry,
        embedder=mock_embedder,
        vector_store=mock_vector_store,
        llm=mock_llm,
        context_builder=context_builder,
        settings=mock_settings,
    )

    # Mock vector store search results
    mock_vector_store.search = AsyncMock(
        return_value=[
            ScoredDocument(
                id="1",
                content="Stock data",
                metadata={"source": "test"},
                score=0.9,
            )
        ]
    )

    result = await pipeline.query(
        "Get me trending stocks",
        server_id="ise",
        tool_hint="get_trending_stocks",
    )

    assert isinstance(result, PipelineResult)
    assert result.tool_used == "get_trending_stocks"
    assert result.mcp_data is not None

