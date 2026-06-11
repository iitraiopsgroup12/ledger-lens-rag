# Build Prompt — LangChain RAG System with FastAPI

> Paste this into your coding assistant (or use it as a design spec) to generate the system.
> It defines the API contract, the object-oriented component design, and the implementation constraints.

---

## Role

You are a senior Python engineer. Build a production-quality **Retrieval-Augmented Generation (RAG)** service exposed over **FastAPI**. The system must be built on **LangChain**, use **FAISS** as the vector store, and use **OpenAI embeddings** for vectorization. Every major component must be **loosely coupled** behind an abstract interface so that any single piece (embedder, vector store, chunker, LLM) can be swapped without touching the rest of the code.

---

## Tech stack (use exactly these unless stated otherwise)

- Python 3.14+
- FastAPI + Uvicorn (ASGI server)
- Pydantic v2 (request/response models and settings)
- LangChain (`langchain`, `langchain-openai`, `langchain-community`)
- FAISS (`faiss-cpu`) as the vector store
- OpenAI embeddings (`text-embedding-3-small` by default, model name configurable)
- OpenAI chat model for answer generation (`gpt-4o-mini` by default, configurable)
- `python-dotenv` / Pydantic `BaseSettings` for configuration
- `pytest` for tests

---

## Architectural principles (non-negotiable)

1. **Dependency inversion.** High-level orchestration (the RAG pipeline) depends on abstract interfaces, never on concrete classes. Concrete implementations (`OpenAIEmbedder`, `FAISSVectorStore`, etc.) are injected at construction time.
2. **Single responsibility.** Each class does one thing: loading, chunking, embedding, storing, retrieving, generating.
3. **Open/closed.** Adding a new embedder or vector store means writing a new class that implements the existing interface — no edits to existing components.
4. **No business logic in the API layer.** FastAPI route handlers only validate input, call the pipeline, and shape the response. All RAG logic lives in the service/domain layer.
5. **Stateless endpoints.** Shared objects (pipeline, vector store) are created once at startup and injected via FastAPI dependency injection.

---

## Component design (abstract interfaces → concrete implementations)

Define abstract base classes (using `abc.ABC` / `@abstractmethod`) for each role, then provide one concrete implementation each. Use these names.

### 1. `BaseChunker`
```python
class BaseChunker(ABC):
    @abstractmethod
    def split(self, text: str, metadata: dict) -> list[Document]: ...
```
- Concrete: `RecursiveChunker` wrapping LangChain's `RecursiveCharacterTextSplitter`. Chunk size and overlap come from config.

### 2. `BaseEmbedder`
```python
class BaseEmbedder(ABC):
    @abstractmethod
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    @abstractmethod
    def embed_query(self, text: str) -> list[float]: ...
```
- Concrete: `OpenAIEmbedder` wrapping `langchain_openai.OpenAIEmbeddings`. Model name configurable.

### 3. `BaseVectorStore`
```python
class BaseVectorStore(ABC):
    @abstractmethod
    def add_documents(self, documents: list[Document]) -> list[str]: ...
    @abstractmethod
    def similarity_search(self, query: str, k: int, filter: dict | None) -> list[Document]: ...
    @abstractmethod
    def persist(self) -> None: ...
    @abstractmethod
    def load(self) -> None: ...
```
- Concrete: `FAISSVectorStore` wrapping LangChain's `FAISS`. It is constructed with a `BaseEmbedder`. Index is persisted to and loaded from a configurable local path.

### 4. `BaseLLM`
```python
class BaseLLM(ABC):
    @abstractmethod
    def generate(self, question: str, context: list[Document]) -> str: ...
```
- Concrete: `OpenAIChatLLM` wrapping `langchain_openai.ChatOpenAI`. Uses a prompt template that grounds the answer in the retrieved context and instructs the model to say it doesn't know when the context is insufficient.

### 5. `RAGPipeline` (orchestrator)
- Constructor takes `chunker: BaseChunker`, `vector_store: BaseVectorStore`, `llm: BaseLLM` — all by interface.
- `ingest(documents: list[IngestDocument]) -> IngestResult` — chunk → embed → store → persist.
- `query(question: str, k: int, generate_answer: bool) -> QueryResult` — retrieve top-k → optionally generate grounded answer.

### Wiring
- A single `build_pipeline()` factory (or a DI container module) reads config and assembles the concrete objects into a `RAGPipeline`. This is the **only** place concrete classes are named. Swapping FAISS for another store or OpenAI for another embedder happens here alone.

---

## API specification

Base path: `/api/v1`. Use Pydantic models for every request and response. Document all models so they render in the auto-generated OpenAPI/Swagger docs.

### `POST /api/v1/ingest`
Ingests one or more documents into the RAG pipeline.

**Request body**
```json
{
  "documents": [
    {
      "id": "doc-001",
      "text": "Full text content to be ingested...",
      "metadata": { "source": "handbook.pdf", "author": "Jane Doe", "tags": ["hr"] }
    }
  ]
}
```
- `documents`: non-empty list. Each item: `id` (optional string), `text` (required, non-empty), `metadata` (optional object).

**Response `200`**
```json
{
  "status": "success",
  "ingested_documents": 1,
  "chunks_created": 14,
  "vector_ids": ["..."],
  "took_ms": 832
}
```

### `POST /api/v1/query`
Runs retrieval (and optional generation) against the ingested corpus.

**Request body**
```json
{
  "query": "What is the leave policy?",
  "top_k": 4,
  "generate_answer": true,
  "filter": { "tags": "hr" }
}
```
- `query`: required, non-empty. `top_k`: optional int, default 4, range 1–20. `generate_answer`: optional bool, default `true`. `filter`: optional metadata filter.

**Response `200`**
```json
{
  "query": "What is the leave policy?",
  "answer": "Employees receive 24 days of paid leave...",
  "sources": [
    {
      "text": "matched chunk text",
      "score": 0.83,
      "metadata": { "source": "handbook.pdf", "doc_id": "doc-001" }
    }
  ],
  "took_ms": 410
}
```
- When `generate_answer` is `false`, `answer` is `null` and only `sources` are returned.

### `GET /api/v1/health`
Returns `{ "status": "ok" }` plus whether the vector index is loaded and how many vectors it holds.

### Error contract (all endpoints)
Return a consistent JSON error shape and correct HTTP status codes:
```json
{ "error": { "code": "VALIDATION_ERROR", "message": "documents must not be empty" } }
```
- `400` validation errors, `404` empty/missing index on query, `500` unexpected failures, `503` if the embedding/LLM provider is unreachable.

---

## Non-functional requirements

- **Configuration** via environment variables / `.env` using a Pydantic `Settings` class: `OPENAI_API_KEY`, `EMBEDDING_MODEL`, `LLM_MODEL`, `CHUNK_SIZE`, `CHUNK_OVERLAP`, `FAISS_INDEX_PATH`, `DEFAULT_TOP_K`. Never hardcode the API key.
- **Logging** with structured, level-based logs (request received, chunks created, retrieval latency).
- **Startup/shutdown** lifecycle: load the FAISS index on startup if it exists; persist on ingest. Inject the pipeline through FastAPI `Depends`.
- **Async** route handlers; offload blocking embedding/index calls appropriately so the event loop is not blocked.
- **Type hints everywhere** and docstrings on public classes/methods.

---

## Project structure (deliver exactly this layout)

```
app/
  main.py                 # FastAPI app, lifespan, router registration
  config.py               # Pydantic Settings
  api/
    routes.py             # /ingest, /query, /health handlers (thin)
    schemas.py            # Pydantic request/response models
    dependencies.py       # build_pipeline() / DI wiring
  core/
    interfaces.py         # BaseChunker, BaseEmbedder, BaseVectorStore, BaseLLM
    pipeline.py           # RAGPipeline orchestrator
    chunking.py           # RecursiveChunker
    embeddings.py         # OpenAIEmbedder
    vector_store.py       # FAISSVectorStore
    llm.py                # OpenAIChatLLM
  exceptions.py           # custom exceptions + handlers
tests/
  test_pipeline.py        # pipeline with mocked embedder/store
  test_api.py             # endpoint tests with FastAPI TestClient
requirements.txt
.env.example
README.md
```

---

## Testing requirements

- Unit-test `RAGPipeline` with **mocked** `BaseEmbedder`, `BaseVectorStore`, and `BaseLLM` (no network calls) to prove loose coupling.
- API tests using `fastapi.testclient.TestClient` covering: successful ingest, successful query with and without generation, validation errors, and query against an empty index.

---

## Deliverables

1. All source files per the structure above, runnable with `uvicorn app.main:app --reload`.
2. `requirements.txt` and `.env.example`.
3. A `README.md` with setup, env-var table, run instructions, and `curl` examples for both endpoints.
4. Working tests that pass with `pytest`.

## Constraints

- Do **not** put any RAG logic in the route handlers.
- Do **not** reference concrete implementation classes anywhere except the DI/factory module.
- Keep each concrete class swappable purely by editing the factory.
