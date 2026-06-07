"""Anthropic Claude LLM backend implementation."""

import logging

from anthropic import AsyncAnthropic

from rag_mcp import RagMCPError
from rag_mcp.llm.base import LLMBackend


class LLMError(RagMCPError):
    """Error raised by LLM backend."""

    pass


class AnthropicLLM(LLMBackend):
    """Anthropic Claude LLM backend."""

    def __init__(self, api_key: str, model: str, max_tokens: int = 2048):
        """Initialize Anthropic LLM.

        Args:
            api_key: Anthropic API key.
            model: Model name (e.g., claude-sonnet-4-20250514).
            max_tokens: Maximum tokens for responses.
        """
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens
        self.client = AsyncAnthropic(api_key=api_key)
        self.logger = logging.getLogger(__name__)

    async def complete(
        self,
        system: str,
        messages: list[dict],
    ) -> str:
        """Generate completion using Anthropic Claude.

        Args:
            system: System prompt.
            messages: List of message dicts with 'role' and 'content'.

        Returns:
            str: Generated response.

        Raises:
            LLMError: If completion fails.
        """
        self.logger.debug(
            "Calling Claude %s with %d messages",
            self.model,
            len(messages),
        )

        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system,
                messages=messages,
            )

            # Extract text from response
            if response.content and len(response.content) > 0:
                content = response.content[0]
                if hasattr(content, "text"):
                    return content.text
                return str(content)

            self.logger.warning("No content in Claude response")
            return ""

        except Exception as e:
            self.logger.error("Failed to get Claude completion: %s", e)
            raise LLMError(f"Failed to get Claude completion: {e}") from e

