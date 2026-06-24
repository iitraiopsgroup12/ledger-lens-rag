import logging

from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import OpenAIEmbeddings
from langchain_voyageai import VoyageAIEmbeddings

from app.core.interfaces import BaseEmbedder

logger = logging.getLogger(__name__)


class OpenAIEmbedder(BaseEmbedder):
    """Wraps OpenAI embeddings from langchain-openai."""

    def __init__(self, api_key: str, model: str) -> None:
        logger.info("Initializing OpenAIEmbedder with model %s", model)
        self._embeddings = OpenAIEmbeddings(api_key=api_key, model=model)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        logger.debug("Embedding %d document(s) via OpenAI", len(texts))
        return self._embeddings.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        logger.debug("Embedding query via OpenAI")
        return self._embeddings.embed_query(text)

    @property
    def langchain_embeddings(self) -> OpenAIEmbeddings:
        return self._embeddings


class AnthropicEmbedder(BaseEmbedder):
    """Wraps Voyage AI embeddings (Anthropic-ecosystem) from langchain-voyageai."""

    def __init__(self, api_key: str, model: str) -> None:
        logger.info("Initializing AnthropicEmbedder (Voyage AI) with model %s", model)
        self._embeddings = VoyageAIEmbeddings(voyage_api_key=api_key, model=model)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        logger.debug("Embedding %d document(s) via Voyage AI", len(texts))
        return self._embeddings.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        logger.debug("Embedding query via Voyage AI")
        return self._embeddings.embed_query(text)

    @property
    def langchain_embeddings(self) -> VoyageAIEmbeddings:
        return self._embeddings


class GoogleEmbedder(BaseEmbedder):
    """Wraps Google Generative AI embeddings from langchain-google-genai."""

    def __init__(self, api_key: str, model: str) -> None:
        logger.info("Initializing GoogleEmbedder with model %s", model)
        self._embeddings = GoogleGenerativeAIEmbeddings(google_api_key=api_key, model=model)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        logger.debug("Embedding %d document(s) via Google", len(texts))
        return self._embeddings.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        logger.debug("Embedding query via Google")
        return self._embeddings.embed_query(text)

    @property
    def langchain_embeddings(self) -> GoogleGenerativeAIEmbeddings:
        return self._embeddings


class HuggingFaceEmbedder(BaseEmbedder):
    """Wraps HuggingFace sentence-transformers embeddings (runs locally, no API key needed)."""

    def __init__(self, model: str) -> None:
        logger.info("Initializing HuggingFaceEmbedder with model %s", model)
        self._embeddings = HuggingFaceEmbeddings(model_name=model)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        logger.debug("Embedding %d document(s) via HuggingFace", len(texts))
        return self._embeddings.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        logger.debug("Embedding query via HuggingFace")
        return self._embeddings.embed_query(text)

    @property
    def langchain_embeddings(self) -> HuggingFaceEmbeddings:
        return self._embeddings
