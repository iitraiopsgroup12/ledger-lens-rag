# Prompt: Build the `/kpi` Agentic AI Workflow (LangGraph) for LedgerLens

> Paste everything below the line into an AI coding assistant, or use it as the
> implementation spec. It assumes the model can read the existing repository and
> keeps to the conventions already used in `app/` and `nse_data_storage/`.

---

## Role

You are a senior Python/FastAPI + LangChain/LangGraph engineer extending the
**LedgerLens RAG** service. Add a new **`/kpi` conversational endpoint** backed by
an **agentic workflow** that, given a natural-language request and a user's email,
identifies the company, enforces an access-scope guardrail, fetches and parses the
company's filing, and generates a **structured KPI JSON** using the project's
existing LLM stack. The workflow is **stateful per user** (chat memory keyed by
email) and supports **human-in-the-loop (HITL) approval** before the final KPI
generation.

Do **not** rewrite the existing RAG pipeline. Reuse it (parsers, LLM providers,
config, DI seam) and add the KPI agent as a new layer.

## Source-of-truth inputs (read these first)

- **`docs/db.sql`** — PostgreSQL schema (local, `localhost:5432`, owner `postgres`).
  Tables the workflow uses:
  - `users(id, email, password_hash, full_name, role, created_at)` — `role` ∈
    {`analyst`,`admin`}. Lookup by `email`.
  - `companies(id, symbol, company_name, sector, is_active, created_at)` — resolve
    by `symbol` or `company_name`.
  - `watchlists(id, user_id→users.id, company_id→companies.id, frequency,
    last_checked, status)` — the **authorization mapping**: a user may analyze a
    company only if a `watchlists` row links their `user_id` to that `company_id`
    (prefer `status='active'`).
  - `documents(id, company_id→companies.id, document_type, document_title,
    report_year, s3_key, source, upload_date, processing_status)` — generic docs;
    **`s3_key` is the storage pointer**; `document_type` ∈
    {`annual_report`,`announcement`,`other`}; `processing_status` ∈
    {`pending`,`processing`,`completed`,`failed`}.
  - `annual_reports(id, company_id, symbol, company_name, from_yr, to_yr,
    submission_type, broadcast_dttm, dissemination_date_time, file_name,
    att_file_size, …)` — **`file_name` is the storage pointer** (UNIQUE).
  - `financial_results(id, seq_number, symbol, company_name, isin, audited,
    consolidated, period, relating_to, financial_year, from_date, to_date, format,
    ind_as, industry, result_description, result_detailed_data_link, xbrl, …)` —
    pointers are **`result_detailed_data_link`** / **`xbrl`** (no `s3_key`).
  - Read **all** columns of `documents`, `annual_reports`, `financial_results` —
    the user asks for KPIs in natural language, so fields like `report_year`,
    `financial_year`, `period`, `consolidated`, `audited`, `from_yr/to_yr` are how
    you pick the right filing.
- **`docs/kpi-prompt.md`** — the **KPI extraction prompt template** (system rules +
  extraction steps + strict JSON output contract). Use it verbatim as the system
  prompt for the final generation step; inject the registries/context into it.
- **`docs/KPI-List.txt`** — the catalog of ~500 KPIs grouped into 34 **Categories**
  (Revenue & Growth, Profitability, Return Ratios, Liquidity, Solvency, …). Use it
  as the **KPI Registry / allow-list**: map the user's NL request to one or more
  categories/KPIs from this file, and never invent KPIs outside it.
- **`nse_data_storage/`** — storage package (note: the package is `nse_data_storage`,
  not `nsc_*`). `DataStorage.retrieve(storage_id: str, bucket: str | None) -> bytes`
  returns the raw file. `LocalFileStorage` is the default implementation. The agent
  fetches documents through this interface only.

## What already exists to reuse (do not duplicate)

- `app/api/routes.py` — endpoint conventions: `async` handlers, CPU/IO work in
  `loop.run_in_executor(...)`, provider/connection errors remapped to
  `ProviderUnavailableError`. Multipart upload pattern in `POST /ingest/file` and
  `POST /query-with-file` (read `UploadFile` bytes before the executor; `get_parser`
  validates type early).
- `app/core/parsers.py` — `get_parser(filename)` for `.xlsx/.docx/.txt/.pdf/.csv/.xml`;
  raises `UnsupportedFileTypeError`. Use this to parse both the fetched filing and
  any optional user-uploaded file.
- `app/core/llm.py` — provider LLM wrappers (`OpenAIChatLLM`, `AnthropicChatLLM`,
  `GoogleChatLLM`, `HuggingFaceChatLLM`) over LangChain chat models, sharing a
  financial-analyst persona. Use the configured provider for KPI generation.
- `app/api/dependencies.py` — `build_pipeline()` is the single DI seam
  (`@lru_cache`). Add KPI wiring here.
- `app/config.py` — `Settings` (pydantic-settings); `LLM_PROVIDER` switch.
- `app/exceptions.py` — custom exceptions + handlers.

## Endpoint

Add to `app/api/routes.py` (prefix stays `/api/v1`):

### `POST /api/v1/kpi/chat`

Multipart form (mirrors `/query-with-file`), fields:
- `email: str` (required) — identifies the user; the **session key** for chat memory
  and HITL state.
- `message: str` (required, min_length=1) — natural-language KPI request, e.g.
  *"Show me TCS profitability and return ratios for FY2024."*
- `file: UploadFile | None` (optional) — extra document to include as additional
  context during KPI generation (parsed with `get_parser`, **not** persisted to the
  vector store unless explicitly requested).
- `session_id: str | None` (optional) — to run multiple parallel threads for one
  email; default to a stable per-email thread if omitted.

Response (`KpiChatResponse`):
- `session_id: str`
- `status: str` — one of `completed`, `awaiting_approval`, `denied`, `error`.
- `company: { symbol, company_name } | None` — resolved company.
- `kpis: dict | null` — the final KPI JSON (shape defined by `docs/kpi-prompt.md`)
  when `status=completed`.
- `message: str | None` — assistant text (e.g. the guardrail denial, or an approval
  prompt describing what will be analyzed).
- `pending_approval: { interrupt_id, summary } | None` — present when
  `status=awaiting_approval` (see HITL).
- `steps: list[KpiStepResponse]` — transparent trace `{node, summary}`.
- `took_ms: float`

### `POST /api/v1/kpi/approve`

Resumes a paused workflow after human review.
- `email: str`, `session_id: str`, `interrupt_id: str`
- `decision: "approve" | "reject"`
- `feedback: str | None` — optional reviewer note / correction (e.g. "use
  consolidated FY2023 instead").
Returns the same `KpiChatResponse` shape (continues to `completed`/`denied`).

> Both endpoints follow the existing async + `run_in_executor` + error-remap pattern
> and inject the service via `Depends(get_kpi_service)`.

## Agentic workflow (LangGraph state machine)

Implement with **LangGraph** (`StateGraph`) so you get first-class **persistence**
(per-email memory) and **interrupts** (HITL). Use a checkpointer keyed by
`thread_id = f"{email}:{session_id}"`. Prefer a Postgres checkpointer against the
same DB (`langgraph.checkpoint.postgres`) so history survives restarts; a
memory/SQLite checkpointer is acceptable for the first cut behind a setting.

### Graph state (`KpiState`, a `TypedDict`/dataclass)

```
email, session_id, message
company: {id, symbol, company_name} | None
authorized: bool
candidate_documents: list[DocumentRef]      # from documents/annual_reports/financial_results
selected_document: DocumentRef | None
storage_id: str | None                      # s3_key | file_name | (link/xbrl)
document_text: str | None                   # parsed filing
user_file_text: str | None                  # optional uploaded file, parsed
requested_kpis: list[str]                    # mapped to KPI-List.txt categories/ids
kpi_prompt: str | None                       # final prompt built from kpi-prompt.md
kpis: dict | None                            # final JSON
status, denial_reason, steps, messages       # messages = running chat history
```

### Nodes (sequence)

1. **`resolve_company`** — Analyze `message` to extract a company name/symbol
   (LLM-assisted extraction + a DB lookup against `companies` by `symbol` /
   `company_name`, fuzzy/ILIKE match). If no company can be identified, ask a
   clarifying question (return `status=awaiting_approval`-style clarification or a
   plain reply) rather than guessing.
2. **`authorize` (GUARDRAIL)** — Look up the `users` row by `email`, then check
   `watchlists` for a row linking that `user_id` to the resolved `company_id`
   (prefer `status='active'`). Admins (`users.role='admin'`) may be allowed to
   bypass — confirm desired policy; default: **no bypass**, watchlist required.
   - If **not** linked: **stop the graph** and return exactly:
     `"The Analysis of this company is not in your scope"`,
     `status=denied`. No documents are fetched, no LLM call is made.
3. **`fetch_documents`** — Query `documents`, `annual_reports`, and
   `financial_results` for `company_id` (and matching `symbol`). Inspect **all**
   fields to rank candidates by what the user asked (year/period/consolidated/
   audited/document_type). Normalize each into a `DocumentRef` carrying the storage
   pointer (`documents.s3_key` | `annual_reports.file_name` |
   `financial_results.result_detailed_data_link`/`xbrl`) and `source_table`. Pick
   the best `selected_document`; if multiple plausible filings exist, surface the
   choice at the HITL step.
4. **`retrieve_document`** — If `storage_id` (the s3_key/pointer) is present, fetch
   bytes via `nse_data_storage` `DataStorage.retrieve(storage_id, bucket)` (default
   `LocalFileStorage`). Handle `FileNotFoundError` gracefully (report, don't crash).
   If the pointer is missing/empty, record that and continue with whatever context
   is available (e.g. the optional user file).
5. **`parse_document`** — Parse the fetched bytes with `get_parser(filename)` and
   preprocess to clean text (strip boilerplate, normalize whitespace). Also parse
   the optional uploaded `file` into `user_file_text`.
6. **`map_kpis`** — Map the NL request to concrete KPIs/categories from
   `docs/KPI-List.txt` (the allow-list). Store `requested_kpis`. Never include KPIs
   outside the list.
7. **`build_prompt`** — Construct the final prompt: system = the template from
   `docs/kpi-prompt.md` (verbatim rules + strict JSON contract); inject the
   requested KPI registry subset, the parsed filing text, and any `user_file_text`
   as the context. Keep the strict "JSON only, no prose, no code fences" output
   contract.
8. **`human_approval` (HITL — `interrupt`)** — Before the (potentially costly /
   high-stakes) generation, **pause** via LangGraph `interrupt(...)`, surfacing a
   `summary`: resolved company, selected document (table + year/period), and the
   KPI set to be computed. The `/kpi/approve` endpoint resumes with
   approve/reject(+feedback). On reject, either end (`status=denied`) or loop back
   to `fetch_documents`/`map_kpis` using the feedback. Make HITL toggleable via a
   setting (`KPI_REQUIRE_APPROVAL`, default `true`).
9. **`generate_kpis`** — Call the configured provider LLM from `app/core/llm.py`
   with the built prompt. Parse/validate the returned JSON against the
   `docs/kpi-prompt.md` output schema; coerce missing values to `null`; never
   fabricate numbers. Store `kpis`, set `status=completed`.
10. **`persist`** — Append the turn (user message + assistant result) to the
    thread's message history via the checkpointer so the next call with the same
    `email`/`session_id` has context.

> The graph must be **decoupled from FastAPI** (no `fastapi` imports inside the
> graph/service module). The route handler adapts HTTP ↔ graph invoke/resume.

## Deliverables (files)

Mirror existing house style: type hints, `logging.getLogger(__name__)`, dataclasses
for results, ABCs at seams, terse docstrings.

1. `app/kpi/__init__.py`
2. `app/kpi/service.py` — **`KPIService`**: builds/holds the compiled LangGraph,
   exposes `chat(email, message, file_bytes?, session_id?) -> KpiResult` and
   `resume(email, session_id, interrupt_id, decision, feedback?) -> KpiResult`.
3. `app/kpi/graph.py` — the `StateGraph`, `KpiState`, nodes, edges, checkpointer.
4. `app/kpi/nodes.py` — node functions (or co-locate in `graph.py` if small).
5. `app/kpi/registry.py` — loads `docs/KPI-List.txt` into structured
   categories/KPIs (parsed once, cached) and exposes lookup/allow-list helpers; and
   loads `docs/kpi-prompt.md` as the system template.
6. `app/core/kpi_repository.py` — **read-only, parameterized** repository for
   `users`, `companies`, `watchlists`, `documents`, `annual_reports`,
   `financial_results`. The only place SQL is written. Methods:
   `get_user_by_email`, `find_company(symbol_or_name)`,
   `is_user_authorized(user_id, company_id)`,
   `find_company_documents(company_id, symbol, filters…) -> list[DocumentRef]`.
   **No LLM-authored SQL**; bind all values; whitelist columns; statement timeout.
7. `app/kpi/storage_provider.py` *(or reuse a shared one)* — `build_storage()`
   returning a `DataStorage` (default `LocalFileStorage`), DI-seam + `@lru_cache`.
8. Wire-up: routes in `app/api/routes.py`, schemas in `app/api/schemas.py`,
   `get_kpi_service()` in `app/api/dependencies.py`, settings in `app/config.py`.
9. Tests in `tests/` (mock LLM, repository, storage, checkpointer — no live DB).
10. README section documenting `/kpi/chat` + `/kpi/approve` and new settings.

## Config additions (`app/config.py` + `.env.example`)

- `database_url: str = Field("postgresql+psycopg://postgres:postgres@localhost:5432/ledgerlens", alias="DATABASE_URL")`
- `kpi_require_approval: bool = Field(True, alias="KPI_REQUIRE_APPROVAL")`
- `kpi_checkpointer: str = Field("postgres", alias="KPI_CHECKPOINTER")` — `postgres` | `memory`
- `kpi_list_path: str = Field("docs/KPI-List.txt", alias="KPI_LIST_PATH")`
- `kpi_prompt_path: str = Field("docs/kpi-prompt.md", alias="KPI_PROMPT_PATH")`
- `storage_dir: str = Field("storage", alias="STORAGE_DIR")`
- `db_statement_timeout_ms: int = Field(5000, alias="DB_STATEMENT_TIMEOUT_MS")`

(Keep secrets in `.env`; use a placeholder password in `.env.example`.)

## Guardrails & correctness rules

- **Scope guardrail is mandatory and fail-closed.** If `authorize` cannot confirm a
  watchlist mapping for the user→company, return
  `"The Analysis of this company is not in your scope"` and stop *before* any
  document fetch or LLM call.
- **DB access only via `kpi_repository`** — read-only, parameterized. The agent/LLM
  supplies structured arguments (symbol, year, type), never SQL text. Add a test
  that injection-y input is treated as a literal and matches nothing.
- **Storage access only via `nse_data_storage.DataStorage`** — never touch the
  filesystem directly from nodes.
- **KPI allow-list:** only KPIs present in `docs/KPI-List.txt`. **No hallucinated
  values** — honor every rule in `docs/kpi-prompt.md` (numeric-only, no currency
  symbols/commas, `null` when unavailable, JSON-only output).
- **Per-email isolation:** chat history and HITL/interrupt state are scoped to
  `thread_id = email[:session_id]`; one user's session never leaks into another's.
- **Honest failures:** missing storage pointer, `FileNotFoundError`, unsupported
  file type, or unparseable LLM JSON each produce a clean `status=error` with a
  readable message — never a 500 or a crashed graph.

## Acceptance criteria

- [ ] `POST /api/v1/kpi/chat` with `email` + NL `message` resolves the company,
      enforces the watchlist guardrail, fetches+parses the company filing via the
      DB pointer and `nse_data_storage`, and returns KPI JSON matching
      `docs/kpi-prompt.md`.
- [ ] A user **not** linked to the company in `watchlists` gets exactly
      `"The Analysis of this company is not in your scope"`, `status=denied`, with
      **no** document fetch and **no** LLM call (assert via mocks).
- [ ] With `KPI_REQUIRE_APPROVAL=true`, the first call returns
      `status=awaiting_approval` + `pending_approval`; `POST /kpi/approve` with
      `approve` resumes to `completed`; `reject` ends/loops per `feedback`.
- [ ] Chat memory persists per `email`/`session_id`: a follow-up message
      ("now add liquidity ratios") reuses prior company/document context.
- [ ] Optional uploaded `file` is parsed and included as extra context without being
      persisted to the vector store.
- [ ] KPIs are constrained to `docs/KPI-List.txt`; output validates against the
      `docs/kpi-prompt.md` schema; unavailable metrics are `null`.
- [ ] Provider switch (`LLM_PROVIDER=anthropic|openai|google|huggingface`) routes
      KPI generation through `app/core/llm.py` via the existing DI seam.
- [ ] Existing endpoints/tests stay green; new tests cover: guardrail denial,
      happy path (mocked LLM/repo/storage), HITL pause+resume, and bad-JSON repair.

## Worked example (target behavior)

Request:
```bash
curl -X POST http://localhost:8080/api/v1/kpi/chat \
  -F "email=analyst@firm.com" \
  -F "message=Give me TCS profitability and return ratios for FY2024"
```
Trace:
1. `resolve_company` → `companies` match → `{id, symbol: "TCS", company_name: "Tata Consultancy Services"}`
2. `authorize` → `users(email)` → `watchlists(user_id, company_id, status='active')` found → authorized
3. `fetch_documents` → `annual_reports`/`documents` for FY2024 → `DocumentRef{storage_id, source_table:"annual_reports"}`
4. `retrieve_document` → `DataStorage.retrieve(storage_id)` → bytes
5. `parse_document` → text via `get_parser(...)`
6. `map_kpis` → Categories "2. Profitability" + "4. Return Ratios" from `KPI-List.txt`
7. `build_prompt` → system = `kpi-prompt.md`, context = parsed filing
8. `human_approval` → `status=awaiting_approval`, summary: "TCS · FY2024 annual report · 23 KPIs (Profitability, Return Ratios)"
   → client calls `/kpi/approve {decision:"approve"}`
9. `generate_kpis` → LLM (provider from config) → validated KPI JSON
10. `persist` → turn saved to thread `analyst@firm.com:default`

Denied example:
```bash
curl -X POST http://localhost:8080/api/v1/kpi/chat \
  -F "email=analyst@firm.com" -F "message=KPIs for Reliance Industries"
# → {"status":"denied","message":"The Analysis of this company is not in your scope"}
```

---

## Notes for the implementer

- **Why LangGraph over a plain LangChain AgentExecutor:** the two hard requirements
  here — *per-session memory keyed by email* and *human-in-the-loop approval* — map
  directly onto LangGraph's checkpointer (`thread_id`) and `interrupt()`/resume.
  A ReAct AgentExecutor can call tools but doesn't natively persist/replay or pause
  for approval. Reuse the existing LLM objects from `app/core/llm.py` as the graph's
  model(s); don't fork the persona/prompt stack.
- **Pointer is not uniform:** normalize `documents.s3_key`,
  `annual_reports.file_name`, and `financial_results.result_detailed_data_link`/`xbrl`
  into one `DocumentRef.storage_id` in the repository so `retrieve_document` stays
  table-agnostic. Confirm whether `bucket` is needed and how it's derived (e.g.
  company `symbol`), and document the decision.
- **`docs/KPI-List.txt` is plain text today** (already markdown-ish with `##`
  category headers and numbered KPIs). Parse category headers (`## N. Name`) and the
  numbered lines into `{category: [kpi, …]}`. If it is later renamed to `.md`, keep
  `KPI_LIST_PATH` configurable.
- **`docs/kpi-prompt.md` mandates JSON-only output** (no markdown/code fences). When
  generating, request raw JSON and validate; if the model wraps it in fences, strip
  and re-parse before failing. Surface unrecoverable parse failures as
  `status=error`.
- **DB writes:** the workflow itself is read-only against the business tables; the
  only writes are chat/interrupt state handled by the LangGraph checkpointer (its
  own tables). Optionally log a `update_logs` row (`update_type='rag_process'`) for
  observability — confirm before adding writes to business tables.
