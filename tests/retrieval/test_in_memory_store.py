"""Tests for in-memory vector store."""

import pytest

from rag_mcp.retrieval.in_memory_store import InMemoryVectorStore, VectorStoreError
from rag_mcp.retrieval.vector_store import Document


@pytest.mark.asyncio
async def test_in_memory_store_add_documents() -> None:
    """Test adding documents to store."""
    store = InMemoryVectorStore()

    documents = [
        Document(
            id="1",
            content="Test document 1",
            metadata={"embedding": [0.1, 0.2, 0.3]},
        ),
        Document(
            id="2",
            content="Test document 2",
            metadata={"embedding": [0.2, 0.3, 0.4]},
        ),
    ]

    await store.add(documents)

    assert len(store.documents) == 2


@pytest.mark.asyncio
async def test_in_memory_store_add_missing_embedding() -> None:
    """Test adding document without embedding raises error."""
    store = InMemoryVectorStore()

    documents = [
        Document(
            id="1",
            content="Test document",
            metadata={},  # Missing embedding
        ),
    ]

    with pytest.raises(VectorStoreError):
        await store.add(documents)


@pytest.mark.asyncio
async def test_in_memory_store_search() -> None:
    """Test searching for similar documents."""
    store = InMemoryVectorStore(similarity_threshold=0.5)

    documents = [
        Document(
            id="1",
            content="Machine learning basics",
            metadata={"embedding": [1.0, 0.0, 0.0], "source": "doc1"},
        ),
        Document(
            id="2",
            content="Deep learning advanced",
            metadata={"embedding": [0.9, 0.1, 0.0], "source": "doc2"},
        ),
        Document(
            id="3",
            content="Database design patterns",
            metadata={"embedding": [0.0, 0.0, 1.0], "source": "doc3"},
        ),
    ]

    await store.add(documents)

    # Search with similar vector to first document
    query_vector = [1.0, 0.0, 0.0]
    results = await store.search(query_vector, top_k=2)

    assert len(results) > 0
    assert results[0].id == "1"  # Most similar


@pytest.mark.asyncio
async def test_in_memory_store_search_empty() -> None:
    """Test search on empty store."""
    store = InMemoryVectorStore()

    query_vector = [0.1, 0.2, 0.3]
    results = await store.search(query_vector, top_k=5)

    assert results == []


@pytest.mark.asyncio
async def test_in_memory_store_similarity_threshold() -> None:
    """Test similarity threshold filtering."""
    store = InMemoryVectorStore(similarity_threshold=0.9)

    documents = [
        Document(
            id="1",
            content="Doc 1",
            metadata={"embedding": [1.0, 0.0, 0.0]},
        ),
        Document(
            id="2",
            content="Doc 2",
            metadata={"embedding": [0.1, 0.1, 0.1]},  # Very different
        ),
    ]

    await store.add(documents)

    query_vector = [1.0, 0.0, 0.0]
    results = await store.search(query_vector, top_k=2)

    # Should only return doc1 due to high threshold
    assert len(results) == 1
    assert results[0].id == "1"


@pytest.mark.asyncio
async def test_in_memory_store_add_multiple_times() -> None:
    """Test adding documents multiple times."""
    store = InMemoryVectorStore()

    docs1 = [
        Document(
            id="1",
            content="First batch",
            metadata={"embedding": [0.1, 0.2, 0.3]},
        ),
    ]

    docs2 = [
        Document(
            id="2",
            content="Second batch",
            metadata={"embedding": [0.2, 0.3, 0.4]},
        ),
    ]

    await store.add(docs1)
    await store.add(docs2)

    assert len(store.documents) == 2

