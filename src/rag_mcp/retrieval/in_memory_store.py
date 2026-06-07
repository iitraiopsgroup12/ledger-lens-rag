"""In-memory vector store using cosine similarity."""

import asyncio
import logging
from typing import Any

import numpy as np

from rag_mcp import RagMCPError
from rag_mcp.retrieval.vector_store import Document, ScoredDocument, VectorStore


class VectorStoreError(RagMCPError):
    """Error raised by vector store."""

    pass


class InMemoryVectorStore(VectorStore):
    """In-memory vector store using numpy for cosine similarity."""

    def __init__(self, similarity_threshold: float = 0.7):
        """Initialize in-memory vector store.

        Args:
            similarity_threshold: Minimum similarity score for results.
        """
        self.similarity_threshold = similarity_threshold
        self.documents: list[Document] = []
        self.embeddings: np.ndarray | None = None
        self.lock = asyncio.Lock()
        self.logger = logging.getLogger(__name__)

    async def add(self, documents: list[Document]) -> None:
        """Add documents to the store.

        Args:
            documents: List of documents with embeddings.

        Raises:
            VectorStoreError: If embeddings are invalid.
        """
        async with self.lock:
            if not documents:
                self.logger.warning("No documents provided")
                return

            self.logger.debug("Adding %d documents to vector store", len(documents))

            # For in-memory store, we expect documents to have embeddings in metadata
            for doc in documents:
                if "embedding" not in doc.metadata:
                    raise VectorStoreError(
                        f"Document {doc.id} missing 'embedding' in metadata"
                    )

            self.documents.extend(documents)

            # Rebuild embeddings array
            embeddings_list: list[list[float]] = [
                doc.metadata["embedding"] for doc in self.documents
            ]
            self.embeddings = np.array(embeddings_list, dtype=np.float32)

            self.logger.debug("Vector store now contains %d documents", len(self.documents))

    async def search(
        self,
        query_vector: list[float],
        top_k: int,
    ) -> list[ScoredDocument]:
        """Search for similar documents using cosine similarity.

        Args:
            query_vector: Query embedding vector.
            top_k: Number of top results to return.

        Returns:
            list[ScoredDocument]: Similar documents with scores.
        """
        async with self.lock:
            if self.embeddings is None or len(self.documents) == 0:
                self.logger.debug("Vector store is empty")
                return []

            query_array = np.array(query_vector, dtype=np.float32)

            # Compute cosine similarity
            query_norm = np.linalg.norm(query_array)
            if query_norm == 0:
                return []

            query_normalized = query_array / query_norm
            embeddings_normalized = self.embeddings / np.linalg.norm(
                self.embeddings, axis=1, keepdims=True
            )

            similarities = np.dot(embeddings_normalized, query_normalized)

            # Filter by threshold
            above_threshold = similarities >= self.similarity_threshold
            valid_indices = np.where(above_threshold)[0]

            if len(valid_indices) == 0:
                self.logger.debug("No documents found above threshold %.2f", self.similarity_threshold)
                return []

            # Get top-k
            scores_with_indices = [
                (similarities[idx].item(), idx) for idx in valid_indices
            ]
            scores_with_indices.sort(reverse=True, key=lambda x: x[0])

            results: list[ScoredDocument] = []
            for score, idx in scores_with_indices[:top_k]:
                doc = self.documents[idx]
                results.append(
                    ScoredDocument(
                        id=doc.id,
                        content=doc.content,
                        metadata=doc.metadata,
                        score=float(score),
                    )
                )

            self.logger.debug("Search returned %d results", len(results))
            return results

