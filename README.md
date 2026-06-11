# LedgerLens RAG API

A production-quality Retrieval-Augmented Generation (RAG) service built with FastAPI, LangChain, FAISS, and OpenAI.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env and set OPENAI_API_KEY
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | *(required)* | Your OpenAI API key |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | OpenAI embedding model |
| `LLM_MODEL` | `gpt-4o-mini` | OpenAI chat model for answer generation |
| `CHUNK_SIZE` | `1000` | Characters per chunk |
| `CHUNK_OVERLAP` | `200` | Overlap between consecutive chunks |
| `FAISS_INDEX_PATH` | `faiss_index` | Local directory for the persisted FAISS index |
| `DEFAULT_TOP_K` | `4` | Default number of chunks to retrieve |

## Run

```bash
uvicorn app.main:app --reload
```

Swagger docs available at `http://localhost:8000/docs`.

## API

### POST /api/v1/ingest

```bash
curl -X POST http://localhost:8000/api/v1/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "documents": [
      {
        "id": "doc-001",
        "text": "Employees receive 24 days of paid leave per year...",
        "metadata": {"source": "handbook.pdf", "tags": ["hr"]}
      }
    ]
  }'
```

### POST /api/v1/query

```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the leave policy?",
    "top_k": 4,
    "generate_answer": true
  }'
```

### GET /api/v1/health

```bash
curl http://localhost:8000/api/v1/health
```

## Tests

```bash
pytest
```

## Project Structure

```
app/
  main.py              # FastAPI app, lifespan, router registration
  config.py            # Pydantic Settings
  api/
    routes.py          # /ingest, /query, /health handlers
    schemas.py         # Pydantic request/response models
    dependencies.py    # build_pipeline() / DI wiring (only place concrete classes appear)
  core/
    interfaces.py      # BaseChunker, BaseEmbedder, BaseVectorStore, BaseLLM
    pipeline.py        # RAGPipeline orchestrator
    chunking.py        # RecursiveChunker
    embeddings.py      # OpenAIEmbedder
    vector_store.py    # FAISSVectorStore
    llm.py             # OpenAIChatLLM
  exceptions.py        # Custom exceptions + handlers
tests/
  test_pipeline.py     # Pipeline tests with mocked interfaces
  test_api.py          # Endpoint tests with FastAPI TestClient
```
