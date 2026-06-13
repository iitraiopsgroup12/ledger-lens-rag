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
