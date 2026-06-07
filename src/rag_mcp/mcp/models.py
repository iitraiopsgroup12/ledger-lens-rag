"""Pydantic models for MCP communication."""

from pydantic import BaseModel, Field


class MCPTool(BaseModel):
    """Represents an MCP tool available on the server."""

    name: str = Field(description="Tool name")
    description: str = Field(description="Tool description")
    input_schema: dict = Field(description="JSON schema for tool inputs")


class MCPRequest(BaseModel):
    """JSON-RPC 2.0 request format for MCP."""

    jsonrpc: str = Field(default="2.0", description="JSON-RPC version")
    method: str = Field(description="Method name to call")
    params: dict = Field(description="Method parameters")
    id: int | str = Field(description="Request ID")


class MCPResponse(BaseModel):
    """JSON-RPC 2.0 response format from MCP."""

    jsonrpc: str = Field(description="JSON-RPC version")
    result: dict | None = Field(default=None, description="Result if successful")
    error: dict | None = Field(default=None, description="Error if failed")
    id: int | str = Field(description="Request ID")

