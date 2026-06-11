from functools import lru_cache

from app.config import settings
from app.core.chunking import RecursiveChunker
from app.core.embeddings import AnthropicEmbedder, GoogleEmbedder, HuggingFaceEmbedder, OpenAIEmbedder
from app.core.llm import AnthropicChatLLM, GoogleChatLLM, HuggingFaceChatLLM, OpenAIChatLLM
from app.core.pipeline import RAGPipeline
from app.core.vector_store import FAISSVectorStore


@lru_cache(maxsize=1)
def build_pipeline() -> RAGPipeline:
    """Assembles all concrete components into a RAGPipeline.

    Set LLM_PROVIDER=anthropic in .env to switch the LLM + embedder to the
    Anthropic stack (Claude LLM + Voyage AI embeddings). Defaults to OpenAI.
    """
    chunker = RecursiveChunker(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )

    if settings.llm_provider == "anthropic":
        embedder = AnthropicEmbedder(
            api_key=settings.voyage_api_key,
            model=settings.anthropic_embedding_model,
        )
        llm = AnthropicChatLLM(
            api_key=settings.anthropic_api_key,
            model=settings.anthropic_llm_model,
        )
    elif settings.llm_provider == "google":
        embedder = GoogleEmbedder(
            api_key=settings.google_api_key,
            model=settings.google_embedding_model,
        )
        llm = GoogleChatLLM(
            api_key=settings.google_api_key,
            model=settings.google_llm_model,
        )
    elif settings.llm_provider == "huggingface":
        embedder = HuggingFaceEmbedder(model=settings.huggingface_embedding_model)
        llm = HuggingFaceChatLLM(
            api_key=settings.huggingface_api_key,
            model=settings.huggingface_llm_model,
        )
    else:
        embedder = OpenAIEmbedder(
            api_key=settings.openai_api_key,
            model=settings.embedding_model,
        )
        llm = OpenAIChatLLM(
            api_key=settings.openai_api_key,
            model=settings.llm_model,
        )

    vector_store = FAISSVectorStore(
        embedder=embedder,
        index_path=settings.faiss_index_path,
    )
    return RAGPipeline(chunker=chunker, vector_store=vector_store, llm=llm)


def get_pipeline() -> RAGPipeline:
    return build_pipeline()
