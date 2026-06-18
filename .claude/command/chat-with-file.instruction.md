## Goal

Add a new endpoint, **`POST /api/v1/query-with-file`**, sitting alongside the existing
`POST /api/v1/query` (`app/api/routes.py:101`). It accepts a query plus an uploaded file in the
same request. Depending on a request flag, the file is either:

- **persisted** into the vector store (same path as `/api/v1/ingest/file`), or
- used **ephemerally** as extra context for this one answer, alongside whatever the existing
  `/query` retrieval pipeline already returns for the typed query — without touching the vector DB.

In both cases the endpoint returns the same shape as `QueryResponse` so existing clients of
`/query` don't need a different response parser.

---

## Endpoint contract

### `POST /api/v1/query-with-file`

**Content-Type:** `multipart/form-data` (it must accept a file plus form fields — `UploadFile` +
`Form(...)`, the same FastAPI pattern already used by `ingest_file` in `routes.py:53`).

| Field | Type | Required | Description |
|---|---|---|---|
| `query` | `str` | yes | Question to answer (same semantics as `QueryRequest.query`). |
| `file` | `UploadFile` | yes | The uploaded document. Allowed extensions: `.xlsx`, `.docx`, `.txt`, `.pdf`, `.csv`, `.xml`. |
| `top_k` | `int` | no, default `4` | Same as `QueryRequest.top_k` (range 1–20). |
| `generate_answer` | `bool` | no, default `true` | Same as `QueryRequest.generate_answer`. |
| `filter` | `str` (JSON-encoded dict) | no | Same as `QueryRequest.filter`; multipart forms can't carry nested JSON natively, so accept it as a JSON string and parse server-side. |
| `isIngest` | `bool` | no, default `false` | See behavior below. |

**Validation (mirror `ingest_file`'s existing checks):**
- Reject unsupported extensions before reading the file body (`get_parser(filename)` already
  raises `UnsupportedFileTypeError` — extend the parser registry first, see below).
- Reject empty file content (`EmptyFileError`, already raised by each parser).
- Reject empty `query` (`ValidationError`, mirrors `QueryRequest.query` min_length=1).

**Response `200`** — identical shape to the existing `QueryResponse`:
```json
{
  "query": "What is the total invoice amount?",
  "answer": "The total invoice amount is $4,820.00.",
  "sources": [
    { "text": "matched chunk text", "score": 0.83, "metadata": { "source": "handbook.pdf", "doc_id": "doc-001" } }
  ],
  "took_ms": 540
}
```

**Errors** — reuse the existing error contract (`app/exceptions.py`): `400` for validation /
unsupported file type / empty file, `503` if the embedding/LLM provider is unreachable, `500`
for unexpected failures.

---

## Behavior

### 1. Parsing (always happens, regardless of `isIngest`)

Reuse `app.core.parsers.get_parser(filename)` (`app/core/parsers.py:144`) to dispatch by
extension and extract plain text from the uploaded file — same as `ingest_file` already does.

- `.xlsx` → `ExcelParser` (existing)
- `.docx` → `DocxParser` (existing)
- `.txt` → `TextParser` (existing)
- `.pdf` → `PDFParser` (existing)
- `.csv` → `CsvParser` (existing)
- `.xml` → **new** `XmlParser` (does not exist yet — add it to `_REGISTRY` in
  `app/core/parsers.py`). Implement with `xml.etree.ElementTree`, walking the tree and emitting
  a flattened `tag: text` representation (or adapt to whatever element shape the target XML
  documents use). Follow the existing parser pattern: raise `FileParseError` on malformed XML,
  `EmptyFileError` if there's no extractable text.

After parsing, run the extracted text through the existing chunker
(`app.core.chunking`, via `BaseChunker.split`) exactly as `RAGPipeline.ingest` does internally —
do **not** reimplement chunking in the route handler.

### 2. `isIngest = true` — persist to the vector DB

Same code path as today's `POST /api/v1/ingest/file` (`routes.py:53`):
1. Build an `IngestDocument` from the parsed text + file metadata (`source_file`, `file_type`,
   `content_type`), matching what `ingest_file` already does.
2. Call `pipeline.ingest([doc])` — this chunks, embeds, stores, and persists the FAISS index.
3. **Then** run the normal query flow: call `pipeline.query(query, top_k, generate_answer,
   filter)` so the just-ingested content is immediately retrievable for this answer too (the
   index is updated synchronously before the similarity search runs).
4. Return the `QueryResult` mapped into `QueryResponse`, same as `/query` does today
   (`routes.py:125`).

### 3. `isIngest = false` — ephemeral context, no DB write

The file is **not** added to the vector store. Instead:
1. Run `pipeline.query(query, top_k, generate_answer=False, filter)` to get the normal
   vector-store `sources` for the typed query (reuse existing retrieval — don't duplicate
   similarity-search logic in the route).
2. Take the retrieved `Document`s from that search **plus** the chunked `Document`s produced
   from the uploaded file in step 1 above, and pass the combined list into the LLM:
   `BaseLLM.generate(question, context: list[Document])` (`app/core/interfaces.py`,
   implemented by `OpenAIChatLLM` per `rag_fastapi_build_prompt.md`).
3. Return a `QueryResponse` whose `sources` reflect only what came from the vector store search
   (the uploaded file's chunks are answer-context only, not persisted, so they're not
   "retrieved sources" in the same sense — but include them in `sources` if you want full
   transparency about what the LLM actually saw; pick one and document it in the docstring).
4. If `generate_answer` is `false` in this branch, there's nothing to generate — return early
   with `answer: null` and just the vector-store `sources`, same as `/query` does today.

> **Pipeline-level change required:** `RAGPipeline.query` (`app/core/pipeline.py:90`) currently
> only knows how to search the vector store and generate from those results. Add a method (e.g.
> `RAGPipeline.query_with_extra_context(question, k, generate_answer, filter, extra_docs:
> list[Document])`) that performs the same retrieval as `query()` but unions `extra_docs` into
> the context passed to `self._llm.generate(...)`. Keep `query()` itself unchanged so `/query`'s
> behavior and tests are unaffected.

---

## Files to touch

```
app/
  core/
    parsers.py        # add XmlParser + ".xml" entry in _REGISTRY
    pipeline.py        # add RAGPipeline.query_with_extra_context(...)
  api/
    schemas.py          # add QueryWithFileResponse if it diverges from QueryResponse, else reuse it
    routes.py           # add POST /query-with-file handler
tests/
  test_parsers.py       # XmlParser unit tests (valid xml, malformed xml, empty xml)
  test_pipeline.py       # query_with_extra_context unit tests (mocked vector store + llm)
  test_api.py            # /query-with-file: isIngest=true and isIngest=false, unsupported ext, empty file, empty query
```

---

## Constraints (same as the original build prompt)

- No RAG/parsing/chunking logic inline in `routes.py` — the handler only validates input,
  delegates to `RAGPipeline`/parsers, and shapes the response.
- Don't duplicate the ingest logic from `ingest_file` or the query logic from `query` — call the
  same pipeline methods/parsers they already use.
- Blocking work (parsing, chunking, embedding, similarity search, LLM calls) must run via
  `loop.run_in_executor`, matching the pattern already used in every existing handler in
  `routes.py`.
- Update `README.md`'s endpoint list and env/curl examples once implemented.
