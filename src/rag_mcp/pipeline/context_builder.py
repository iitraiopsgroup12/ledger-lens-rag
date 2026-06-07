"""Context builder for constructing prompts from documents and MCP responses."""

import logging

from rag_mcp.retrieval.vector_store import ScoredDocument


class ContextBuilder:
    """Builds prompt context from retrieved documents and MCP responses."""

    def __init__(self, max_context_length: int = 4000):
        """Initialize context builder.

        Args:
            max_context_length: Maximum length of context in characters.
        """
        self.max_context_length = max_context_length
        self.logger = logging.getLogger(__name__)

    def build_context(
        self,
        documents: list[ScoredDocument],
        mcp_data: dict | None = None,
    ) -> str:
        """Build context string from documents and MCP data.

        Args:
            documents: Retrieved documents with scores.
            mcp_data: Optional MCP response data.

        Returns:
            str: Formatted context string.
        """
        context_parts: list[str] = []

        # Add retrieved documents
        if documents:
            context_parts.append("## Retrieved Documents")
            for i, doc in enumerate(documents, 1):
                score_pct = int(doc.score * 100) if doc.score else 0
                source = doc.metadata.get("source", "unknown")
                context_parts.append(
                    f"\n### Document {i} (relevance: {score_pct}%) - {source}\n{doc.content}"
                )

        # Add MCP data
        if mcp_data:
            context_parts.append("\n## Market Data (from MCP Server)")
            context_parts.append(self._format_mcp_data(mcp_data))

        context = "\n".join(context_parts)

        # Truncate if too long
        if len(context) > self.max_context_length:
            self.logger.warning(
                "Context too long (%d chars), truncating to %d",
                len(context),
                self.max_context_length,
            )
            context = context[: self.max_context_length] + "\n...[truncated]"

        return context

    def _format_mcp_data(self, data: dict) -> str:
        """Format MCP response data for display.

        Args:
            data: MCP response data.

        Returns:
            str: Formatted data string.
        """
        lines: list[str] = []

        for key, value in data.items():
            if isinstance(value, dict):
                lines.append(f"- {key}:")
                for k, v in value.items():
                    lines.append(f"  - {k}: {v}")
            elif isinstance(value, list):
                lines.append(f"- {key}: {len(value)} items")
                for item in value[:5]:  # Show first 5 items
                    if isinstance(item, dict):
                        lines.append(f"  - {item}")
                    else:
                        lines.append(f"  - {item}")
                if len(value) > 5:
                    lines.append(f"  ... and {len(value) - 5} more items")
            else:
                lines.append(f"- {key}: {value}")

        return "\n".join(lines)

