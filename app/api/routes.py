import asyncio
import json
import logging
from functools import partial
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.api.dependencies import get_kpi_service, get_pipeline
from app.api.schemas import (
    HealthResponse,
    IngestRequest,
    IngestResponse,
    KpiApproveRequest,
    KpiChatResponse,
    QueryRequest,
    QueryResponse,
    SourceDocumentResponse,
)
from app.core.parsers import get_parser
from app.core.pipeline import IngestDocument, RAGPipeline
from app.exceptions import (
    EmptyFileError,
    KpiWorkflowError,
    ProviderUnavailableError,
    ValidationError,
)
from app.kpi.service import KPIService, KpiResult

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1")


@router.post("/ingest", response_model=IngestResponse)
async def ingest(
    body: IngestRequest,
    pipeline: RAGPipeline = Depends(get_pipeline),
) -> IngestResponse:
    logger.info("POST /ingest — %d document(s) received", len(body.documents))
    docs = [
        IngestDocument(text=d.text, id=d.id, metadata=d.metadata)
        for d in body.documents
    ]
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(None, partial(pipeline.ingest, docs))
    except Exception as exc:
        if "openai" in str(exc).lower() or "connection" in str(exc).lower():
            raise ProviderUnavailableError() from exc
        raise

    return IngestResponse(
        status="success",
        ingested_documents=result.ingested_documents,
        chunks_created=result.chunks_created,
        vector_ids=result.vector_ids,
        took_ms=result.took_ms,
        doc_types=result.doc_types,
    )


@router.post("/ingest/file", response_model=IngestResponse)
async def ingest_file(
    files: list[UploadFile] = File(..., description="One or more files to ingest"),
    metadata: str | None = Form(
        None,
        description="Optional key/value pairs, JSON-encoded, stored as metadata on every "
        "chunk for filtered retrieval (e.g. {\"tenant\": \"acme\", \"year\": 2024})",
    ),
    pipeline: RAGPipeline = Depends(get_pipeline),
) -> IngestResponse:
    if not files:
        raise ValidationError("At least one file must be provided")

    user_metadata: dict = {}
    if metadata:
        try:
            user_metadata = json.loads(metadata)
        except json.JSONDecodeError as exc:
            raise ValidationError("metadata must be valid JSON") from exc
        if not isinstance(user_metadata, dict):
            raise ValidationError("metadata must be a JSON object of key/value pairs")

    logger.info(
        "POST /ingest/file — %d file(s) received, %d metadata key(s)",
        len(files),
        len(user_metadata),
    )

    # Read all file bytes async before entering the thread executor
    files_data: list[tuple[str, bytes, dict]] = []
    for f in files:
        filename = f.filename or "unknown"
        get_parser(filename)  # raises UnsupportedFileTypeError early, before reading
        content = await f.read()
        if not content:
            raise EmptyFileError(filename)
        ext = Path(filename).suffix.lower().lstrip(".")
        # User-supplied metadata first, then file-derived keys so source provenance
        # (source_file/file_type/content_type) always wins on conflicts.
        meta = {
            **user_metadata,
            "source_file": filename,
            "file_type": ext,
            "content_type": f.content_type or "",
        }
        files_data.append((filename, content, meta))

    def _parse_and_ingest() -> object:
        docs = []
        for filename, data, meta in files_data:
            parser = get_parser(filename)
            text = parser.parse(data, filename)
            docs.append(IngestDocument(text=text, metadata=meta))
        return pipeline.ingest(docs)

    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(None, _parse_and_ingest)
    except Exception as exc:
        if "openai" in str(exc).lower() or "connection" in str(exc).lower():
            raise ProviderUnavailableError() from exc
        raise

    return IngestResponse(
        status="success",
        ingested_documents=result.ingested_documents,
        chunks_created=result.chunks_created,
        vector_ids=result.vector_ids,
        took_ms=result.took_ms,
        doc_types=result.doc_types,
    )


@router.post("/query", response_model=QueryResponse)
async def query(
    body: QueryRequest,
    pipeline: RAGPipeline = Depends(get_pipeline),
) -> QueryResponse:
    logger.info("POST /query — %r top_k=%d", body.query, body.top_k)

    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(
            None,
            partial(
                pipeline.query,
                body.query,
                body.top_k,
                body.generate_answer,
                body.filter,
            ),
        )
    except Exception as exc:
        if "openai" in str(exc).lower() or "connection" in str(exc).lower():
            raise ProviderUnavailableError() from exc
        raise

    return QueryResponse(
        query=result.query,
        answer=result.answer,
        sources=[
            SourceDocumentResponse(
                text=s.text, score=s.score, metadata=s.metadata
            )
            for s in result.sources
        ],
        took_ms=result.took_ms,
    )


@router.post("/query-with-file", response_model=QueryResponse)
async def query_with_file(
    query: str = Form(..., min_length=1, description="Question to answer"),
    file: UploadFile = File(..., description="Document to parse: .xlsx, .docx, .txt, .pdf, .csv, .xml"),
    top_k: int = Form(4, ge=1, le=20),
    generate_answer: bool = Form(True),
    filter: str | None = Form(None, description="Optional metadata filter, JSON-encoded"),
    isIngest: bool = Form(False, description="Persist the file into the vector store before answering"),
    pipeline: RAGPipeline = Depends(get_pipeline),
) -> QueryResponse:
    filename = file.filename or "unknown"
    get_parser(filename)  # raises UnsupportedFileTypeError early, before reading
    content = await file.read()
    if not content:
        raise EmptyFileError(filename)

    parsed_filter: dict | None = None
    if filter:
        try:
            parsed_filter = json.loads(filter)
        except json.JSONDecodeError as exc:
            raise ValidationError("filter must be valid JSON") from exc

    ext = Path(filename).suffix.lower().lstrip(".")
    metadata = {"source_file": filename, "file_type": ext, "content_type": file.content_type or ""}

    logger.info(
        "POST /query-with-file — file=%s isIngest=%s top_k=%d", filename, isIngest, top_k
    )

    def _run() -> object:
        parser = get_parser(filename)
        text = parser.parse(content, filename)

        if isIngest:
            doc = IngestDocument(text=text, metadata=metadata)
            pipeline.ingest([doc])
            return pipeline.query(query, top_k, generate_answer, parsed_filter)

        extra_docs = pipeline._chunker.split(text, metadata)
        return pipeline.query_with_extra_context(
            query, top_k, generate_answer, parsed_filter, extra_docs
        )

    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(None, _run)
    except Exception as exc:
        if "openai" in str(exc).lower() or "connection" in str(exc).lower():
            raise ProviderUnavailableError() from exc
        raise

    return QueryResponse(
        query=result.query,
        answer=result.answer,
        sources=[
            SourceDocumentResponse(text=s.text, score=s.score, metadata=s.metadata)
            for s in result.sources
        ],
        took_ms=result.took_ms,
    )


def _kpi_response(result: KpiResult) -> KpiChatResponse:
    return KpiChatResponse(
        session_id=result.session_id,
        status=result.status,
        company=result.company,
        kpis=result.kpis,
        message=result.message,
        pending_approval=result.pending_approval,
        steps=result.steps,
        took_ms=result.took_ms,
    )


@router.post("/kpi/chat", response_model=KpiChatResponse)
async def kpi_chat(
    email: str = Form(..., min_length=1, description="User email — chat-memory session key"),
    symbol: str = Form(..., min_length=1, description="Company stock symbol to analyze"),
    message: str = Form(..., min_length=1, description="Natural-language KPI request"),
    session_id: str | None = Form(None, description="Optional parallel thread for this email"),
    service: KPIService = Depends(get_kpi_service),
) -> KpiChatResponse:
    logger.info("POST /kpi/chat — email=%s symbol=%s session=%s", email, symbol, session_id)

    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(
            None,
            partial(service.chat, email, symbol, message, session_id=session_id),
        )
    except Exception as exc:
        if "openai" in str(exc).lower() or "connection" in str(exc).lower():
            raise ProviderUnavailableError() from exc
        raise KpiWorkflowError(str(exc)) from exc

    return _kpi_response(result)


@router.post("/kpi/approve", response_model=KpiChatResponse)
async def kpi_approve(
    body: KpiApproveRequest,
    service: KPIService = Depends(get_kpi_service),
) -> KpiChatResponse:
    logger.info(
        "POST /kpi/approve — email=%s session=%s decision=%s",
        body.email,
        body.session_id,
        body.decision,
    )

    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(
            None,
            partial(
                service.resume,
                body.email,
                body.session_id,
                body.interrupt_id or "",
                body.decision,
                body.feedback,
            ),
        )
    except Exception as exc:
        if "openai" in str(exc).lower() or "connection" in str(exc).lower():
            raise ProviderUnavailableError() from exc
        raise KpiWorkflowError(str(exc)) from exc

    return _kpi_response(result)


@router.get("/health", response_model=HealthResponse)
async def health(
    pipeline: RAGPipeline = Depends(get_pipeline),
) -> HealthResponse:
    return HealthResponse(
        status="ok",
        index_loaded=pipeline._vector_store.is_loaded(),
        vector_count=pipeline._vector_store.vector_count(),
    )
