import os
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings

# Resolve the .env file location: use APP_CONFIG_PATH if set, otherwise the
# project-local .env.  APP_CONFIG_PATH should be a directory; .env is appended.
_config_dir = os.environ.get("APP_CONFIG_PATH", "")
_env_file = str(Path(_config_dir) / ".env") if _config_dir else ".env"
print(_env_file)

class Settings(BaseSettings):
    # Provider selection: "openai" | "anthropic"
    llm_provider: str = Field("openai", alias="LLM_PROVIDER")

    # OpenAI
    openai_api_key: str = Field("", alias="OPENAI_API_KEY")
    embedding_model: str = Field("text-embedding-3-small", alias="EMBEDDING_MODEL")
    llm_model: str = Field("gpt-4o-mini", alias="LLM_MODEL")

    # Anthropic (LLM)
    anthropic_api_key: str = Field("", alias="ANTHROPIC_API_KEY")
    anthropic_llm_model: str = Field("claude-opus-4-8", alias="ANTHROPIC_LLM_MODEL")

    # Voyage AI (Anthropic-ecosystem embeddings)
    voyage_api_key: str = Field("", alias="VOYAGE_API_KEY")
    anthropic_embedding_model: str = Field("voyage-3", alias="ANTHROPIC_EMBEDDING_MODEL")

    # Google (LLM + embeddings)
    google_api_key: str = Field("", alias="GOOGLE_API_KEY")
    google_llm_model: str = Field("gemini-2.0-flash", alias="GOOGLE_LLM_MODEL")
    google_embedding_model: str = Field("models/text-embedding-004", alias="GOOGLE_EMBEDDING_MODEL")

    # HuggingFace (LLM via Inference API + local embeddings)
    huggingface_api_key: str = Field("", alias="HUGGINGFACE_API_KEY")
    huggingface_llm_model: str = Field("HuggingFaceH4/zephyr-7b-beta", alias="HUGGINGFACE_LLM_MODEL")
    huggingface_embedding_model: str = Field("sentence-transformers/all-MiniLM-L6-v2", alias="HUGGINGFACE_EMBEDDING_MODEL")

    # Shared (also used as NARRATIVE fallback by AdaptiveChunker)
    chunk_size: int = Field(1000, alias="CHUNK_SIZE")
    chunk_overlap: int = Field(200, alias="CHUNK_OVERLAP")
    faiss_index_path: str = Field("faiss_index", alias="FAISS_INDEX_PATH")
    default_top_k: int = Field(4, alias="DEFAULT_TOP_K")

    # Per-document-type adaptive chunking
    invoice_chunk_size: int = Field(400, alias="INVOICE_CHUNK_SIZE")
    invoice_chunk_overlap: int = Field(50, alias="INVOICE_CHUNK_OVERLAP")
    financial_chunk_size: int = Field(800, alias="FINANCIAL_CHUNK_SIZE")
    financial_chunk_overlap: int = Field(150, alias="FINANCIAL_CHUNK_OVERLAP")
    legal_chunk_size: int = Field(1500, alias="LEGAL_CHUNK_SIZE")
    legal_chunk_overlap: int = Field(300, alias="LEGAL_CHUNK_OVERLAP")
    tabular_chunk_size: int = Field(300, alias="TABULAR_CHUNK_SIZE")
    tabular_chunk_overlap: int = Field(0, alias="TABULAR_CHUNK_OVERLAP")
    markdown_chunk_size: int = Field(1000, alias="MARKDOWN_CHUNK_SIZE")
    markdown_chunk_overlap: int = Field(100, alias="MARKDOWN_CHUNK_OVERLAP")

    model_config = {"env_file": _env_file, "populate_by_name": True}


settings = Settings()
