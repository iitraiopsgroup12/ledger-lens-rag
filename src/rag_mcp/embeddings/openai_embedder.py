"""OpenAI embeddings implementation."""

import logging

from openai import AsyncOpenAI

from rag_mcp import RagMCPError
from rag_mcp.embeddings.base import Embedder


class EmbedderError(RagMCPError):
    """Error raised by embedder."""

    pass


class OpenAIEmbedder(Embedder):
    """OpenAI text embeddings provider."""

    BATCH_SIZE = 100

    def __init__(self, api_key: str, model: str = "text-embedding-3-small"):
        """Initialize OpenAI embedder.

        Args:
            api_key: OpenAI API key.
            model: Embedding model name.
        """
        self.api_key = api_key
        self.model = model
        self.client = AsyncOpenAI(api_key=api_key)
        self.logger = logging.getLogger(__name__)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts using OpenAI API.

        Args:
            texts: List of texts to embed.

        Returns:
            list[list[float]]: List of embedding vectors.

        Raises:
            EmbedderError: If embedding fails.
        """
        if not texts:
            self.logger.warning("No texts provided for embedding")
            return []

        self.logger.debug("Embedding %d texts using model %s", len(texts), self.model)

        all_embeddings: list[list[float]] = []

        # Process in batches
        for i in range(0, len(texts), self.BATCH_SIZE):
            batch = texts[i : i + self.BATCH_SIZE]
            self.logger.debug("Processing embedding batch %d-%d", i, i + len(batch))

            try:
                response = await self.client.embeddings.create(
                    input=batch,
                    model=self.model,
                )

                for data in response.data:
                    all_embeddings.append(data.embedding)

            except Exception as e:
                self.logger.error("Failed to embed texts: %s", e)
                raise EmbedderError(f"Failed to embed texts: {e}") from e

        self.logger.debug("Successfully embedded %d texts", len(texts))
        return all_embeddings

