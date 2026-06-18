import logging
import time
from dataclasses import dataclass, field

from langchain_core.documents import Document

from app.core.interfaces import BaseChunker, BaseLLM, BaseVectorStore

logger = logging.getLogger(__name__)


@dataclass
class IngestDocument:
    text: str
    id: str | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class SourceDocument:
    text: str
    score: float
    metadata: dict


@dataclass
class IngestResult:
    ingested_documents: int
    chunks_created: int
    vector_ids: list[str]
    took_ms: float
    doc_types: dict[str, str] = field(default_factory=dict)


@dataclass
class QueryResult:
    query: str
    answer: str | None
    sources: list[SourceDocument]
    took_ms: float


class RAGPipeline:
    """Orchestrates chunking, embedding, storage, retrieval, and generation."""

    def __init__(
        self,
        chunker: BaseChunker,
        vector_store: BaseVectorStore,
        llm: BaseLLM,
    ) -> None:
        self._chunker = chunker
        self._vector_store = vector_store
        self._llm = llm

    def ingest(self, documents: list[IngestDocument]) -> IngestResult:
        start = time.monotonic()
        all_chunks: list[Document] = []
        doc_types: dict[str, str] = {}

        for doc in documents:
            meta = dict(doc.metadata)
            if doc.id:
                meta["doc_id"] = doc.id
            chunks = self._chunker.split(doc.text, meta)
            all_chunks.extend(chunks)
            if chunks and "doc_type" in chunks[0].metadata:
                key = doc.id or meta.get("source_file", f"doc_{len(doc_types)}")
                doc_types[key] = chunks[0].metadata["doc_type"]
            logger.info("Document %s split into %d chunks", doc.id, len(chunks))

        vector_ids = self._vector_store.add_documents(all_chunks)
        self._vector_store.persist()

        took_ms = (time.monotonic() - start) * 1000
        logger.info(
            "Ingested %d docs → %d chunks in %.0f ms",
            len(documents),
            len(all_chunks),
            took_ms,
        )
        return IngestResult(
            ingested_documents=len(documents),
            chunks_created=len(all_chunks),
            vector_ids=vector_ids,
            took_ms=round(took_ms, 2),
            doc_types=doc_types,
        )

    def query(
        self, question: str, k: int, generate_answer: bool, filter: dict | None = None
    ) -> QueryResult:
        start = time.monotonic()

        results = self._vector_store.similarity_search(question, k=k, filter=filter)
        logger.info("Retrieved %d chunks for query", len(results))

        sources = [
            SourceDocument(
                text=doc.page_content,
                score=round(float(score), 4),
                metadata=doc.metadata,
            )
            for doc, score in results
        ]

        answer: str | None = None
        if generate_answer:
            docs = [doc for doc, _ in results]
            answer = self._llm.generate(question, docs)

        took_ms = (time.monotonic() - start) * 1000
        return QueryResult(
            query=question,
            answer=answer,
            sources=sources,
            took_ms=round(took_ms, 2),
        )

    def query_with_extra_context(
        self,
        question: str,
        k: int,
        generate_answer: bool,
        filter: dict | None,
        extra_docs: list[Document],
    ) -> QueryResult:
        """Same retrieval as `query`, but unions `extra_docs` into the LLM context.

        `extra_docs` are not persisted and do not appear in the returned `sources` —
        they only influence the generated answer (used by /query-with-file when the
        uploaded file is not ingested into the vector store).
        """
        start = time.monotonic()

        results = self._vector_store.similarity_search(question, k=k, filter=filter)
        logger.info("Retrieved %d chunks for query", len(results))

        sources = [
            SourceDocument(
                text=doc.page_content,
                score=round(float(score), 4),
                metadata=doc.metadata,
            )
            for doc, score in results
        ]

        answer: str | None = None
        if generate_answer:
            docs = [doc for doc, _ in results] + extra_docs
            answer = self._llm.generate(question, docs)

        took_ms = (time.monotonic() - start) * 1000
        return QueryResult(
            query=question,
            answer=answer,
            sources=sources,
            took_ms=round(took_ms, 2),
        )
