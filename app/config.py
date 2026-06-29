import logging
import os
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)

# Environment gate. Only a dev environment loads values from the local .env
# file; everywhere else (e.g. Kubernetes) settings come solely from real process
# environment variables. Opt in explicitly with APP_ENV=dev (or development /
# local). This check runs at import, before Settings() reads its sources, so it
# must read os.environ directly rather than the settings object.
_DEV_ENVS = {"dev", "development", "local"}
IS_DEV = os.environ.get("APP_ENV", "").strip().lower() in _DEV_ENVS

# Resolve the .env file location only in dev: use APP_CONFIG_PATH if set,
# otherwise the project-local .env (APP_CONFIG_PATH is a directory; .env is
# appended). In non-dev environments _env_file is None so pydantic skips it.
_env_file = None
if IS_DEV:
    _config_dir = os.environ.get("APP_CONFIG_PATH", "")
    _env_file = str(Path(_config_dir) / ".env") if _config_dir else ".env"
    logger.debug("Dev environment: loading settings from env file: %s", _env_file)
else:
    logger.debug("Non-dev environment: using process environment variables only")

class Settings(BaseSettings):
    # Deployment environment. "dev" (or development/local) makes the app load the
    # local .env file; any other value runs purely off process env vars.
    app_env: str = Field("production", alias="APP_ENV")

    # Provider selection: "openai" | "anthropic" | "google" | "huggingface"
    llm_provider: str = Field("openai", alias="LLM_PROVIDER")
    # Embedding provider. Independent of the LLM so you can mix stacks (e.g.
    # Anthropic LLM + OpenAI embeddings). Empty = follow llm_provider.
    embedding_provider: str = Field("", alias="EMBEDDING_PROVIDER")

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

    # Logging verbosity (DEBUG | INFO | WARNING | ERROR | CRITICAL).
    log_level: str = Field("INFO", alias="LOG_LEVEL")

    # CORS: comma-separated list of allowed origins ("*" = any). Browsers forbid
    # combining "*" with credentials, so cors_allow_credentials is ignored (forced
    # off) when origins is "*".
    cors_allow_origins: str = Field("*", alias="CORS_ALLOW_ORIGINS")
    cors_allow_credentials: bool = Field(False, alias="CORS_ALLOW_CREDENTIALS")

    # Shared (also used as NARRATIVE fallback by AdaptiveChunker)
    chunk_size: int = Field(1000, alias="CHUNK_SIZE")
    chunk_overlap: int = Field(200, alias="CHUNK_OVERLAP")
    faiss_index_path: str = Field("faiss_index", alias="FAISS_INDEX_PATH")
    default_top_k: int = Field(4, alias="DEFAULT_TOP_K")

    # Max seconds to wait for an LLM generation before timing out (default 1 hour).
    llm_timeout: int = Field(3600, alias="LLM_TIMEOUT")

    # --- KPI agentic workflow ---
    # PostgreSQL metadata DB backing the KPI repository. DATABASE_URL, if set,
    # wins; otherwise it is assembled from the POSTGRES_* parts below.
    database_url_override: str = Field("", alias="DATABASE_URL")
    postgres_host: str = Field("localhost", alias="POSTGRES_HOST")
    postgres_port: str = Field("5432", alias="POSTGRES_PORT")
    postgres_user: str = Field("postgres", alias="POSTGRES_USER")
    postgres_password: str = Field("postgres", alias="POSTGRES_PASSWORD")
    postgres_db: str = Field("postgres", alias="POSTGRES_DB")
    # Local filesystem root for LocalFileStorage document retrieval.
    storage_dir: str = Field("storage", alias="STORAGE_DIR")
    # KPI catalog + prompt template sources.
    kpi_list_path: str = Field("docs/KPI-List.txt", alias="KPI_LIST_PATH")
    kpi_prompt_path: str = Field("docs/kpi-prompt.md", alias="KPI_PROMPT_PATH")
    # Require human-in-the-loop approval before final KPI generation.
    kpi_require_approval: bool = Field(True, alias="KPI_REQUIRE_APPROVAL")
    # Allow admin-role users to bypass the watchlist authorization guardrail.
    kpi_admin_bypass: bool = Field(False, alias="KPI_ADMIN_BYPASS")
    # Max chars of parsed document text injected into the KPI prompt (keeps the
    # request under the LLM/provider token limit). 0 = unbounded.
    kpi_max_document_chars: int = Field(24000, alias="KPI_MAX_DOCUMENT_CHARS")

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

    model_config = {"env_file": _env_file, "populate_by_name": True, "extra": "ignore"}

    @property
    def cors_allow_origins_list(self) -> list[str]:
        """Parsed CORS origins: comma-separated env string -> list."""
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]

    @property
    def is_dev(self) -> bool:
        """True when running in a dev environment (loads the local .env file)."""
        return self.app_env.strip().lower() in _DEV_ENVS

    @property
    def resolved_embedding_provider(self) -> str:
        """Embedding provider, falling back to the LLM provider when unset."""
        return self.embedding_provider or self.llm_provider

    @property
    def database_url(self) -> str:
        """SQLAlchemy URL for the KPI repository (psycopg driver)."""
        if self.database_url_override:
            return self.database_url_override
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()
