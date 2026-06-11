import logging
import os

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

from app.core.interfaces import BaseEmbedder, BaseVectorStore

logger = logging.getLogger(__name__)


class FAISSVectorStore(BaseVectorStore):
    """FAISS-backed vector store persisted to a local directory."""

    def __init__(self, embedder: BaseEmbedder, index_path: str) -> None:
        self._embedder = embedder
        self._index_path = index_path
        self._store: FAISS | None = None

    def add_documents(self, documents: list[Document]) -> list[str]:
        if self._store is None:
            self._store = FAISS.from_documents(
                documents, self._embedder.langchain_embeddings
            )
        else:
            self._store.add_documents(documents)
        texts = [d.page_content for d in documents]
        logger.info("Added %d chunks to FAISS index", len(texts))
        return list(self._store.index_to_docstore_id.values())

    def similarity_search(
        self, query: str, k: int, filter: dict | None
    ) -> list[tuple[Document, float]]:
        if self._store is None:
            return []
        return self._store.similarity_search_with_relevance_scores(
            query, k=k, filter=filter
        )

    def persist(self) -> None:
        if self._store is not None:
            self._store.save_local(self._index_path)
            logger.info("FAISS index persisted to %s", self._index_path)

    def load(self) -> None:
        index_file = os.path.join(self._index_path, "index.faiss")
        if os.path.exists(index_file):
            self._store = FAISS.load_local(
                self._index_path,
                self._embedder.langchain_embeddings,
                allow_dangerous_deserialization=True,
            )
            logger.info("FAISS index loaded from %s", self._index_path)

    def is_loaded(self) -> bool:
        return self._store is not None

    def vector_count(self) -> int:
        if self._store is None:
            return 0
        return self._store.index.ntotal
