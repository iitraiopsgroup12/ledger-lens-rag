"""Retrieval module."""

from rag_mcp.retrieval.base import Retriever
from rag_mcp.retrieval.in_memory_store import InMemoryVectorStore, VectorStoreError
from rag_mcp.retrieval.vector_store import Document, ScoredDocument, VectorStore
from rag_mcp.retrieval.ingest import ingest_texts
from rag_mcp.retrieval.faiss_store import FaissVectorStore, FaissError

__all__ = [
    "Retriever",
    "VectorStore",
    "Document",
    "ScoredDocument",
    "InMemoryVectorStore",
    "VectorStoreError",
    "ingest_texts",
    "FaissVectorStore",
    "FaissError",
]

