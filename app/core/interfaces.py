from abc import ABC, abstractmethod
from langchain_core.documents import Document


class BaseChunker(ABC):
    """Splits raw text into LangChain Document chunks."""

    @abstractmethod
    def split(self, text: str, metadata: dict) -> list[Document]: ...


class BaseEmbedder(ABC):
    """Converts text to dense vector embeddings."""

    @abstractmethod
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    @abstractmethod
    def embed_query(self, text: str) -> list[float]: ...


class BaseVectorStore(ABC):
    """Stores and retrieves document embeddings."""

    @abstractmethod
    def add_documents(self, documents: list[Document]) -> list[str]: ...

    @abstractmethod
    def similarity_search(
        self, query: str, k: int, filter: dict | None
    ) -> list[tuple[Document, float]]: ...

    @abstractmethod
    def persist(self) -> None: ...

    @abstractmethod
    def load(self) -> None: ...

    @abstractmethod
    def is_loaded(self) -> bool: ...

    @abstractmethod
    def vector_count(self) -> int: ...


class BaseLLM(ABC):
    """Generates grounded answers from retrieved context."""

    @abstractmethod
    def generate(self, question: str, context: list[Document]) -> str: ...
