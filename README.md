# RAG MCP Pipeline

A production-ready **Retrieval-Augmented Generation (RAG)** pipeline in Python that integrates with **MCP (Model Context Protocol)** servers for enhanced context retrieval. Currently supports the **Live-NSE-BSE-MCP** server for Indian stock market data, with extensibility for additional MCP servers.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                      User Query                                 │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
        ┌────────────────────────────────┐
        │   1. Embed Query               │
        │   (OpenAI Embeddings)          │
        └──────────────┬─────────────────┘
                       │
                       ▼
        ┌────────────────────────────────┐
        │   2. Retrieve Documents        │
        │   (Vector Store - In-Memory)   │
        │   Cosine Similarity Search     │
        └──────────────┬─────────────────┘
                       │
                       ▼
        ┌────────────────────────────────┐
        │   3. Call MCP Tool (Optional)  │
        │   (ISE Stock Market Data)      │
        └──────────────┬─────────────────┘
                       │
                       ▼
        ┌────────────────────────────────┐
        │   4. Build Context             │
        │   (Documents + MCP Data)       │
        └──────────────┬─────────────────┘
                       │
                       ▼
        ┌────────────────────────────────┐
        │   5. Generate Answer           │
        │   (Anthropic Claude LLM)       │
        └──────────────┬─────────────────┘
                       │
                       ▼
        ┌────────────────────────────────┐
        │   PipelineResult               │
        │   - Answer                     │
        │   - Sources                    │
        │   - MCP Data                   │
        │   - Confidence                 │
        └────────────────────────────────┘
```

## Features

- **🔌 MCP Integration**: Connect to multiple MCP servers (starting with ISE/NSE-BSE)
- **🧠 Vector Search**: In-memory vector store with cosine similarity
- **🤖 LLM Generation**: Anthropic Claude integration for intelligent responses
- **📝 OpenAI Embeddings**: High-quality text embeddings for semantic search
- **🏗️ SOLID Architecture**: Clean, extensible codebase following best practices
- **📊 Structured Logging**: JSON-formatted logs for production monitoring
- **✅ Comprehensive Tests**: pytest with 80%+ coverage
- **⚡ Async I/O**: Fully asynchronous for high concurrency
- **🔐 Configuration Management**: Environment-based secrets via Pydantic

## Prerequisites

- **Python 3.14+** (pre-release, install via `uv python install 3.14`)
- **uv** package manager (modern, fast replacement for pip)
- API keys for:
  - OpenAI (embeddings)
  - Anthropic (LLM)
  - ISE MCP Server (stock market data)

## Installation

### 1. Clone the repository

```bash
git clone <repository-url>
cd ledger-lens-rag
```

### 2. Install Python 3.14 (if not already installed)

```bash
uv python install 3.14
```

### 3. Sync dependencies

```bash
uv sync
```

### 4. Set up environment variables

```bash
cp .env.example .env
# Edit .env with your API keys
```

Edit `.env` and add your credentials:

```dotenv
# MCP Server
ISE_MCP_BASE_URL=http://localhost:8000
ISE_API_KEY=your_api_key

# LLM
ANTHROPIC_API_KEY=sk-ant-...
LLM_MODEL=claude-sonnet-4-20250514
LLM_MAX_TOKENS=2048

# Embeddings
OPENAI_API_KEY=sk-...
EMBEDDING_MODEL=text-embedding-3-small

# Retrieval
TOP_K=5
SIMILARITY_THRESHOLD=0.7

# App
LOG_LEVEL=INFO
```

## Usage

### Basic Example

```python
import asyncio
from rag_mcp.config.settings import get_settings
from rag_mcp.mcp.clients import ISEMCPClient
from rag_mcp.mcp.registry import MCPClientRegistry
from rag_mcp.embeddings import OpenAIEmbedder
from rag_mcp.retrieval import InMemoryVectorStore, Document
from rag_mcp.llm import AnthropicLLM
from rag_mcp.pipeline import RAGPipeline, ContextBuilder
from rag_mcp.utils import configure_logging


async def main():
    # Configure logging
    configure_logging("INFO")

    # Load settings
    settings = get_settings()

    # Initialize components
    embedder = OpenAIEmbedder(
        api_key=settings.openai_api_key,
        model=settings.embedding_model,
    )

    vector_store = InMemoryVectorStore(
        similarity_threshold=settings.similarity_threshold,
    )

    llm = AnthropicLLM(
        api_key=settings.anthropic_api_key,
        model=settings.llm_model,
        max_tokens=settings.llm_max_tokens,
    )

    # Register MCP clients
    registry = MCPClientRegistry()
    ise_client = ISEMCPClient(
        base_url=settings.ise_mcp_base_url,
        api_key=settings.ise_api_key,
    )
    registry.register("ise", ise_client)

    # Initialize pipeline
    context_builder = ContextBuilder()
    pipeline = RAGPipeline(
        mcp_registry=registry,
        embedder=embedder,
        vector_store=vector_store,
        llm=llm,
        context_builder=context_builder,
        settings=settings,
    )

    # Add sample documents to vector store
    documents = [
        Document(
            id="1",
            content="TCS is a major IT services company in India",
            metadata={
                "embedding": await embedder.embed(["TCS is a major IT services company in India"])[0],
                "source": "knowledge_base",
            },
        ),
    ]
    await vector_store.add(documents)

    # Query the pipeline
    result = await pipeline.query(
        "What is TCS?",
        server_id="ise",
        tool_hint="get_stock_data",
    )

    print(f"Answer: {result.answer}")
    print(f"Sources: {result.sources}")
    print(f"Confidence: {result.confidence:.2f}")


if __name__ == "__main__":
    asyncio.run(main())
```

## Adding a New MCP Server

To extend the pipeline with a new MCP server, follow these 3 steps:

### Step 1: Create a Client Implementation

```python
# src/rag_mcp/mcp/clients/custom_client.py
from rag_mcp.mcp.clients.http_client import HTTPMCPClient

class CustomMCPClient(HTTPMCPClient):
    """Client for custom MCP server."""

    async def custom_method(self, param: str) -> dict:
        """Call a custom tool."""
        response = await self.call_tool("custom_tool", {"param": param})
        return response.result or {}
```

### Step 2: Register in Settings & Registry

```python
# In your application setup:
from rag_mcp.mcp.clients import CustomMCPClient

settings = get_settings()
client = CustomMCPClient(
    base_url="http://custom-server:8000",
    api_key="custom_key",
)
registry.register("custom", client)
```

### Step 3: Use in Pipeline Query

```python
result = await pipeline.query(
    "Your query",
    server_id="custom",
    tool_hint="custom_method",
)
```

## Development

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage report
uv run pytest --cov=src --cov-report=html

# Run specific test file
uv run pytest tests/mcp/test_registry.py

# Run with verbose output
uv run pytest -v
```

### Code Quality

```bash
# Type checking
uv run mypy src

# Linting
uv run ruff check src

# Format code
uv run ruff format src
```

### Project Structure

```
ledger-lens-rag/
├── src/rag_mcp/
│   ├── config/           # Settings & configuration
│   ├── mcp/              # MCP clients & registry
│   ├── embeddings/       # Text embedding providers
│   ├── retrieval/        # Vector storage & search
│   ├── llm/              # LLM backends
│   ├── pipeline/         # RAG pipeline orchestration
│   └── utils/            # Logging, retry logic
├── tests/                # Test suite
├── pyproject.toml        # Project metadata & dependencies
├── .env.example          # Environment template
└── README.md             # This file
```

## Key Components

### MCPClientRegistry
Centralized registry for managing MCP client connections. Supports multiple servers and async context management.

### InMemoryVectorStore
Lightweight in-memory vector store using numpy for cosine similarity search. Suitable for prototyping and small-scale deployments.

### RAGPipeline
Orchestrates the full RAG flow: embedding → retrieval → MCP call → context building → LLM generation.

### OpenAIEmbedder
Batches text embeddings to OpenAI API with configurable model selection.

### AnthropicLLM
Async Anthropic Claude integration with configurable model and token limits.

## Configuration

All settings are loaded from environment variables via Pydantic `BaseSettings`. See `.env.example` for all available options.

**Key Settings:**
- `TOP_K`: Number of documents to retrieve (default: 5)
- `SIMILARITY_THRESHOLD`: Minimum similarity score for retrieval (default: 0.7)
- `LLM_MAX_TOKENS`: Maximum tokens in LLM responses (default: 2048)
- `LOG_LEVEL`: Logging verbosity (default: INFO)

## Logging

Structured JSON logging is configured via `rag_mcp.utils.configure_logging()`. Each log line contains:

```json
{
  "timestamp": "2026-06-07T10:30:45.123456",
  "level": "INFO",
  "logger": "rag_mcp.pipeline.rag_pipeline",
  "message": "Starting RAG query: What is TCS?",
  "extra": {}
}
```

## Error Handling

All custom exceptions inherit from `RagMCPError`:

- `MCPClientError`: MCP communication failures
- `EmbedderError`: Embedding generation failures
- `VectorStoreError`: Vector store operations
- `LLMError`: LLM generation failures
- `PipelineError`: Overall pipeline failures

## Performance Considerations

- **Vector Store**: In-memory store is fast but limited by available RAM. For production deployments, consider integrating Pinecone, Weaviate, or Milvus.
- **Embeddings**: Batch requests to OpenAI API (up to 100 texts per request).
- **Retry Logic**: Automatic exponential backoff on transient failures (max 3 attempts).
- **Concurrency**: Fully async implementation supports thousands of concurrent requests.

## Security

- **API Keys**: Never commit `.env` files with real credentials. Use environment variables.
- **Rate Limiting**: Implement rate limiting in production deployments.
- **Data Privacy**: Ensure sensitive data is not stored in logs or vector store metadata.

## Contributing

1. Create a feature branch: `git checkout -b feature/your-feature`
2. Write tests (aim for 80%+ coverage)
3. Follow code style: `uv run ruff format` and `uv run mypy src`
4. Submit a pull request

## License

MIT License - see LICENSE file for details.

## Support

For issues or questions:
1. Check existing GitHub issues
2. Review the architecture documentation
3. Run tests to verify your setup: `uv run pytest --cov=src`

## Roadmap

- [ ] Support for additional MCP servers (crypto, weather, etc.)
- [ ] PostgreSQL-backed vector store integration
- [ ] Pinecone/Weaviate cloud support
- [ ] Web API (FastAPI)
- [ ] CLI tool for batch queries
- [ ] Evaluation metrics & benchmarking
- [ ] Fine-tuned embedding models
- [ ] Multi-language support

---

**Built with Python 3.14, asyncio, Pydantic, and best practices in mind.**
