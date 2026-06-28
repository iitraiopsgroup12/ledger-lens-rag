from pydantic import BaseModel, Field


class IngestDocumentRequest(BaseModel):
    id: str | None = Field(None, description="Optional document identifier")
    text: str = Field(..., min_length=1, description="Full text content to be ingested")
    metadata: dict = Field(default_factory=dict, description="Arbitrary metadata")


class IngestRequest(BaseModel):
    documents: list[IngestDocumentRequest] = Field(
        ..., min_length=1, description="Non-empty list of documents to ingest"
    )


class IngestResponse(BaseModel):
    status: str
    ingested_documents: int
    chunks_created: int
    vector_ids: list[str]
    took_ms: float
    doc_types: dict[str, str] = Field(default_factory=dict)


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Question to answer")
    top_k: int = Field(4, ge=1, le=20, description="Number of chunks to retrieve")
    generate_answer: bool = Field(True, description="Whether to generate an LLM answer")
    filter: dict | None = Field(None, description="Optional metadata filter")


class SourceDocumentResponse(BaseModel):
    text: str
    score: float
    metadata: dict


class QueryResponse(BaseModel):
    query: str
    answer: str | None
    sources: list[SourceDocumentResponse]
    took_ms: float


class HealthResponse(BaseModel):
    status: str
    index_loaded: bool
    vector_count: int


class KpiChatResponse(BaseModel):
    session_id: str
    status: str = Field(..., description="completed | awaiting_approval | denied | error")
    company: dict | None = None
    kpis: str | None = Field(None, description="KPI analysis rendered as Markdown")
    message: str | None = None
    pending_approval: dict | None = Field(
        None, description="Present when status=awaiting_approval; carries interrupt_id + summary"
    )
    steps: list[dict] = Field(default_factory=list)
    took_ms: float = 0.0


class KpiApproveRequest(BaseModel):
    email: str = Field(..., min_length=1, description="User email — chat-memory session key")
    session_id: str = Field(..., min_length=1, description="Session/thread to resume")
    interrupt_id: str | None = Field(None, description="The pending interrupt id from the chat response")
    decision: str = Field(..., description="approve | reject")
    feedback: str | None = Field(None, description="Optional reviewer note, returned on reject")
