"""FastAPI server exposing a POST /query endpoint that uses the RAG pipeline.

The endpoint expects a JWT in the Authorization header (Bearer) and a JSON body
with fields: query (str), user (str), company (str). The server decodes the JWT to
obtain session/user information, records the conversation into the provided
vector store, and forwards the request to the RAG pipeline's async query method.
"""

import logging
from typing import Any

import jwt
from fastapi import FastAPI, Header, HTTPException
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
from datetime import datetime


logger = logging.getLogger(__name__)
app = FastAPI()


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


async def _store_message(
    store: FaissVectorStore,
    embedder: OpenAIEmbedder,
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
    meta = {"session_id": session_id, "role": role, "company": company}
    # Attach ISO timestamp to allow chronological sorting
    meta["ts"] = datetime.utcnow().isoformat()
    # faiss store expects embedding in metadata under 'embedding'
    meta["embedding"] = emb[0]
    doc = Document(id=doc_id, content=text, metadata=meta)
    await store.add([doc])


@app.on_event("startup")
async def _startup() -> None:
    """Create long-lived components and register MCP client at startup."""
    settings = get_settings()

    # Create components
    app.state.settings = settings
    app.state.embedder = OpenAIEmbedder(api_key=settings.openai_api_key, model=settings.embedding_model)
    app.state.llm = AnthropicLLM(api_key=settings.anthropic_api_key, model=settings.llm_model, max_tokens=settings.llm_max_tokens)
    app.state.context_builder = ContextBuilder()
    app.state.vector_store = FaissVectorStore(similarity_threshold=settings.similarity_threshold)

    # MCP client registry and register an HTTP client for the ISE server
    registry = MCPClientRegistry()
    # The target MCP server is at http://0.0.0.0:8000/jsonrpc per user request
    http_client = HTTPMCPClient(base_url="http://0.0.0.0:8000", api_key=settings.ise_api_key, rpc_path="/jsonrpc")
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


@app.post("/query")
async def query_endpoint(payload: QueryPayload, authorization: str | None = Header(None)) -> dict:
    """Handle POST /query and route to RAG pipeline.

    The Authorization header should be: Bearer <jwt>. The JWT is decoded to
    obtain a session identifier used to store and retrieve per-user conversation
    history which is stored in the FAISS vector store and used as additional
    context for the LLM.
    """
    settings = get_settings()

    if authorization is None:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization scheme")

    token = authorization.split(" ", 1)[1]
    decoded = decode_jwt(token, settings.ise_api_key)
    session_id = str(decoded.get("sub") or decoded.get("session_id") or decoded.get("user") or "anonymous")

    pipeline: RAGPipeline = app.state.pipeline
    vector_store: FaissVectorStore = app.state.vector_store
    embedder: OpenAIEmbedder = app.state.embedder

    # Persist the incoming user message into the conversation memory
    await _store_message(vector_store, embedder, session_id, "user", payload.query, payload.company)

    # Use the company name as a potential tool hint to the MCP, else None
    tool_hint = None
    if payload.company:
        # simple mapping: use company name lowercased as hint; real app would map names -> tools
        tool_hint = payload.company.lower()

    # Call the RAG pipeline to obtain an answer
    try:
        result: PipelineResult = await pipeline.query(payload.query, server_id="ise", tool_hint=tool_hint)
    except Exception as exc:
        logger.exception("Pipeline query failed")
        raise HTTPException(status_code=500, detail=str(exc))

    # Store assistant response into memory
    await _store_message(vector_store, embedder, session_id, "assistant", result.answer, payload.company)

    return {
        "answer": result.answer,
        "sources": result.sources,
        "mcp_data": result.mcp_data,
        "tool_used": result.tool_used,
        "confidence": result.confidence,
    }


@app.get("/history")
async def history(authorization: str | None = Header(None)) -> dict:
    """Return conversation history for the authenticated session.

    The endpoint expects the same Authorization: Bearer <jwt> header used by
    `/query`. It returns an ordered list of messages (user and assistant)
    previously stored in the FAISS store during this session.
    """
    settings = get_settings()

    if authorization is None:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization scheme")

    token = authorization.split(" ", 1)[1]
    decoded = decode_jwt(token, settings.ise_api_key)
    session_id = str(decoded.get("sub") or decoded.get("session_id") or decoded.get("user") or "anonymous")

    vector_store: FaissVectorStore = app.state.vector_store

    try:
        docs = await vector_store.list_session(session_id)
    except Exception as exc:
        logger.exception("Failed to list session documents")
        raise HTTPException(status_code=500, detail=str(exc))

    # Convert documents to simple serializable form
    out = []
    for d in docs:
        out.append({
            "id": d.id,
            "role": d.metadata.get("role"),
            "company": d.metadata.get("company"),
            "ts": d.metadata.get("ts"),
            "content": d.content,
        })

    return {"session_id": session_id, "messages": out}


