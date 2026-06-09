"""API routes for the RAG MCP pipeline.

This module defines an APIRouter with the `/query` and `/history` endpoints.
The router expects the application to have been initialized (app.state.*)
by the main `server.py` lifespan handler.
"""

from typing import Any

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from rag_mcp.config import get_settings
from rag_mcp.pipeline.rag_pipeline import PipelineResult, RAGPipeline
from rag_mcp.retrieval.faiss_store import FaissVectorStore
from rag_mcp.retrieval.vector_store import Document

router = APIRouter()
bearer_scheme = HTTPBearer()


class QueryPayload(BaseModel):
    query: str
    user: str
    company: str


def decode_jwt(token: str, secret: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, secret, algorithms=["HS256"])  # type: ignore[arg-type]
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid token")


async def get_current_session(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> dict[str, Any]:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    token = credentials.credentials
    settings = get_settings()
    decoded = decode_jwt(token, settings.ise_api_key)
    session_id = str(decoded.get("sub") or decoded.get("session_id") or decoded.get("user") or "anonymous")
    return {"decoded": decoded, "session_id": session_id}


async def _store_message(
    request: Request,
    session_id: str,
    role: str,
    text: str,
    company: str | None = None,
) -> None:
    """Embed a message using the configured embedder and store it in vector store.

    Args:
        request: FastAPI Request used to access app.state components.
    """
    if not text:
        return

    embedder: Any = request.app.state.embedder
    vector_store: FaissVectorStore = request.app.state.vector_store

    emb = await embedder.embed([text])
    if not emb:
        return

    doc_id = f"session:{session_id}:{role}:{hash(text) & 0xFFFFFFFF:x}"
    meta = {"session_id": session_id, "role": role, "company": company}
    from datetime import datetime, timezone

    meta["ts"] = datetime.now(timezone.utc).isoformat()
    meta["embedding"] = emb[0]  # type: ignore[assignment]

    doc = Document(id=doc_id, content=text, metadata=meta)
    await vector_store.add([doc])


@router.post("/query")
async def query_endpoint(payload: QueryPayload, session: dict[str, Any] = Depends(get_current_session), request: Request = Depends()) -> dict:
    session_id = session["session_id"]

    pipeline: RAGPipeline = request.app.state.pipeline

    # Persist the incoming user message into the conversation memory
    await _store_message(request, session_id, "user", payload.query, payload.company)

    tool_hint = payload.company.lower() if payload.company else None

    try:
        result: PipelineResult = await pipeline.query(payload.query, server_id="ise", tool_hint=tool_hint)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    # Store assistant response into memory
    await _store_message(request, session_id, "assistant", result.answer, payload.company)

    return {
        "answer": result.answer,
        "sources": result.sources,
        "mcp_data": result.mcp_data,
        "tool_used": result.tool_used,
        "confidence": result.confidence,
    }


@router.get("/history")
async def history(session: dict[str, Any] = Depends(get_current_session), request: Request = Depends()) -> dict:
    session_id = session["session_id"]
    vector_store: FaissVectorStore = request.app.state.vector_store

    try:
        docs = await vector_store.list_session(session_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

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

