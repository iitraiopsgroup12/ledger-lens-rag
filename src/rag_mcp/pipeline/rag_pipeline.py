"""RAG pipeline orchestrating retrieval, MCP calls, and LLM generation."""

import logging
from typing import Any

from pydantic import BaseModel, Field

from rag_mcp import RagMCPError
from rag_mcp.config.settings import Settings
from rag_mcp.embeddings.base import Embedder
from rag_mcp.llm.base import LLMBackend
from rag_mcp.mcp.registry import MCPClientRegistry
from rag_mcp.pipeline.context_builder import ContextBuilder
from rag_mcp.retrieval.vector_store import VectorStore


class PipelineResult(BaseModel):
    """Result from RAG pipeline query."""

    answer: str = Field(description="LLM-generated answer")
    sources: list[str] = Field(default_factory=list, description="Retrieved document sources")
    mcp_data: dict | None = Field(default=None, description="Raw MCP response data")
    tool_used: str | None = Field(default=None, description="MCP tool that was called")
    confidence: float = Field(default=0.0, description="Confidence score (0-1)")


class PipelineError(RagMCPError):
    """Error raised during pipeline execution."""

    pass


class RAGPipeline:
    """Orchestrates the RAG (Retrieval-Augmented Generation) pipeline."""

    def __init__(
        self,
        mcp_registry: MCPClientRegistry,
        embedder: Embedder,
        vector_store: VectorStore,
        llm: LLMBackend,
        context_builder: ContextBuilder,
        settings: Settings,
    ):
        """Initialize RAG pipeline.

        Args:
            mcp_registry: MCP client registry.
            embedder: Text embedding provider.
            vector_store: Vector database for retrieval.
            llm: LLM backend for generation.
            context_builder: Context builder for prompts.
            settings: Application settings.
        """
        self.mcp_registry = mcp_registry
        self.embedder = embedder
        self.vector_store = vector_store
        self.llm = llm
        self.context_builder = context_builder
        self.settings = settings
        self.logger = logging.getLogger(__name__)

    async def query(
        self,
        user_query: str,
        server_id: str = "ise",
        tool_hint: str | None = None,
    ) -> PipelineResult:
        """Execute a query through the RAG pipeline.

        Args:
            user_query: User's natural language query.
            server_id: MCP server ID to use.
            tool_hint: Optional hint for which tool to call.

        Returns:
            PipelineResult: Generated answer with sources and metadata.

        Raises:
            PipelineError: If pipeline execution fails.
        """
        try:
            self.logger.info("Starting RAG query: %s", user_query)

            # Step 1: Embed the query
            self.logger.debug("Embedding user query")
            query_embeddings = await self.embedder.embed([user_query])
            if not query_embeddings:
                raise PipelineError("Failed to embed query")
            query_vector = query_embeddings[0]

            # Step 2: Retrieve relevant documents
            self.logger.debug("Retrieving documents from vector store")
            documents = await self.vector_store.search(
                query_vector=query_vector,
                top_k=self.settings.top_k,
            )

            # Calculate average confidence from retrieved documents
            confidence = (
                sum(doc.score for doc in documents) / len(documents)
                if documents
                else 0.0
            )

            mcp_data: dict | None = None
            tool_used: str | None = None
            sources: list[str] = []

            # Step 3: Call MCP tool if documents found and tool hint provided
            if documents and tool_hint:
                self.logger.debug("Calling MCP tool: %s", tool_hint)
                try:
                    client = self.mcp_registry.get(server_id)
                    mcp_response = await client.call_tool(tool_hint, {})
                    mcp_data = mcp_response.result
                    tool_used = tool_hint
                except Exception as e:
                    self.logger.warning("MCP call failed: %s", e)
                    # Continue without MCP data

            # Extract sources
            sources = [
                doc.metadata.get("source", f"document_{doc.id}") for doc in documents
            ]

            # Step 4: Build context from documents and MCP data
            context = self.context_builder.build_context(documents, mcp_data)

            # Step 5: Generate answer using LLM
            self.logger.debug("Generating answer with LLM")
            system_prompt = (
                "You are a knowledgeable financial advisor specializing in Indian stock "
                "markets (NSE/BSE). Provide clear, accurate answers based on the provided "
                "context. If you don't have enough information, say so explicitly."
            )

            messages = [
                {
                    "role": "user",
                    "content": f"Context:\n{context}\n\nQuestion: {user_query}",
                }
            ]

            answer = await self.llm.complete(system_prompt, messages)

            self.logger.info("Query completed successfully")

            return PipelineResult(
                answer=answer,
                sources=sources,
                mcp_data=mcp_data,
                tool_used=tool_used,
                confidence=float(confidence),
            )

        except PipelineError:
            raise
        except Exception as e:
            self.logger.error("Pipeline error: %s", e)
            raise PipelineError(f"Pipeline execution failed: {e}") from e

