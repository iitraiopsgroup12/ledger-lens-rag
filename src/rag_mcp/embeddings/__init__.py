"""Embeddings module."""

from rag_mcp.embeddings.base import Embedder
from rag_mcp.embeddings.openai_embedder import EmbedderError, OpenAIEmbedder

__all__ = [
    "Embedder",
    "OpenAIEmbedder",
    "EmbedderError",
]

