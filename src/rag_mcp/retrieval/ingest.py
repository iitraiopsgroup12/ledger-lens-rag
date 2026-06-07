"""Data ingestion helpers for the retrieval module.

This module provides a convenience function to embed raw texts and ingest
Document objects into a VectorStore in batches.
"""

import logging
from typing import Iterable

from rag_mcp.embeddings.base import Embedder
from rag_mcp.retrieval.vector_store import Document, VectorStore
from rag_mcp.retrieval.in_memory_store import VectorStoreError


logger = logging.getLogger(__name__)


async def ingest_texts(
    embedder: Embedder,
    vector_store: VectorStore,
    texts: list[str],
    ids: list[str] | None = None,
    batch_size: int = 100,
    metadata: dict | list[dict] | None = None,
) -> int:
    """Embed and ingest texts into the provided vector store.

    This function will batch texts, call the provided embedder, construct
    :class:`Document` objects (attaching the returned embedding to
    ``metadata["embedding"]``) and call ``vector_store.add`` for each batch.

    Args:
        embedder: An Embedder implementation with an async ``embed`` method.
        vector_store: A VectorStore to receive documents.
        texts: A list of strings to ingest.
        ids: Optional list of ids for documents. If not provided, ids will be
            generated as ``doc_0``, ``doc_1``, ...
        batch_size: Number of texts to embed per API call. Defaults to 100.
        metadata: Optional metadata dict applied to all documents or a list of
            per-document metadata dicts matching ``texts`` length.

    Returns:
        int: Total number of documents ingested.

    Raises:
        VectorStoreError: If inputs are invalid or vector_store.add fails.
    """
    if not texts:
        logger.debug("No texts provided for ingestion")
        return 0

    n = len(texts)

    if ids is None:
        ids = [f"doc_{i}" for i in range(n)]
    elif len(ids) != n:
        raise VectorStoreError("Length of 'ids' must match length of 'texts'")

    # Normalize metadata
    if metadata is None:
        metas: list[dict] = [{} for _ in range(n)]
    elif isinstance(metadata, dict):
        metas = [metadata.copy() for _ in range(n)]
    else:
        if len(metadata) != n:
            raise VectorStoreError("Length of 'metadata' list must match length of 'texts'")
        metas = [m.copy() for m in metadata]

    total_added = 0

    # Process in batches
    for start in range(0, n, batch_size):
        end = min(start + batch_size, n)
        batch_texts = texts[start:end]
        batch_ids = ids[start:end]
        batch_metas = metas[start:end]

        logger.debug("Embedding batch %d-%d", start, end)
        try:
            embeddings = await embedder.embed(batch_texts)
        except Exception as exc:  # propagate as VectorStoreError
            logger.error("Embedding failed for batch %d-%d: %s", start, end, exc)
            raise VectorStoreError(f"Embedding failed: {exc}") from exc

        if len(embeddings) != len(batch_texts):
            raise VectorStoreError("Embedder returned unexpected number of embeddings")

        documents: list[Document] = []
        for doc_id, text, emb, meta in zip(batch_ids, batch_texts, embeddings, batch_metas):
            # Ensure embedding is attached to metadata under key 'embedding'
            doc_meta = dict(meta) if meta is not None else {}
            doc_meta["embedding"] = emb
            documents.append(Document(id=doc_id, content=text, metadata=doc_meta))

        # Add to vector store
        try:
            await vector_store.add(documents)
            total_added += len(documents)
            logger.info("Ingested %d documents (total %d)", len(documents), total_added)
        except Exception as exc:
            logger.error("Failed to add documents to vector store: %s", exc)
            raise VectorStoreError(f"Failed to add documents: {exc}") from exc

    return total_added

