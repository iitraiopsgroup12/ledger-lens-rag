# Technical Reference Card

**RAG MCP Pipeline** | **Python 3.14+** | **June 7, 2026**

---

## 🏗️ Core Architecture

### Exception Hierarchy
```
RagMCPError (base)
├── MCPClientError
├── EmbedderError
├── VectorStoreError
├── LLMError
├── PipelineError
└── ServerNotFoundError
```

### Module Dependencies
```
Pipeline
├── MCP Registry
│   └── MCPClient (HTTP/ISE)
├── Embedder (OpenAI)
├── VectorStore (In-Memory)
├── LLMBackend (Anthropic)
├── ContextBuilder
└── Settings
```

---

## 📝 Common Code Patterns

### Using the Pipeline
```python
from rag_mcp.pipeline import RAGPipeline
from rag_mcp.config import get_settings

settings = get_settings()
pipeline = RAGPipeline(...)
result = await pipeline.query("query", server_id="ise")
```

### Registering MCP Servers
```python
from rag_mcp.mcp.registry import MCPClientRegistry
from rag_mcp.mcp.clients import ISEMCPClient

registry = MCPClientRegistry()
client = ISEMCPClient(url, key)
registry.register("ise", client)
```

### Adding Documents
```python
from rag_mcp.retrieval import Document, InMemoryVectorStore

store = InMemoryVectorStore()
docs = [Document(id="1", content="...", metadata={"embedding": [...]}) ]
await store.add(docs)
```

### Embedding Text
```python
from rag_mcp.embeddings import OpenAIEmbedder

embedder = OpenAIEmbedder(api_key, model)
vectors = await embedder.embed(["text1", "text2"])
```

### Generating Responses
```python
from rag_mcp.llm import AnthropicLLM

llm = AnthropicLLM(api_key, model, max_tokens)
response = await llm.complete(system_prompt, messages)
```

---

## 🔧 Configuration Keys

```env
# MCP
ISE_MCP_BASE_URL=http://localhost:8000
ISE_API_KEY=key

# LLM
ANTHROPIC_API_KEY=key
LLM_MODEL=claude-sonnet-4-20250514
LLM_MAX_TOKENS=2048

# Embeddings
OPENAI_API_KEY=key
EMBEDDING_MODEL=text-embedding-3-small

# Retrieval
TOP_K=5
SIMILARITY_THRESHOLD=0.7

# App
LOG_LEVEL=INFO
```

---

## 🧪 Testing Quick Commands

```bash
# All tests
uv run pytest

# With coverage
uv run pytest --cov=src --cov-report=html

# Specific test file
uv run pytest tests/mcp/test_http_client.py -v

# Single test
uv run pytest tests/mcp/test_registry.py::test_registry_register_and_get -v

# Coverage summary
uv run pytest --cov=src --cov-report=term-missing

# Parallel execution
uv run pytest -n auto
```

---

## 🔍 Code Quality Commands

```bash
# Type checking
uv run mypy src

# Linting
uv run ruff check src

# Format check
uv run ruff format src --check

# Apply formatting
uv run ruff format src

# All checks
uv run mypy src && uv run ruff check src
```

---

## 📊 Class Reference

### MCPClientRegistry
```python
registry = MCPClientRegistry()
registry.register(server_id, client)
client = registry.get(server_id)
servers = registry.list_servers()
async with registry as r: ...
```

### HTTPMCPClient
```python
client = HTTPMCPClient(base_url, api_key, timeout)
response = await client.call_tool(tool_name, arguments)
tools = await client.list_tools()
healthy = await client.health_check()
```

### ISEMCPClient
```python
client = ISEMCPClient(base_url, api_key)
data = await client.get_stock_data(name)
data = await client.get_trending_stocks()
data = await client.get_52_week_high_low()
# ... 7 more methods
```

### OpenAIEmbedder
```python
embedder = OpenAIEmbedder(api_key, model)
vectors = await embedder.embed(texts)  # list[list[float]]
```

### InMemoryVectorStore
```python
store = InMemoryVectorStore(similarity_threshold)
await store.add(documents)
results = await store.search(query_vector, top_k)
```

### AnthropicLLM
```python
llm = AnthropicLLM(api_key, model, max_tokens)
response = await llm.complete(system, messages)
```

### RAGPipeline
```python
pipeline = RAGPipeline(registry, embedder, store, llm, builder, settings)
result = await pipeline.query(user_query, server_id, tool_hint)
```

---

## 📦 Data Models

### MCPRequest
```python
MCPRequest(
    jsonrpc="2.0",
    method="tool_name",
    params={...},
    id=1
)
```

### MCPResponse
```python
MCPResponse(
    jsonrpc="2.0",
    result={...} | None,
    error={...} | None,
    id=1
)
```

### Document
```python
Document(
    id="doc_id",
    content="text content",
    metadata={"embedding": [...], "source": "..."}
)
```

### ScoredDocument
```python
ScoredDocument(
    id="doc_id",
    content="text",
    metadata={...},
    score=0.85  # similarity score
)
```

### PipelineResult
```python
PipelineResult(
    answer="generated answer",
    sources=["source1", "source2"],
    mcp_data={...},
    tool_used="tool_name",
    confidence=0.92
)
```

### Settings
```python
settings = get_settings()
# All from .env:
settings.openai_api_key
settings.anthropic_api_key
settings.ise_mcp_base_url
settings.top_k
settings.similarity_threshold
# ... etc
```

---

## 🔄 Async Patterns

### Retry Decorator
```python
from rag_mcp.utils import async_retry

@async_retry(max_attempts=3, initial_wait=1.0, max_wait=10.0)
async def my_function():
    pass
```

### Context Manager
```python
async with MCPClientRegistry() as registry:
    client = ISEMCPClient(...)
    registry.register("ise", client)
# Automatically closed on exit
```

### Batch Processing
```python
# OpenAI Embedder automatically batches up to 100 texts
vectors = await embedder.embed(1000_texts)
```

---

## 🎯 Common Workflows

### Workflow 1: Add Documents & Query
```python
# 1. Initialize embedder
embedder = OpenAIEmbedder(key, model)

# 2. Embed texts
vectors = await embedder.embed(texts)

# 3. Create documents
docs = [Document(id=i, content=t, metadata={"embedding": v}) 
        for i, (t, v) in enumerate(zip(texts, vectors))]

# 4. Add to store
store = InMemoryVectorStore()
await store.add(docs)

# 5. Query pipeline
pipeline = RAGPipeline(...)
result = await pipeline.query("my question")
```

### Workflow 2: Multiple MCP Servers
```python
registry = MCPClientRegistry()

# Register ISE server
ise = ISEMCPClient(url1, key1)
registry.register("ise", ise)

# Register Crypto server
crypto = CustomMCPClient(url2, key2)
registry.register("crypto", crypto)

# Query with specific server
result = await pipeline.query("...", server_id="crypto")
```

### Workflow 3: Error Handling
```python
from rag_mcp.pipeline import PipelineError
from rag_mcp.mcp.clients import MCPClientError

try:
    result = await pipeline.query("query")
except MCPClientError as e:
    print(f"MCP error: {e}")
except PipelineError as e:
    print(f"Pipeline error: {e}")
```

---

## 📈 Performance Tips

| Operation | Time | Optimization |
|-----------|------|--------------|
| Embedding | API call | Batch up to 100 texts |
| Vector Search | O(n) | Use external DB for >10K docs |
| MCP Call | API call | Cache responses |
| LLM Gen | API call | Stream responses |

**Memory Usage:**
- In-memory store: ~1GB per 1M embeddings (384-dim)
- Embedder batch: 100 texts ≈ 1-5MB

---

## 🐛 Debugging

### Enable Debug Logging
```python
from rag_mcp.utils import configure_logging
configure_logging("DEBUG")
```

### Check Server Health
```python
client = ISEMCPClient(url, key)
is_healthy = await client.health_check()
print(f"Server healthy: {is_healthy}")
```

### List Available Tools
```python
tools = await client.list_tools()
for tool in tools:
    print(f"Tool: {tool.name} - {tool.description}")
```

### Type Check Specific File
```bash
uv run mypy src/rag_mcp/pipeline/rag_pipeline.py
```

---

## 🔐 Security Checklist

- [ ] Never commit `.env` file
- [ ] Use strong API keys (20+ chars)
- [ ] Rotate keys regularly
- [ ] Use VPN for sensitive data
- [ ] Audit logging for PII
- [ ] Validate MCP server certificates
- [ ] Rate limit API calls
- [ ] Monitor for unusual patterns

---

## 📚 File Locations Quick Reference

| Component | Location |
|-----------|----------|
| Settings | `src/rag_mcp/config/__init__.py` |
| MCP Base | `src/rag_mcp/mcp/base.py` |
| HTTP Client | `src/rag_mcp/mcp/clients/http_client.py` |
| ISE Client | `src/rag_mcp/mcp/clients/ise_client.py` |
| Embeddings | `src/rag_mcp/embeddings/openai_embedder.py` |
| Vector Store | `src/rag_mcp/retrieval/in_memory_store.py` |
| LLM | `src/rag_mcp/llm/anthropic_llm.py` |
| Pipeline | `src/rag_mcp/pipeline/rag_pipeline.py` |
| Tests | `tests/` |

---

## ✅ Verification Checklist

After setup, run:

```bash
# 1. Syntax
python -m py_compile src/rag_mcp/**/*.py

# 2. Dependencies
uv pip list

# 3. Tests
uv run pytest --cov=src

# 4. Type Checking
uv run mypy src

# 5. Linting
uv run ruff check src

# 6. Import Check
python -c "import rag_mcp; print(rag_mcp.RagMCPError)"
```

**All should succeed before deployment!**

---

## 🚀 Deployment Checklist

- [ ] All tests passing
- [ ] No type errors (mypy)
- [ ] No lint errors (ruff)
- [ ] .env configured
- [ ] API keys valid
- [ ] MCP server running
- [ ] Logging configured
- [ ] Error handling in place
- [ ] Documentation reviewed
- [ ] Code reviewed

---

**Generated:** June 7, 2026 | **Version:** 0.1.0 | **Status:** ✅ Production Ready

