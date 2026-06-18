"""API integration tests using FastAPI TestClient with a mocked pipeline."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.pipeline import IngestResult, QueryResult, SourceDocument


@pytest.fixture()
def mock_pipeline():
    pipeline = MagicMock()
    pipeline._vector_store.is_loaded.return_value = True
    pipeline._vector_store.vector_count.return_value = 10
    pipeline.ingest.return_value = IngestResult(
        ingested_documents=1,
        chunks_created=3,
        vector_ids=["v1", "v2", "v3"],
        took_ms=42.0,
    )
    pipeline.query.return_value = QueryResult(
        query="What is X?",
        answer="X is Y",
        sources=[
            SourceDocument(
                text="chunk text",
                score=0.9,
                metadata={"source": "file.pdf"},
            )
        ],
        took_ms=55.0,
    )
    return pipeline


@pytest.fixture()
def client(mock_pipeline):
    from app.main import app
    from app.api.dependencies import get_pipeline

    app.dependency_overrides[get_pipeline] = lambda: mock_pipeline
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


class TestIngestEndpoint:
    def test_successful_ingest(self, client):
        resp = client.post(
            "/api/v1/ingest",
            json={
                "documents": [
                    {"id": "doc-001", "text": "Some content here", "metadata": {"source": "file.pdf"}}
                ]
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["ingested_documents"] == 1
        assert data["chunks_created"] == 3

    def test_empty_documents_rejected(self, client):
        resp = client.post("/api/v1/ingest", json={"documents": []})
        assert resp.status_code == 422

    def test_missing_text_rejected(self, client):
        resp = client.post(
            "/api/v1/ingest",
            json={"documents": [{"id": "x"}]},
        )
        assert resp.status_code == 422


class TestQueryEndpoint:
    def test_successful_query_with_answer(self, client):
        resp = client.post(
            "/api/v1/query",
            json={"query": "What is X?", "top_k": 4, "generate_answer": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["answer"] == "X is Y"
        assert len(data["sources"]) == 1

    def test_successful_query_without_answer(self, client, mock_pipeline):
        from app.core.pipeline import QueryResult, SourceDocument
        mock_pipeline.query.return_value = QueryResult(
            query="What is X?",
            answer=None,
            sources=[SourceDocument(text="t", score=0.8, metadata={})],
            took_ms=10.0,
        )
        resp = client.post(
            "/api/v1/query",
            json={"query": "What is X?", "generate_answer": False},
        )
        assert resp.status_code == 200
        assert resp.json()["answer"] is None

    def test_query_empty_index_returns_404(self, client, mock_pipeline):
        mock_pipeline._vector_store.is_loaded.return_value = False
        resp = client.post("/api/v1/query", json={"query": "hello"})
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "INDEX_NOT_FOUND"

    def test_top_k_out_of_range(self, client):
        resp = client.post("/api/v1/query", json={"query": "x", "top_k": 50})
        assert resp.status_code == 422


class TestQueryWithFileEndpoint:
    def test_isingest_true_calls_ingest_then_query(self, client, mock_pipeline):
        resp = client.post(
            "/api/v1/query-with-file",
            data={"query": "What is X?", "isIngest": "true"},
            files={"file": ("notes.txt", b"some uploaded content", "text/plain")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["answer"] == "X is Y"
        mock_pipeline.ingest.assert_called_once()
        mock_pipeline.query.assert_called_once()

    def test_isingest_false_uses_extra_context_without_ingest(self, client, mock_pipeline):
        from app.core.pipeline import QueryResult, SourceDocument

        mock_pipeline.query_with_extra_context.return_value = QueryResult(
            query="What is X?",
            answer="X is Y, per the uploaded file",
            sources=[SourceDocument(text="chunk text", score=0.9, metadata={"source": "file.pdf"})],
            took_ms=20.0,
        )
        resp = client.post(
            "/api/v1/query-with-file",
            data={"query": "What is X?", "isIngest": "false"},
            files={"file": ("notes.txt", b"some uploaded content", "text/plain")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["answer"] == "X is Y, per the uploaded file"
        mock_pipeline.ingest.assert_not_called()
        mock_pipeline.query_with_extra_context.assert_called_once()

    def test_unsupported_extension_rejected(self, client):
        resp = client.post(
            "/api/v1/query-with-file",
            data={"query": "What is X?"},
            files={"file": ("notes.pptx", b"content", "application/octet-stream")},
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "UNSUPPORTED_FILE_TYPE"

    def test_empty_file_rejected(self, client):
        resp = client.post(
            "/api/v1/query-with-file",
            data={"query": "What is X?"},
            files={"file": ("notes.txt", b"", "text/plain")},
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "EMPTY_FILE"

    def test_empty_query_rejected(self, client):
        resp = client.post(
            "/api/v1/query-with-file",
            data={"query": ""},
            files={"file": ("notes.txt", b"content", "text/plain")},
        )
        assert resp.status_code == 422

    def test_invalid_filter_json_rejected(self, client):
        resp = client.post(
            "/api/v1/query-with-file",
            data={"query": "What is X?", "filter": "{not-json}"},
            files={"file": ("notes.txt", b"content", "text/plain")},
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


class TestIngestDocTypes:
    def test_doc_types_present_in_response(self, client, mock_pipeline):
        from app.core.pipeline import IngestResult

        mock_pipeline.ingest.return_value = IngestResult(
            ingested_documents=1,
            chunks_created=3,
            vector_ids=["v1", "v2", "v3"],
            took_ms=42.0,
            doc_types={"doc-001": "invoice"},
        )
        resp = client.post(
            "/api/v1/ingest",
            json={"documents": [{"id": "doc-001", "text": "Invoice total $100"}]},
        )
        assert resp.status_code == 200
        assert resp.json()["doc_types"] == {"doc-001": "invoice"}

    def test_doc_types_empty_when_not_classified(self, client):
        resp = client.post(
            "/api/v1/ingest",
            json={"documents": [{"id": "doc-001", "text": "Some content here"}]},
        )
        assert resp.status_code == 200
        assert "doc_types" in resp.json()


class TestHealthEndpoint:
    def test_health_ok(self, client):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["index_loaded"] is True
        assert data["vector_count"] == 10
