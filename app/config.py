from pydantic_settings import BaseSettings
from pydantic import Field


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

    # Shared
    chunk_size: int = Field(1000, alias="CHUNK_SIZE")
    chunk_overlap: int = Field(200, alias="CHUNK_OVERLAP")
    faiss_index_path: str = Field("faiss_index", alias="FAISS_INDEX_PATH")
    default_top_k: int = Field(4, alias="DEFAULT_TOP_K")

    model_config = {"env_file": ".env", "populate_by_name": True}


settings = Settings()
