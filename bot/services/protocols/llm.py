"""
LLM Service Protocol

Defines the interface for LLM services to enable dependency injection
and improve testability.
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMServiceProtocol(Protocol):
    """Protocol for LLM service implementations."""

    async def get_response(
        self,
        messages: list[dict[str, str]],
        system_message: str | None = None,
        user_id: str | None = None,
        session_id: str | None = None,
        **kwargs,
    ) -> str | None:
        """
        Generate a response from the LLM.

        Args:
            messages: List of conversation messages
            system_message: Optional system message for context
            user_id: Optional user identifier for tracking
            session_id: Optional session identifier for tracking
            **kwargs: Additional provider-specific parameters

        Returns:
            Generated response text or None if generation fails
        """
        ...

    async def get_response_with_rag(
        self,
        query: str,
        user_id: str | None = None,
        session_id: str | None = None,
        **kwargs,
    ) -> str | None:
        """
        Generate a response using RAG (Retrieval-Augmented Generation).

        Args:
            query: User query for RAG-enhanced response
            user_id: Optional user identifier for tracking
            session_id: Optional session identifier for tracking
            **kwargs: Additional parameters

        Returns:
            RAG-enhanced response or None if generation fails
        """
        ...

    async def close(self) -> None:
        """Clean up resources and close connections."""
        ...

    def health_check(self) -> dict[str, str]:
        """
        Check service health status.

        Returns:
            Dict containing health status information
        """
        ...
