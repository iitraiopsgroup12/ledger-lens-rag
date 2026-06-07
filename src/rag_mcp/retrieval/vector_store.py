"""Abstract vector store interface and models."""

from abc import ABC, abstractmethod

from pydantic import BaseModel, Field


class Document(BaseModel):
    """Represents a document to be stored in vector store."""

    id: str = Field(description="Document ID")
    content: str = Field(description="Document content")
    metadata: dict = Field(default_factory=dict, description="Document metadata")


class ScoredDocument(Document):
    """Document with similarity score."""

    score: float = Field(description="Similarity score")


class VectorStore(ABC):
    """Abstract base class for vector storage."""

    @abstractmethod
    async def add(self, documents: list[Document]) -> None:
        """Add documents to the vector store.

        Args:
            documents: List of documents to add.

        Raises:
            VectorStoreError: If adding fails.
        """
        pass

    @abstractmethod
    async def search(
        self,
        query_vector: list[float],
        top_k: int,
    ) -> list[ScoredDocument]:
        """Search for similar documents.

        Args:
            query_vector: Query embedding vector.
            top_k: Number of top results to return.

        Returns:
            list[ScoredDocument]: List of similar documents with scores.

        Raises:
            VectorStoreError: If search fails.
        """
        pass

