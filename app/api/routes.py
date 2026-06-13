import asyncio
import logging
from functools import partial
from pathlib import Path

from fastapi import APIRouter, Depends, File, UploadFile

from app.api.dependencies import get_pipeline
from app.api.schemas import (
    HealthResponse,
    IngestRequest,
    IngestResponse,
    QueryRequest,
    QueryResponse,
    SourceDocumentResponse,
)
from app.core.parsers import get_parser
from app.core.pipeline import IngestDocument, RAGPipeline
from app.exceptions import EmptyFileError, ProviderUnavailableError, ValidationError

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
    pipeline: RAGPipeline = Depends(get_pipeline),
) -> IngestResponse:
    if not files:
        raise ValidationError("At least one file must be provided")

    logger.info("POST /ingest/file — %d file(s) received", len(files))

    # Read all file bytes async before entering the thread executor
    files_data: list[tuple[str, bytes, dict]] = []
    for f in files:
        filename = f.filename or "unknown"
        get_parser(filename)  # raises UnsupportedFileTypeError early, before reading
        content = await f.read()
        if not content:
            raise EmptyFileError(filename)
        ext = Path(filename).suffix.lower().lstrip(".")
        metadata = {"source_file": filename, "file_type": ext, "content_type": f.content_type or ""}
        files_data.append((filename, content, metadata))

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


@router.get("/health", response_model=HealthResponse)
async def health(
    pipeline: RAGPipeline = Depends(get_pipeline),
) -> HealthResponse:
    return HealthResponse(
        status="ok",
        index_loaded=pipeline._vector_store.is_loaded(),
        vector_count=pipeline._vector_store.vector_count(),
    )
