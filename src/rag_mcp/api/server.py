"""FastAPI server exposing a POST /query endpoint that uses the RAG pipeline.

The endpoint expects a JWT in the Authorization header (Bearer) and a JSON body
with fields: query (str), user (str), company (str). The server decodes the JWT to
obtain session/user information, records the conversation into the provided
vector store, and forwards the request to the RAG pipeline's async query method.
"""

import logging
from typing import Any
from contextlib import asynccontextmanager
import inspect

import jwt
from fastapi import FastAPI, Header, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from rag_mcp.config.__init__ import get_settings
from rag_mcp.pipeline.rag_pipeline import RAGPipeline, PipelineResult
from rag_mcp.retrieval.faiss_store import FaissVectorStore
from rag_mcp.embeddings.openai_embedder import OpenAIEmbedder
from rag_mcp.llm.anthropic_llm import AnthropicLLM
from rag_mcp.pipeline.context_builder import ContextBuilder
from rag_mcp.mcp.clients.http_client import HTTPMCPClient
from rag_mcp.mcp.registry import MCPClientRegistry
from rag_mcp.retrieval.vector_store import Document
from rag_mcp.api.routes import router as api_router
from datetime import datetime, timezone


logger = logging.getLogger(__name__)
app = FastAPI()

# Security scheme for OpenAPI (Bearer JWT)
bearer_scheme = HTTPBearer()


class QueryPayload(BaseModel):
    query: str
    user: str
    company: str


def decode_jwt(token: str, secret: str) -> dict[str, Any]:
    try:
        # Use HS256 HMAC decode - secret should come from settings in examples
        return jwt.decode(token, secret, algorithms=["HS256"])  # type: ignore[arg-type]
    except jwt.PyJWTError as exc:
        logger.error("Failed to decode JWT: %s", exc)
        raise HTTPException(status_code=401, detail="Invalid token")


async def get_current_session(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> dict[str, Any]:
    """Dependency that validates Authorization: Bearer <token> and returns session info.

    This dependency is used in endpoints to enable the OpenAPI/Swagger "Authorize"
    button by declaring a security scheme.
    """
    if credentials is None:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    token = credentials.credentials
    settings = get_settings()
    decoded = decode_jwt(token, settings.ise_api_key)
    session_id = str(decoded.get("sub") or decoded.get("session_id") or decoded.get("user") or "anonymous")
    return {"decoded": decoded, "session_id": session_id}


async def _store_message(
    store: FaissVectorStore,
    embedder: Any,
    session_id: str,
    role: str,
    text: str,
    company: str | None = None,
) -> None:
    """Embed a message and store it in the FAISS vector store with session metadata."""
    if not text:
        return
    emb = await embedder.embed([text])
    if not emb:
        return
    doc_id = f"session:{session_id}:{role}:{hash(text) & 0xFFFFFFFF:x}"
    meta: dict[str, Any] = {"session_id": session_id, "role": role, "company": company}
    # Attach timezone-aware ISO timestamp to allow chronological sorting
    meta["ts"] = datetime.now(timezone.utc).isoformat()
    # faiss store expects embedding in metadata under 'embedding'
    meta["embedding"] = emb[0]  # type: ignore[assignment]
    doc = Document(id=doc_id, content=text, metadata=meta)
    await store.add([doc])


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context to initialize application state and gracefully shutdown.

    This replaces the deprecated @app.on_event("startup") approach.
    """
    settings = get_settings()

    # Create components
    app.state.settings = settings

    # Initialize embedder, fallback to a dummy embedder if credentials are missing
    try:
        app.state.embedder = OpenAIEmbedder(api_key=settings.openai_api_key, model=settings.embedding_model)
    except Exception as exc:  # pragma: no cover - runtime fallback
        logger.warning("Failed to initialize OpenAIEmbedder: %s. Falling back to DummyEmbedder.", exc)

        class DummyEmbedder:
            """Fallback embedder that returns zero vectors when real embedder is unavailable."""

            async def embed(self, texts: list[str]) -> list[list[float]]:  # type: ignore[override]
                dim = 1536
                return [[0.0] * dim for _ in texts]

        app.state.embedder = DummyEmbedder()

    # Initialize LLM, fallback to a dummy LLM if credentials are missing
    try:
        app.state.llm = AnthropicLLM(api_key=settings.anthropic_api_key, model=settings.llm_model, max_tokens=settings.llm_max_tokens)
    except Exception as exc:  # pragma: no cover - runtime fallback
        logger.warning("Failed to initialize AnthropicLLM: %s. Falling back to DummyLLM.", exc)

        class DummyLLM:
            """Fallback LLM that returns a canned response indicating LLM is unavailable."""

            async def complete(self, system: str, messages: list[dict]) -> str:  # type: ignore[override]
                return (
                    "LLM unavailable (missing API key). "
                    "Please configure ANTHROPIC_API_KEY to enable real LLM responses."
                )

        app.state.llm = DummyLLM()

    app.state.context_builder = ContextBuilder()
    app.state.vector_store = FaissVectorStore(similarity_threshold=settings.similarity_threshold)

    # MCP client registry and register an HTTP client for the ISE server
    registry = MCPClientRegistry()
    # The target MCP server is at http://0.0.0.0:8000/jsonrpc per user request
    http_client = HTTPMCPClient(base_url=settings.ise_mcp_base_url or "http://0.0.0.0:8000", api_key=settings.ise_api_key, rpc_path="/jsonrpc")
    registry.register("ise", http_client)
    app.state.mcp_registry = registry

    # Build the pipeline instance
    app.state.pipeline = RAGPipeline(
        mcp_registry=registry,
        embedder=app.state.embedder,
        vector_store=app.state.vector_store,
        llm=app.state.llm,
        context_builder=app.state.context_builder,
        settings=settings,
    )

    try:
        yield
    finally:
        # Attempt graceful shutdown of MCP clients
        try:
            servers = registry.list_servers()
            for sid in servers:
                try:
                    client = registry.get(sid)
                    # Prefer async close method if present
                    aclose = getattr(client, "aclose", None)
                    if aclose is not None and callable(aclose):
                        maybe = aclose()
                        if inspect.isawaitable(maybe):
                            await maybe
                    else:
                        close = getattr(client, "close", None)
                        if close is not None and callable(close):
                            close()
                except Exception:
                    # ignore shutdown errors
                    continue
        except Exception:
            pass


# Register lifespan handler
app.router.lifespan_context = lifespan  # type: ignore[attr-defined]

# Include API routes
app.include_router(api_router)



