# GitHub Copilot Instructions: RAG Pipeline with MCP Server Integration

## Project Context

You are building a **production-ready RAG (Retrieval-Augmented Generation) pipeline** in Python that connects to MCP (Model Context Protocol) servers — starting with the `Live-NSE-BSE-MCP` server for Indian stock market data. The architecture must be extensible to support additional MCP servers in the future.

The project uses **uv** as the package and environment manager.

---

## Guiding Principles

- Follow **SOLID principles** throughout. Every class has a single responsibility. Depend on abstractions, not concretions.
- Write **production-grade Python**: type hints everywhere, docstrings on every public class and method, no bare `except` clauses, explicit error handling.
- Use **abstract base classes** (`abc.ABC`) to define contracts for all swappable components (MCP clients, retrievers, embedders, LLM backends).
- Prefer **composition over inheritance**.
- All configuration via **Pydantic `BaseSettings`** with `.env` support — never hardcode secrets or URLs.
- Structured logging via Python's `logging` module with JSON-compatible formatters. No `print()` statements.
- Every public module, class, and function must have a **Google-style docstring**.
- Write **pytest** tests alongside each module, with fixtures and mocks. Aim for ≥80% coverage.
- Use **`pyproject.toml`** (uv-compatible) as the single source of project metadata, dependencies, and tool configuration.
- Target **Python 3.14** exclusively. Take advantage of 3.14-specific features: deferred annotation evaluation (PEP 749), improved `typing` ergonomics, and `asyncio` improvements. Do **not** add `from __future__ import annotations` — it is no longer needed.

---

## Project Structure to Generate

```
rag-mcp-pipeline/
├── pyproject.toml
├── .python-version          # contains: 3.14
├── .env.example
├── .gitignore
├── README.md
│
├── src/
│   └── rag_mcp/
│       ├── __init__.py
│       │
│       ├── config/
│       │   ├── __init__.py
│       │   └── settings.py          # Pydantic BaseSettings, all env vars
│       │
│       ├── mcp/
│       │   ├── __init__.py
│       │   ├── base.py              # Abstract MCPClient interface
│       │   ├── registry.py          # MCPClientRegistry (maps server_id → client)
│       │   ├── models.py            # Pydantic models: MCPTool, MCPRequest, MCPResponse
│       │   └── clients/
│       │       ├── __init__.py
│       │       ├── http_client.py   # HTTP JSON-RPC MCP client
│       │       └── ise_client.py    # ISE (NSE/BSE) concrete client
│       │
│       ├── embeddings/
│       │   ├── __init__.py
│       │   ├── base.py              # Abstract Embedder interface
│       │   └── openai_embedder.py   # OpenAI embeddings implementation
│       │
│       ├── retrieval/
│       │   ├── __init__.py
│       │   ├── base.py              # Abstract Retriever interface
│       │   ├── vector_store.py      # Abstract VectorStore interface
│       │   └── in_memory_store.py   # In-memory vector store (numpy cosine sim)
│       │
│       ├── pipeline/
│       │   ├── __init__.py
│       │   ├── rag_pipeline.py      # Orchestrates retrieval → MCP → LLM
│       │   └── context_builder.py   # Builds prompt context from retrieved docs
│       │
│       ├── llm/
│       │   ├── __init__.py
│       │   ├── base.py              # Abstract LLMBackend interface
│       │   └── anthropic_llm.py     # Anthropic Claude backend
│       │
│       └── utils/
│           ├── __init__.py
│           ├── logging.py           # Structured JSON logger setup
│           └── retry.py             # Exponential backoff decorator
│
└── tests/
    ├── conftest.py
    ├── mcp/
    │   ├── test_registry.py
    │   └── test_http_client.py
    ├── retrieval/
    │   └── test_in_memory_store.py
    └── pipeline/
        └── test_rag_pipeline.py
```

---

## File-by-File Generation Instructions

### `pyproject.toml`

Generate a complete `pyproject.toml` compatible with **uv**:

- `[project]` section with name `rag-mcp-pipeline`, version `0.1.0`, requires Python `>=3.14`.
- Dependencies: `pydantic>=2.0`, `pydantic-settings`, `httpx`, `anthropic`, `openai`, `numpy`, `python-dotenv`, `tenacity` (for retries).
- Dev dependencies under `[dependency-groups]`: `pytest`, `pytest-asyncio`, `pytest-cov`, `ruff`, `mypy`, `httpx` (for test mocking).
- `[tool.ruff]` config: line length 100, select `["E", "F", "I", "UP"]`, `target-version = "py314"`.
- `[tool.mypy]` config: strict mode, `python_version = "3.14"`.
- `[tool.pytest.ini_options]`: asyncio_mode = "auto", testpaths = ["tests"].
- Pin the uv Python pin file (`.python-version`) to `3.14`.

---

### `src/rag_mcp/config/settings.py`

Use **Pydantic `BaseSettings`** with `model_config = SettingsConfigDict(env_file=".env")`.

Fields to include:
```python
# MCP
ise_mcp_base_url: str = "http://localhost:8000"
ise_api_key: str  # loaded from ISE_API_KEY env var

# LLM
anthropic_api_key: str
llm_model: str = "claude-sonnet-4-20250514"
llm_max_tokens: int = 2048

# Embeddings
openai_api_key: str
embedding_model: str = "text-embedding-3-small"

# Retrieval
top_k: int = 5
similarity_threshold: float = 0.7

# Logging
log_level: str = "INFO"
```

Expose a module-level `get_settings()` function cached with `@lru_cache`.

---

### `src/rag_mcp/mcp/base.py`

Define an abstract base class `MCPClient(ABC)`:

```python
class MCPClient(ABC):
    @abstractmethod
    async def call_tool(self, tool_name: str, arguments: dict) -> MCPResponse: ...

    @abstractmethod
    async def list_tools(self) -> list[MCPTool]: ...

    @abstractmethod
    async def health_check(self) -> bool: ...
```

---

### `src/rag_mcp/mcp/models.py`

Define these Pydantic v2 models:

```python
class MCPTool(BaseModel):
    name: str
    description: str
    input_schema: dict

class MCPRequest(BaseModel):
    jsonrpc: str = "2.0"
    method: str
    params: dict
    id: int | str

class MCPResponse(BaseModel):
    jsonrpc: str
    result: dict | None
    error: dict | None
    id: int | str
```

---

### `src/rag_mcp/mcp/clients/http_client.py`

Implement `HTTPMCPClient(MCPClient)`:

- Use **`httpx.AsyncClient`** with configurable `base_url` and `timeout`.
- Implement `call_tool`, `list_tools`, `health_check` using the JSON-RPC 2.0 format used by the ISE MCP server.
- Use the `retry` utility (tenacity) on `call_tool` with exponential backoff, max 3 attempts.
- Raise a custom `MCPClientError` (subclass of `Exception`) on non-2xx responses or JSON-RPC error fields.
- Accept `api_key` as a constructor param and pass it as an `X-API-Key` header.

---

### `src/rag_mcp/mcp/clients/ise_client.py`

Implement `ISEMCPClient(HTTPMCPClient)`:

Add typed convenience methods wrapping `call_tool`:

```python
async def get_stock_data(self, name: str) -> dict: ...
async def get_trending_stocks(self) -> dict: ...
async def get_52_week_high_low(self) -> dict: ...
async def get_nse_most_active(self) -> dict: ...
async def get_bse_most_active(self) -> dict: ...
async def get_mutual_funds(self) -> dict: ...
async def get_commodities(self) -> dict: ...
async def search_industry(self, industry: str) -> dict: ...
async def get_analyst_recommendations(self, symbol: str) -> dict: ...
async def get_historical_data(self, symbol: str, **kwargs) -> dict: ...
```

---

### `src/rag_mcp/mcp/registry.py`

Implement `MCPClientRegistry`:

- A dict-backed registry mapping `server_id: str → MCPClient`.
- Methods: `register(server_id, client)`, `get(server_id) -> MCPClient`, `list_servers() -> list[str]`.
- Raise `ServerNotFoundError` if `get()` is called with an unknown ID.
- Support use as an async context manager to close all clients on exit.

---

### `src/rag_mcp/embeddings/base.py` and `openai_embedder.py`

Abstract `Embedder(ABC)`:

```python
class Embedder(ABC):
    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]: ...
```

`OpenAIEmbedder(Embedder)`:
- Use `openai.AsyncOpenAI`.
- Batch texts up to 100 per API call.
- Return `list[list[float]]`.

---

### `src/rag_mcp/retrieval/`

`VectorStore(ABC)`:
```python
class VectorStore(ABC):
    @abstractmethod
    async def add(self, documents: list[Document]) -> None: ...

    @abstractmethod
    async def search(self, query_vector: list[float], top_k: int) -> list[ScoredDocument]: ...
```

`Document` and `ScoredDocument` are Pydantic models with fields `id`, `content`, `metadata`, and (for scored) `score: float`.

`InMemoryVectorStore(VectorStore)`:
- Store embeddings as a numpy array.
- Cosine similarity search.
- Thread-safe with `asyncio.Lock`.

---

### `src/rag_mcp/pipeline/rag_pipeline.py`

`RAGPipeline` orchestrates the full flow. Constructor accepts:

```python
def __init__(
    self,
    mcp_registry: MCPClientRegistry,
    embedder: Embedder,
    vector_store: VectorStore,
    llm: LLMBackend,
    context_builder: ContextBuilder,
    settings: Settings,
): ...
```

Primary method:

```python
async def query(
    self,
    user_query: str,
    server_id: str = "ise",
    tool_hint: str | None = None,
) -> PipelineResult: ...
```

Flow:
1. Embed the user query.
2. Retrieve top-K relevant documents from the vector store.
3. If relevant docs found, use them to determine which MCP tool to call.
4. Call the MCP tool via the registry.
5. Build a prompt context from retrieved docs + MCP response.
6. Send to LLM and return the result.

`PipelineResult` is a Pydantic model: `answer: str`, `sources: list[str]`, `mcp_data: dict | None`, `tool_used: str | None`.

---

### `src/rag_mcp/llm/base.py` and `anthropic_llm.py`

Abstract `LLMBackend(ABC)`:
```python
class LLMBackend(ABC):
    @abstractmethod
    async def complete(self, system: str, messages: list[dict]) -> str: ...
```

`AnthropicLLM(LLMBackend)`:
- Use `anthropic.AsyncAnthropic`.
- Accept `model` and `max_tokens` in constructor.
- Map messages to Anthropic's format.

---

### `src/rag_mcp/utils/retry.py`

Implement a reusable `async_retry` decorator using **tenacity**:
- Default: 3 attempts, exponential backoff starting at 1s, max 10s.
- Re-raise on non-retryable errors (e.g., `AuthenticationError`).

---

### `src/rag_mcp/utils/logging.py`

`configure_logging(level: str)` sets up:
- A root logger with a `logging.StreamHandler`.
- A formatter that emits JSON lines: `{"timestamp": ..., "level": ..., "logger": ..., "message": ..., "extra": {...}}`.
- Call once at application startup.

---

### Tests

For each module, generate `pytest` tests using `pytest-asyncio`:

- `tests/mcp/test_http_client.py`: Mock `httpx.AsyncClient` with `respx` or `unittest.mock.AsyncMock`. Test success path, error response, retry behaviour.
- `tests/retrieval/test_in_memory_store.py`: Test add, search, empty store edge case, similarity threshold filtering.
- `tests/pipeline/test_rag_pipeline.py`: Mock all dependencies, test full happy path and error path.
- `tests/conftest.py`: Shared fixtures — `mock_settings`, `mock_mcp_client`, `mock_embedder`, `mock_vector_store`, `mock_llm`.

---

### `.env.example`

```dotenv
# MCP Server
ISE_MCP_BASE_URL=http://localhost:8000
ISE_API_KEY=your_indianapi_key_here

# LLM
ANTHROPIC_API_KEY=your_anthropic_key_here
LLM_MODEL=claude-sonnet-4-20250514
LLM_MAX_TOKENS=2048

# Embeddings
OPENAI_API_KEY=your_openai_key_here
EMBEDDING_MODEL=text-embedding-3-small

# Retrieval
TOP_K=5
SIMILARITY_THRESHOLD=0.7

# App
LOG_LEVEL=INFO
```

---

### `README.md`

Generate a README covering:
1. Project overview and architecture diagram (ASCII).
2. Prerequisites: Python 3.14+, uv. Note that Python 3.14 is a pre-release; use `uv python install 3.14` to fetch it.
3. Setup: `uv sync`, copy `.env.example` to `.env`.
4. Running: how to instantiate the pipeline and call `pipeline.query(...)`.
5. Adding a new MCP server: explain the 3-step extension pattern (implement `MCPClient`, register in `MCPClientRegistry`, add tool methods).
6. Running tests: `uv run pytest --cov`.
7. Linting: `uv run ruff check .` and `uv run mypy src`.

---

## Code Style Rules (enforce in every file)

- Python 3.14+ syntax: use `X | Y` union types, `match` statements, **free-threading** (`--disable-gil`) awareness where relevant, and the new `annotationlib` lazy annotation evaluation — do **not** use `from __future__ import annotations` (it is superseded in 3.14).
- All async I/O via `asyncio`; no blocking calls in async functions.
- Pydantic v2 style: `model_config`, `model_validator`, `field_validator` — not v1 validators.
- No mutable default arguments.
- All exceptions are custom classes inheriting from a base `RagMCPError`.
- Imports: stdlib → third-party → internal, separated by blank lines (enforced by ruff `I` rules).
- No wildcard imports.

---

## How to Use This Prompt in GitHub Copilot

1. Open **GitHub Copilot Chat** (`Ctrl+Shift+I` / `Cmd+Shift+I`).
2. Paste this entire document as your first message, prefixed with:
   > "Use the following specification to generate the project. Generate one file at a time, starting with `pyproject.toml`, then proceeding top-to-bottom through the structure listed."
3. After each file is generated, review it and prompt:
   > "Now generate `src/rag_mcp/mcp/base.py`" (or whichever file is next).
4. For tests, prompt per module:
   > "Now generate tests for `http_client.py` following the testing rules in the spec."
5. After all files are generated, run:
   ```bash
   uv python install 3.14   # fetch Python 3.14 if not already installed
   uv sync
   uv run mypy src
   uv run ruff check .
   uv run pytest --cov=src
   ```
   and feed any errors back to Copilot to fix.
