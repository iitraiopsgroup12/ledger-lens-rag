import logging
from functools import lru_cache
from pathlib import Path

from langgraph.checkpoint.memory import MemorySaver
from sqlalchemy import create_engine

from app.config import settings
from app.core.chunking import AdaptiveChunker
from app.core.embeddings import AnthropicEmbedder, GoogleEmbedder, HuggingFaceEmbedder, OpenAIEmbedder
from app.core.interfaces import BaseEmbedder, BaseLLM
from app.core.kpi_repository import KpiRepository
from app.core.llm import AnthropicChatLLM, GoogleChatLLM, HuggingFaceChatLLM, OpenAIChatLLM
from app.core.pipeline import RAGPipeline
from app.core.vector_store import FAISSVectorStore
from app.kpi.graph import KpiNodes, build_kpi_graph
from app.kpi.registry import KpiRegistry
from app.kpi.service import KPIService
from app.kpi.storage_provider import build_document_storage

logger = logging.getLogger(__name__)


def build_llm() -> BaseLLM:
    """Construct the configured chat LLM (shared by RAG and the KPI workflow)."""
    if settings.llm_provider == "anthropic":
        return AnthropicChatLLM(
            api_key=settings.anthropic_api_key,
            model=settings.anthropic_llm_model,
            timeout=settings.llm_timeout,
        )
    if settings.llm_provider == "google":
        return GoogleChatLLM(
            api_key=settings.google_api_key,
            model=settings.google_llm_model,
            timeout=settings.llm_timeout,
        )
    if settings.llm_provider == "huggingface":
        return HuggingFaceChatLLM(
            api_key=settings.huggingface_api_key,
            model=settings.huggingface_llm_model,
            timeout=settings.llm_timeout,
        )
    return OpenAIChatLLM(
        api_key=settings.openai_api_key,
        model=settings.llm_model,
        timeout=settings.llm_timeout,
    )


def build_embedder() -> BaseEmbedder:
    """Construct the configured embedder.

    Selected by EMBEDDING_PROVIDER, which is independent of LLM_PROVIDER so the
    embedding stack can differ from the chat stack (e.g. Anthropic LLM + OpenAI
    embeddings). When EMBEDDING_PROVIDER is unset it follows LLM_PROVIDER.
    """
    provider = settings.resolved_embedding_provider
    if provider == "anthropic":
        return AnthropicEmbedder(
            api_key=settings.voyage_api_key,
            model=settings.anthropic_embedding_model,
        )
    if provider == "google":
        return GoogleEmbedder(
            api_key=settings.google_api_key,
            model=settings.google_embedding_model,
        )
    if provider == "huggingface":
        return HuggingFaceEmbedder(model=settings.huggingface_embedding_model)
    return OpenAIEmbedder(
        api_key=settings.openai_api_key,
        model=settings.embedding_model,
    )


@lru_cache(maxsize=1)
def build_pipeline() -> RAGPipeline:
    """Assembles all concrete components into a RAGPipeline.

    LLM_PROVIDER selects the chat model and EMBEDDING_PROVIDER the embedder;
    they are independent so you can mix stacks (e.g. Claude LLM + OpenAI
    embeddings). Both default to OpenAI.
    """
    logger.info(
        "Building RAG pipeline (llm=%s, embedding=%s)",
        settings.llm_provider,
        settings.resolved_embedding_provider,
    )
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

    vector_store = FAISSVectorStore(
        embedder=build_embedder(),
        index_path=settings.faiss_index_path,
    )
    llm = build_llm()
    logger.info("RAG pipeline assembled successfully")
    return RAGPipeline(chunker=chunker, vector_store=vector_store, llm=llm)


def get_pipeline() -> RAGPipeline:
    return build_pipeline()


@lru_cache(maxsize=1)
def build_kpi_service() -> KPIService:
    """Assemble the KPI agentic workflow seams into a compiled, checkpointed service.

    A process-lifetime MemorySaver gives per-(email, session) chat memory and
    human-in-the-loop resumability via the thread_id derived in KPIService.
    """
    logger.info("Building KPI service (provider=%s, db=%s)", settings.llm_provider, settings.database_url)
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    repository = KpiRepository(engine)
    storage = build_document_storage(settings.storage_dir)
    registry = KpiRegistry.from_files(settings.kpi_list_path, settings.kpi_prompt_path)
    prompt_template = Path(settings.kpi_prompt_path).read_text(encoding="utf-8")

    nodes = KpiNodes(
        repository=repository,
        llm=build_llm(),
        storage=storage,
        registry=registry,
        prompt_template=prompt_template,
        require_approval=settings.kpi_require_approval,
        admin_bypass=settings.kpi_admin_bypass,
        max_document_chars=settings.kpi_max_document_chars,
    )
    graph = build_kpi_graph(nodes, MemorySaver())
    logger.info("KPI service assembled successfully")
    return KPIService(graph)


def get_kpi_service() -> KPIService:
    return build_kpi_service()
