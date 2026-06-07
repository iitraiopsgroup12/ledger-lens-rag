"""Abstract base class for LLM backends."""

from abc import ABC, abstractmethod


class LLMBackend(ABC):
    """Abstract base class for LLM (Large Language Model) backends."""

    @abstractmethod
    async def complete(
        self,
        system: str,
        messages: list[dict],
    ) -> str:
        """Generate a completion based on system prompt and messages.

        Args:
            system: System prompt.
            messages: List of message dicts with 'role' and 'content'.

        Returns:
            str: Generated response.

        Raises:
            LLMError: If completion fails.
        """
        pass

