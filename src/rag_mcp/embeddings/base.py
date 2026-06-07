"""Abstract base class for embedder implementations."""

from abc import ABC, abstractmethod


class Embedder(ABC):
    """Abstract base class for text embedding providers."""

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of texts.

        Args:
            texts: List of text strings to embed.

        Returns:
            list[list[float]]: List of embedding vectors.

        Raises:
            EmbedderError: If embedding fails.
        """
        pass

