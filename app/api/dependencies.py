import logging
from functools import lru_cache

from app.config import settings
from app.core.chunking import AdaptiveChunker
from app.core.embeddings import AnthropicEmbedder, GoogleEmbedder, HuggingFaceEmbedder, OpenAIEmbedder
from app.core.llm import AnthropicChatLLM, GoogleChatLLM, HuggingFaceChatLLM, OpenAIChatLLM
from app.core.pipeline import RAGPipeline
from app.core.vector_store import FAISSVectorStore

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def build_pipeline() -> RAGPipeline:
    """Assembles all concrete components into a RAGPipeline.

    Set LLM_PROVIDER=anthropic in .env to switch the LLM + embedder to the
    Anthropic stack (Claude LLM + Voyage AI embeddings). Defaults to OpenAI.
    """
    logger.info("Building RAG pipeline (provider=%s)", settings.llm_provider)
    chunker = AdaptiveChunker(
        invoice_chunk_size=settings.invoice_chunk_size,
        invoice_chunk_overlap=settings.invoice_chunk_overlap,
        financial_chunk_size=settings.financial_chunk_size,
        financial_chunk_overlap=settings.financial_chunk_overlap,
        legal_chunk_size=settings.legal_chunk_size,
        legal_chunk_overlap=settings.legal_chunk_overlap,
        tabular_chunk_size=settings.tabular_chunk_size,
        tabular_chunk_overlap=settings.tabular_chunk_overlap,
        markdown_chunk_size=settings.markdown_chunk_size,
        markdown_chunk_overlap=settings.markdown_chunk_overlap,
        narrative_chunk_size=settings.chunk_size,
        narrative_chunk_overlap=settings.chunk_overlap,
    )

    if settings.llm_provider == "anthropic":
        embedder = AnthropicEmbedder(
            api_key=settings.voyage_api_key,
            model=settings.anthropic_embedding_model,
        )
        llm = AnthropicChatLLM(
            api_key=settings.anthropic_api_key,
            model=settings.anthropic_llm_model,
            timeout=settings.llm_timeout,
        )
    elif settings.llm_provider == "google":
        embedder = GoogleEmbedder(
            api_key=settings.google_api_key,
            model=settings.google_embedding_model,
        )
        llm = GoogleChatLLM(
            api_key=settings.google_api_key,
            model=settings.google_llm_model,
            timeout=settings.llm_timeout,
        )
    elif settings.llm_provider == "huggingface":
        embedder = HuggingFaceEmbedder(model=settings.huggingface_embedding_model)
        llm = HuggingFaceChatLLM(
            api_key=settings.huggingface_api_key,
            model=settings.huggingface_llm_model,
            timeout=settings.llm_timeout,
        )
    else:
        embedder = OpenAIEmbedder(
            api_key=settings.openai_api_key,
            model=settings.embedding_model,
        )
        llm = OpenAIChatLLM(
            api_key=settings.openai_api_key,
            model=settings.llm_model,
            timeout=settings.llm_timeout,
        )

    vector_store = FAISSVectorStore(
        embedder=embedder,
        index_path=settings.faiss_index_path,
    )
    logger.info("RAG pipeline assembled successfully")
    return RAGPipeline(chunker=chunker, vector_store=vector_store, llm=llm)


def get_pipeline() -> RAGPipeline:
    return build_pipeline()
