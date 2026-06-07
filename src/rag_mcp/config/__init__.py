"""Configuration and settings management for the RAG MCP pipeline."""

import logging
from functools import lru_cache
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    # MCP Server
    ise_mcp_base_url: str = Field(
        default="http://localhost:8000",
        description="Base URL for ISE MCP server",
    )
    ise_api_key: str = Field(
        default="",
        description="API key for ISE MCP server",
    )

    # LLM
    anthropic_api_key: str = Field(
        default="",
        description="API key for Anthropic Claude",
    )
    llm_model: str = Field(
        default="claude-sonnet-4-20250514",
        description="Model name for LLM backend",
    )
    llm_max_tokens: int = Field(
        default=2048,
        description="Maximum tokens for LLM responses",
    )

    # Embeddings
    openai_api_key: str = Field(
        default="",
        description="API key for OpenAI embeddings",
    )
    embedding_model: str = Field(
        default="text-embedding-3-small",
        description="Model name for embeddings",
    )

    # Retrieval
    top_k: int = Field(
        default=5,
        description="Number of top results to retrieve",
    )
    similarity_threshold: float = Field(
        default=0.7,
        description="Minimum similarity threshold for retrieval",
    )

    # Logging
    log_level: str = Field(
        default="INFO",
        description="Logging level",
    )

    def dict(self, **kwargs: Any) -> dict[str, Any]:
        """Convert settings to dictionary."""
        return super().model_dump(**kwargs)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get cached settings instance.

    Returns:
        Settings: Configured settings object.
    """
    logger = logging.getLogger(__name__)
    logger.debug("Loading settings from environment")
    return Settings()

