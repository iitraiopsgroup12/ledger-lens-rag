# LedgerLens RAG — Service Architecture

LedgerLens is a FastAPI service that combines a **Retrieval-Augmented Generation (RAG)** pipeline over financial documents with an **agentic KPI workflow** (LangGraph) that performs authorized, human-approved KPI analysis for companies.

This document explains the service across the following areas:

1. [REST Endpoints](#1-rest-endpoints)
2. [Service Layer & Repository Layer](#2-service-layer--repository-layer)
3. [RAG Pipeline Design](#3-rag-pipeline-design)
4. [Chunking Strategies](#4-chunking-strategies)
5. [RAG Retrieval](#5-rag-retrieval)
6. [Agentic Workflow with Human-in-the-Loop for KPI](#6-agentic-workflow-with-human-in-the-loop-for-kpi)

> A companion visual diagram is in [`architecture.drawio`](./architecture.drawio) (3 pages: Layered Architecture, RAG Pipeline & Retrieval, KPI Agentic Workflow).

---

## High-Level Layering

The codebase is organized into clean layers, wired together through dependency injection (`app/api/dependencies.py`) so concrete providers (OpenAI / Anthropic / Google / HuggingFace, FAISS, PostgreSQL, local/AWS storage) are swappable behind abstract interfaces.

| Layer | Responsibility | Key modules |
|-------|----------------|-------------|
| **Client** | HTTP consumers, Swagger UI | — |
| **API** | REST endpoints, request/response schemas, DI, middleware | `app/api/routes.py`, `app/api/schemas.py`, `app/main.py` |
| **Service / Orchestration** | Coordinates the work | `app/core/pipeline.py` (`RAGPipeline`), `app/kpi/service.py` (`KPIService`), `app/kpi/graph.py` (LangGraph) |
| **Core / Domain** | Parsing, chunking, classification, embeddings, LLM, KPI nodes/registry | `app/core/*`, `app/kpi/*` |
| **Repository / Persistence** | Data access seams | `app/core/kpi_repository.py`, `app/core/vector_store.py`, `nse_data_storage/*` |
| **External** | PostgreSQL, FAISS index files, file storage (local/S3), LLM providers | — |

The abstract seams are defined in `app/core/interfaces.py`: `BaseChunker`, `BaseEmbedder`, `BaseVectorStore`, `BaseLLM`.

---

## 1. REST Endpoints

All endpoints are defined in `app/api/routes.py` under the router prefix **`/api/v1`**. The app is assembled in `app/main.py` (CORS middleware, exception handlers, OpenAPI 3.0.2 tweak for file pickers). Blocking work runs in a thread executor (`run_in_executor`) so the async event loop stays responsive.

| Method & Path | Purpose | Request | Response |
|---------------|---------|---------|----------|
| `POST /api/v1/ingest` | Ingest raw JSON documents into the vector store | `IngestRequest` — list of `{id?, text, metadata}` | `IngestResponse` |
| `POST /api/v1/ingest/file` | Upload one or more files, parse and ingest them | multipart: `files[]` + optional JSON `metadata` | `IngestResponse` |
| `POST /api/v1/query` | Ask a question against the vector store (RAG) | `QueryRequest` — `{query, top_k, generate_answer, filter}` | `QueryResponse` |
| `POST /api/v1/query-with-file` | Ask a question over an uploaded file (optionally persisting it) | multipart form: `query`, `file`, `top_k`, `generate_answer`, `filter`, `isIngest` | `QueryResponse` |
| `POST /api/v1/kpi/chat` | Start/continue the agentic KPI workflow for a company | form: `email`, `symbol`, `message`, `session_id?` | `KpiChatResponse` |
| `POST /api/v1/kpi/approve` | Resume a paused KPI workflow with a human decision (HITL) | `KpiApproveRequest` — `{email, session_id, interrupt_id?, decision, feedback?}` | `KpiChatResponse` |
| `GET /api/v1/health` | Liveness + index status | — | `HealthResponse` — `{status, index_loaded, vector_count}` |

### Endpoint details

**`POST /ingest`** — Maps each `IngestDocumentRequest` to an `IngestDocument` and calls `RAGPipeline.ingest`. Returns counts (`ingested_documents`, `chunks_created`), `vector_ids`, timing, and the per-document `doc_types` assigned by the classifier.

**`POST /ingest/file`** — Reads all file bytes asynchronously first; calls `get_parser(filename)` early to reject unsupported types before reading. User-supplied `metadata` is merged with file-derived provenance keys (`source_file`, `file_type`, `content_type`), with provenance winning on conflicts. Parsing + ingestion happen inside the thread executor.

**`POST /query`** — Calls `RAGPipeline.query(query, top_k, generate_answer, filter)`. Returns the answer (if `generate_answer=true`) plus the ranked `sources` (text, relevance score, metadata).

**`POST /query-with-file`** — Two modes:
- `isIngest=true`: the file is parsed, ingested into the store, then a normal query runs.
- `isIngest=false` (default): the file is parsed and chunked **in-memory**, and `query_with_extra_context` unions those chunks into the LLM context **without persisting them** (they do not appear in returned `sources`).

**`POST /kpi/chat`** and **`POST /kpi/approve`** — Thin HTTP wrappers over `KPIService.chat` / `KPIService.resume`. See [section 6](#6-agentic-workflow-with-human-in-the-loop-for-kpi).

**Error handling** — Provider/connection errors are normalized to `ProviderUnavailableError`; KPI-specific failures to `KpiWorkflowError`. All `RAGException` subclasses are converted to structured JSON by the handlers registered in `app/main.py`.

---

## 2. Service Layer & Repository Layer

### Service / Orchestration Layer

| Component | File | Role |
|-----------|------|------|
| `RAGPipeline` | `app/core/pipeline.py` | Orchestrates chunking → embedding → storage (ingest) and retrieval → generation (query). Depends only on `BaseChunker`, `BaseVectorStore`, `BaseLLM`. |
| `KPIService` | `app/kpi/service.py` | FastAPI-facing entry point to the KPI workflow. Translates HTTP calls into LangGraph `invoke`/`resume`. Derives the checkpointer `thread_id = "{email}:{session_id}"` for per-user isolation. |
| Compiled LangGraph | `app/kpi/graph.py` | `StateGraph(KpiState)` compiled with a `MemorySaver` checkpointer; provides per-thread persistence and human-in-the-loop pauses via `interrupt`. |

`RAGPipeline` exposes three operations:
- `ingest(documents)` → chunk each doc, collect `doc_types`, add chunks to the vector store, persist, return `IngestResult`.
- `query(question, k, generate_answer, filter)` → similarity search, optional LLM answer, return `QueryResult`.
- `query_with_extra_context(...)` → same retrieval, but unions ephemeral `extra_docs` into the LLM context (used by `/query-with-file`).

### Repository / Persistence Layer

| Component | File | Backing store | Notes |
|-----------|------|---------------|-------|
| `KpiRepository` | `app/core/kpi_repository.py` | PostgreSQL (via SQLAlchemy) | **SELECT-only, fully parameterized.** No LLM-authored SQL ever reaches the DB. |
| `FAISSVectorStore` | `app/core/vector_store.py` | FAISS index files | Implements `BaseVectorStore`; persisted/loaded from a local directory. |
| `DataStorage` | `nse_data_storage/` | Local FS or AWS S3 | `LocalFileStorage` / `AwsFileStorage` behind a common `retrieve()` seam. |

`KpiRepository` is the single SQL boundary for the KPI workflow. Its methods:
- `get_user_by_email(email)` — resolve the user row (id, role, …).
- `find_company(query)` — resolve a company by exact symbol or `ILIKE` name/symbol.
- `list_company()` — list all companies.
- `is_user_authorized(user_id, company_id)` — true if an active `watchlists` row links the user to the company.
- `find_company_documents(company_id, symbol)` — collect candidate filings, normalizing storage pointers into `DocumentRef.storage_id` so downstream retrieval is table-agnostic.

`FAISSVectorStore` wraps LangChain's FAISS integration: `add_documents`, `similarity_search` (returns `(Document, relevance_score)` tuples), `persist`, `load`, `is_loaded`, `vector_count`.

---

## 3. RAG Pipeline Design

The RAG pipeline (`RAGPipeline`, `app/core/pipeline.py`) is assembled by `build_pipeline()` in `app/api/dependencies.py` as an `lru_cache` singleton. The provider stack is selected by `LLM_PROVIDER` in `.env`:

| Provider | LLM | Embedder |
|----------|-----|----------|
| `openai` (default) | `OpenAIChatLLM` | `OpenAIEmbedder` |
| `anthropic` | `AnthropicChatLLM` (Claude) | `AnthropicEmbedder` (Voyage AI) |
| `google` | `GoogleChatLLM` | `GoogleEmbedder` |
| `huggingface` | `HuggingFaceChatLLM` | `HuggingFaceEmbedder` |

### Ingestion flow

```
Documents (JSON text / uploaded files)
   → get_parser(filename).parse()            # bytes → text  (app/core/parsers.py)
   → AdaptiveChunker.split(text, metadata)   # routes to a strategy chunker
       → DocumentClassifier.classify()       # picks the document type
       → <Strategy>Chunker → Document[]      # + doc_type stamped onto metadata
   → FAISSVectorStore.add_documents()        # embed + index
   → FAISSVectorStore.persist()              # save index to disk
   → IngestResult(ingested_documents, chunks_created, vector_ids, took_ms, doc_types)
```

`RAGPipeline.ingest` iterates documents, copies metadata (adding `doc_id` if an id was supplied), splits each into chunks, records the assigned `doc_type` per document, then adds **all** chunks to the store in one call and persists.

### Supported file types (parsers)

`get_parser()` selects a parser by extension from the registry in `app/core/parsers.py`:

| Extension(s) | Parser |
|--------------|--------|
| `.pdf` | `PDFParser` (layout-aware `PDFParserExtended` also available for columnar financial tables) |
| `.docx` | `DocxParser` |
| `.xlsx`, `.xls` | `ExcelParser` |
| `.csv` | `CsvParser` |
| `.txt`, `.md` | `TextParser` |
| `.xml`, `.xbrl` | `XmlParser` |
| `.html`, `.htm` | `HtmlParser` |

Unsupported extensions raise `UnsupportedFileTypeError` early (before bytes are read).

### Startup

On startup (`app/main.py` `lifespan`), `build_pipeline()` is constructed and `vector_store.load()` rehydrates the FAISS index from disk so queries can be served immediately.

---

## 4. Chunking Strategies

Chunking lives in `app/core/chunking.py`. All concrete chunkers implement `BaseChunker.split(text, metadata) -> list[Document]`. The `AdaptiveChunker` is the orchestrator: it asks `DocumentClassifier` for the document type, dispatches to the matching strategy, and stamps `doc_type` onto every produced chunk.

### Document classification (`app/core/document_classifier.py`)

`DocumentClassifier.classify()` decides the type in three stages:

1. **`file_type` short-circuit** (highest confidence): `xlsx/xls/csv → TABULAR`, `md → MARKDOWN`.
2. **Keyword density scoring**: counts keyword hits per 1000 words for `invoice`, `financial_report`, `legal`.
3. **Structural boosts**: high tab/pipe density → `TABULAR`; many Markdown markers (`#`, ```` ``` ````, `**`, `- `) → `MARKDOWN`.

The highest-scoring type wins; if it falls below the density threshold (`0.5`), the document is treated as `NARRATIVE`.

### Strategy table

| Document type | Strategy class | Splitter & separators | chunk_size / overlap |
|---------------|----------------|-----------------------|----------------------|
| `INVOICE` | `InvoiceChunker` | `RecursiveCharacterTextSplitter` (defaults) | 400 / 50 |
| `FINANCIAL_REPORT` | `FinancialReportChunker` | `RecursiveCharacterTextSplitter` (defaults) | 800 / 150 |
| `LEGAL` | `LegalChunker` | Recursive with separators `["\n\n", "Section", "Article", "\n", " "]` | 1500 / 300 |
| `TABULAR` | `TabularChunker` | Recursive with separator `["\n"]` (keeps rows aligned) | 300 / 0 |
| `MARKDOWN` | `MarkdownChunker` | `MarkdownHeaderTextSplitter` (h1–h4, headers kept) + fallback recursive splitter for oversized sections | 1000 / 100 |
| `NARRATIVE` | `RecursiveChunker` | `RecursiveCharacterTextSplitter` (defaults) | 1000 / 200 |

`MarkdownChunker` first splits on headers (preserving header metadata such as `h1`–`h4`), and only falls back to the recursive splitter for sections that exceed the chunk size — keeping semantically coherent sections intact.

All sizes/overlaps are configurable via settings (`app/config.py`) and injected when `AdaptiveChunker` is constructed in `build_pipeline()`.

---

## 5. RAG Retrieval

Retrieval is implemented in `RAGPipeline.query` / `query_with_extra_context` (`app/core/pipeline.py`) on top of `FAISSVectorStore.similarity_search`.

### Standard retrieval (`/query`)

```
question
  → FAISSVectorStore.similarity_search_with_relevance_scores(query, k, filter)
  → [(Document, score), ...]
  → SourceDocument(text, score, metadata)     # one per hit
  → if generate_answer:                        # LLM grounding
        LLM.generate(question, retrieved_docs)
  → QueryResult(query, answer, sources, took_ms)
```

Key points:
- **`top_k`** controls how many chunks are retrieved (validated `1 ≤ top_k ≤ 20`).
- **`filter`** is an optional metadata filter (e.g. `{"tenant": "acme", "year": 2024}`) applied during the FAISS search — this is how multi-tenant / scoped retrieval is achieved using the metadata stamped at ingestion time.
- **Relevance scores** are returned alongside each source so callers can gauge match quality.
- **Answer generation is optional** (`generate_answer=false` returns sources only — useful for debugging or building custom prompts).

### Retrieval over an uploaded file (`/query-with-file`, `isIngest=false`)

`query_with_extra_context` runs the **same** similarity search against the persisted index, then appends the uploaded file's freshly-chunked `extra_docs` to the LLM context:

```
answer = LLM.generate(question, retrieved_docs + extra_docs)
```

The extra docs influence only the generated answer — they are **not persisted** and **not** included in the returned `sources`. This lets a user ask questions over an ad-hoc document without polluting the shared index.

---

## 6. Agentic Workflow with Human-in-the-Loop for KPI

The KPI feature is an **agentic workflow** built as a LangGraph `StateGraph` (`app/kpi/graph.py`), driven by `KPIService` (`app/kpi/service.py`) and exposed via `POST /kpi/chat` and `POST /kpi/approve`.

### Design principles

- **Decoupled from FastAPI**: graph nodes operate on `KpiState` (a `TypedDict`) and reach the outside world only through injected seams — `KpiRepository`, `BaseLLM`, `DataStorage`, `KpiRegistry`.
- **Per-user persistence & memory**: the graph is compiled with a `MemorySaver` checkpointer keyed by `thread_id = "{email}:{session_id}"`. Prior company/document context is restored from the checkpoint on each turn (chat memory).
- **Human-in-the-loop**: the `human_approval` node calls LangGraph's `interrupt()` to pause the run; the service returns `awaiting_approval` with an `interrupt_id`, and resumes later via `Command(resume=...)`.
- **Guardrails & least privilege**: a domain guardrail (finance-only) and a fail-closed authorization check run before any document is fetched or any expensive LLM call is made. SQL is SELECT-only and parameterized.

### Node pipeline

The nodes are wired in `build_kpi_graph()`:

```
START
 → finance_guardrail   ──(non-finance)──▶ END (denied)
 → resolve_company     ──(no company)───▶ END (error)
 → authorize           ──(unauthorized)─▶ END (denied, fail-closed)
 → fetch_documents
 → retrieve_document
 → parse_document
 → map_kpis
 → build_prompt
 → human_approval ★HITL★ ──(reject)─────▶ END (denied)
 → generate_kpis
 → persist
 → END
```

| # | Node | What it does | Seam used |
|---|------|--------------|-----------|
| 1 | `finance_guardrail` | LLM classifies whether the message is finance-related; fails **open** if the classifier errors so it never blocks legitimate use | `BaseLLM.complete` |
| 2 | `resolve_company` | Resolves the company from `symbol` via the DB (no LLM); reuses prior company context on follow-up turns | `KpiRepository.find_company` |
| 3 | `authorize` | Watchlist authorization check; **fail-closed** (deny unless an active mapping exists); optional admin bypass | `KpiRepository.get_user_by_email`, `is_user_authorized` |
| 4 | `fetch_documents` | Collects candidate filings for the company (ranking currently disabled — all candidates forwarded) | `KpiRepository.find_company_documents` |
| 5 | `retrieve_document` | Pulls document blobs from storage (per-company bucket, with fallback) | `DataStorage.retrieve` |
| 6 | `parse_document` | Parses each blob to text, preprocesses, concatenates (capped to a char budget downstream); drops bytes from persisted state | `get_parser().parse` |
| 7 | `map_kpis` | Maps the free-text request to KPI categories/KPIs from the allow-list | `KpiRegistry.match_categories` |
| 8 | `build_prompt` | Builds the LLM prompt: KPI allow-list block + (capped) filing text + user request | `KpiRegistry.as_prompt_block` |
| 9 | `human_approval` | **HITL** — `interrupt()` pauses awaiting a reviewer decision (skipped if `require_approval=false`) | — |
| 10 | `generate_kpis` | LLM generates the KPI report (Markdown); cleans `<think>` blocks / code fences | `BaseLLM.complete` |
| 11 | `persist` | Appends the user/assistant turn to chat history (reducer channel) | — |

`KpiState` carries channels such as `email`, `symbol`, `message`, `company`, `authorized`, `candidate_documents`, `document_text`, `requested_kpis`, `kpi_prompt`, `kpis`, `status`, and reducer channels `steps`/`messages` (appended across nodes/turns).

### Human-in-the-loop sequence

```
POST /kpi/chat (email, symbol, message)
   → KPIService.chat() → graph.invoke(inputs, thread_id)
   → runs nodes 1–8, reaches human_approval
   → interrupt() PAUSES the graph
   → response: status="awaiting_approval", pending_approval={interrupt_id, summary}

   ── reviewer decides ──

POST /kpi/approve (email, session_id, decision, feedback?)
   → KPIService.resume() → graph.invoke(Command(resume={decision, feedback}), thread_id)
   → human_approval RESUMES from the checkpoint:
        decision == "reject" → END (denied, returns feedback)
        otherwise            → generate_kpis → persist → END
   → response: status="completed", kpis=<Markdown report>
```

Because state is checkpointed by `thread_id`, the pause can span arbitrary time and multiple HTTP requests, and each `(email, session_id)` pair is an isolated conversation thread with its own memory.

### Outcome statuses (`KpiChatResponse.status`)

| Status | Meaning |
|--------|---------|
| `completed` | KPI report generated; `kpis` holds the Markdown |
| `awaiting_approval` | Paused at HITL; `pending_approval` holds the `interrupt_id` + summary |
| `denied` | Blocked by a guardrail (non-finance, unauthorized) or rejected by the reviewer |
| `error` | No company resolved or LLM generation failed; `message` explains why |

Every response also carries `steps` (a trace of nodes executed) and `took_ms` for observability.

### Assembly

`build_kpi_service()` (`app/api/dependencies.py`) wires the seams: a SQLAlchemy engine → `KpiRepository`, document `DataStorage`, the `KpiRegistry` (parsed from `docs/KPI-List.txt`), the prompt template (`docs/kpi-prompt.md`), and the configured `BaseLLM`, then compiles the graph with a `MemorySaver`. Behavior toggles come from settings: `kpi_require_approval`, `kpi_admin_bypass`, `kpi_max_document_chars`.

---

## Related files

- Visual diagrams: [`docs/architecture.drawio`](./architecture.drawio)
- KPI allow-list catalog: [`docs/KPI-List.txt`](./KPI-List.txt)
- KPI prompt template: [`docs/kpi-prompt.md`](./kpi-prompt.md)
- Database schema: [`docs/db.sql`](./db.sql)
- Agentic AI notes: [`docs/agentic-ai.md`](./agentic-ai.md)