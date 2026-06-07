"""Abstract retriever interface."""

from abc import ABC, abstractmethod

from rag_mcp.retrieval.vector_store import ScoredDocument


class Retriever(ABC):
    """Abstract base class for document retrievers."""

    @abstractmethod
    async def retrieve(self, query: str, top_k: int) -> list[ScoredDocument]:
        """Retrieve documents relevant to a query.

        Args:
            query: Query string.
            top_k: Number of top results to return.

        Returns:
            list[ScoredDocument]: Retrieved documents with scores.

        Raises:
            RetrieverError: If retrieval fails.
        """
        pass

