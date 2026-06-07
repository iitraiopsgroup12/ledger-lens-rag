"""FAISS-backed vector store implementation.

Provides a VectorStore implementation using FAISS for efficient similarity
search. This implementation stores documents and their normalized embeddings,
rebuilding the FAISS index on add/upsert operations. It is async-safe via an
asyncio.Lock.
"""

import asyncio
import logging
from typing import Dict, List

import numpy as np

try:
    import faiss  # type: ignore
except Exception as exc:  # pragma: no cover - optional runtime dependency
    faiss = None  # type: ignore

from rag_mcp import RagMCPError
from rag_mcp.retrieval.vector_store import Document, ScoredDocument, VectorStore


class FaissError(RagMCPError):
    """Errors raised by the FAISS vector store."""


class FaissVectorStore(VectorStore):
    """FAISS-backed vector store.

    Notes:
    - Embeddings are expected to be list[float] and will be normalized for cosine
      similarity. The underlying index uses inner-product on normalized vectors
      (equivalent to cosine similarity).
    - The store supports upsert behavior: adding documents with existing ids will
      replace the stored document and embedding.
    - For simplicity and correctness, the FAISS index is rebuilt after each
      add() call. For very large datasets, consider a writable index or
      chunked rebuilding strategy.
    """

    def __init__(self, similarity_threshold: float = 0.7):
        if faiss is None:
            raise FaissError("faiss is not available; please install faiss-cpu or faiss")

        self.similarity_threshold = similarity_threshold
        self._id_to_doc: Dict[str, Document] = {}
        self._ids: List[str] = []
        self._embeddings: np.ndarray | None = None  # shape (N, dim)
        self._index = None
        self.lock = asyncio.Lock()
        self.logger = logging.getLogger(__name__)

    async def add(self, documents: list[Document]) -> None:
        """Add or upsert documents into the FAISS index.

        Args:
            documents: List of Document instances with embedding in metadata.

        Raises:
            FaissError: If embedding is missing or index operations fail.
        """
        async with self.lock:
            if not documents:
                self.logger.debug("No documents provided for FAISS add")
                return

            for doc in documents:
                if "embedding" not in doc.metadata:
                    raise FaissError(f"Document {doc.id} missing 'embedding' in metadata")

            # Upsert into internal mapping
            for doc in documents:
                self._id_to_doc[doc.id] = doc

            # Rebuild ids and embeddings arrays
            self._ids = list(self._id_to_doc.keys())
            embeddings_list = [self._id_to_doc[_id].metadata["embedding"] for _id in self._ids]
            try:
                emb_array = np.array(embeddings_list, dtype=np.float32)
            except Exception as exc:
                raise FaissError(f"Invalid embeddings: {exc}") from exc

            # Normalize embeddings to unit length for cosine similarity
            norms = np.linalg.norm(emb_array, axis=1, keepdims=True)
            # Avoid division by zero
            norms[norms == 0] = 1.0
            emb_normalized = emb_array / norms

            self._embeddings = emb_normalized

            # Build FAISS index (inner product on normalized vectors => cosine)
            dim = self._embeddings.shape[1]
            try:
                index = faiss.IndexFlatIP(dim)
                index.add(self._embeddings)
                self._index = index
            except Exception as exc:
                raise FaissError(f"Failed to build FAISS index: {exc}") from exc

            self.logger.info("FAISS store contains %d documents", len(self._ids))

    async def search(self, query_vector: list[float], top_k: int) -> list[ScoredDocument]:
        """Search FAISS index for similar documents.

        Args:
            query_vector: Query embedding as list[float]
            top_k: Number of top results to return

        Returns:
            list[ScoredDocument]
        """
        async with self.lock:
            if self._index is None or self._embeddings is None or len(self._ids) == 0:
                self.logger.debug("FAISS index is empty")
                return []

            q = np.array(query_vector, dtype=np.float32)
            q_norm = np.linalg.norm(q)
            if q_norm == 0:
                return []
            q = q / q_norm

            # faiss expects shape (n, dim)
            q = q.reshape(1, -1)

            try:
                distances, indices = self._index.search(q, top_k)
            except Exception as exc:
                raise FaissError(f"FAISS search failed: {exc}") from exc

            results: list[ScoredDocument] = []
            sims = distances[0]
            idxs = indices[0]

            for sim, idx in zip(sims, idxs):
                if idx < 0:
                    continue
                # sim is inner product of normalized vectors -> cosine similarity
                if sim < self.similarity_threshold:
                    continue
                doc_id = self._ids[int(idx)]
                doc = self._id_to_doc[doc_id]
                results.append(
                    ScoredDocument(
                        id=doc.id,
                        content=doc.content,
                        metadata=doc.metadata,
                        score=float(sim),
                    )
                )

            return results

    async def list_session(self, session_id: str) -> list[Document]:
        """Return all documents belonging to a session.

        This helper is specific to the FAISS-backed store and is used to
        retrieve per-session conversation history stored in document metadata
        under the key "session_id". Results are sorted by the metadata
        timestamp key "ts" when present.

        Args:
            session_id: The session identifier to filter documents by.

        Returns:
            list[Document]: Documents matching the session id.
        """
        async with self.lock:
            if not self._id_to_doc:
                return []

            docs: list[Document] = []
            for doc in self._id_to_doc.values():
                try:
                    if doc.metadata.get("session_id") == session_id:
                        docs.append(doc)
                except Exception:
                    # skip malformed metadata
                    continue

            # Sort by timestamp if available
            def _ts_key(d: Document) -> str:
                return d.metadata.get("ts", "")

            docs.sort(key=_ts_key)
            return docs

