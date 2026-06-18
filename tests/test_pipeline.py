"""Unit tests for RAGPipeline using mocked interfaces — no network calls."""

from unittest.mock import MagicMock

import pytest
from langchain_core.documents import Document

from app.core.interfaces import BaseChunker, BaseLLM, BaseVectorStore
from app.core.pipeline import IngestDocument, RAGPipeline


@pytest.fixture()
def mock_chunker() -> BaseChunker:
    chunker = MagicMock(spec=BaseChunker)
    chunker.split.return_value = [
        Document(page_content="chunk1", metadata={"doc_id": "doc-001"}),
        Document(page_content="chunk2", metadata={"doc_id": "doc-001"}),
    ]
    return chunker


@pytest.fixture()
def mock_vector_store() -> BaseVectorStore:
    store = MagicMock(spec=BaseVectorStore)
    store.add_documents.return_value = ["id-1", "id-2"]
    store.similarity_search.return_value = [
        (Document(page_content="chunk1", metadata={"source": "file.pdf"}), 0.92),
    ]
    store.is_loaded.return_value = True
    store.vector_count.return_value = 2
    return store


@pytest.fixture()
def mock_llm() -> BaseLLM:
    llm = MagicMock(spec=BaseLLM)
    llm.generate.return_value = "Mocked answer"
    return llm


@pytest.fixture()
def pipeline(mock_chunker, mock_vector_store, mock_llm) -> RAGPipeline:
    return RAGPipeline(
        chunker=mock_chunker,
        vector_store=mock_vector_store,
        llm=mock_llm,
    )


class TestIngest:
    def test_returns_correct_counts(self, pipeline, mock_chunker, mock_vector_store):
        docs = [IngestDocument(text="hello world", id="doc-001")]
        result = pipeline.ingest(docs)

        assert result.ingested_documents == 1
        assert result.chunks_created == 2
        assert result.vector_ids == ["id-1", "id-2"]
        mock_chunker.split.assert_called_once()
        mock_vector_store.add_documents.assert_called_once()
        mock_vector_store.persist.assert_called_once()

    def test_metadata_forwarding(self, pipeline, mock_chunker):
        docs = [IngestDocument(text="text", id="x", metadata={"source": "s.pdf"})]
        pipeline.ingest(docs)
        _, kwargs = mock_chunker.split.call_args
        meta = mock_chunker.split.call_args[0][1]
        assert meta["source"] == "s.pdf"
        assert meta["doc_id"] == "x"


class TestQuery:
    def test_with_answer_generation(self, pipeline, mock_vector_store, mock_llm):
        result = pipeline.query("What is X?", k=4, generate_answer=True)

        assert result.query == "What is X?"
        assert result.answer == "Mocked answer"
        assert len(result.sources) == 1
        assert result.sources[0].score == 0.92
        mock_llm.generate.assert_called_once()

    def test_without_answer_generation(self, pipeline, mock_llm):
        result = pipeline.query("What is X?", k=4, generate_answer=False)

        assert result.answer is None
        mock_llm.generate.assert_not_called()

    def test_empty_results_no_llm_call(self, pipeline, mock_vector_store, mock_llm):
        mock_vector_store.similarity_search.return_value = []
        result = pipeline.query("unknown?", k=4, generate_answer=True)

        assert result.answer is None
        assert result.sources == []
        mock_llm.generate.assert_not_called()


class TestQueryWithExtraContext:
    def test_extra_docs_passed_to_llm_alongside_retrieved(self, pipeline, mock_vector_store, mock_llm):
        extra_docs = [Document(page_content="uploaded file content", metadata={"source_file": "f.txt"})]
        result = pipeline.query_with_extra_context(
            "What is X?", k=4, generate_answer=True, filter=None, extra_docs=extra_docs
        )

        assert result.answer == "Mocked answer"
        mock_llm.generate.assert_called_once()
        _, llm_docs = mock_llm.generate.call_args[0]
        assert extra_docs[0] in llm_docs
        assert len(llm_docs) == 2  # 1 retrieved + 1 extra

    def test_sources_reflect_only_vector_store_results(self, pipeline):
        result = pipeline.query_with_extra_context(
            "What is X?", k=4, generate_answer=False, filter=None,
            extra_docs=[Document(page_content="uploaded", metadata={})],
        )

        assert len(result.sources) == 1
        assert result.sources[0].text == "chunk1"

    def test_no_generation_skips_llm(self, pipeline, mock_llm):
        result = pipeline.query_with_extra_context(
            "What is X?", k=4, generate_answer=False, filter=None,
            extra_docs=[Document(page_content="uploaded", metadata={})],
        )

        assert result.answer is None
        mock_llm.generate.assert_not_called()
