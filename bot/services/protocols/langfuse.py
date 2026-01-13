"""
Langfuse Service Protocol

Defines the interface for Langfuse observability services.
"""

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class LangfuseServiceProtocol(Protocol):
    """Protocol for Langfuse service implementations."""

    def trace_llm_call(
        self,
        model: str,
        messages: list[dict[str, str]],
        response: str | None,
        usage: dict[str, int] | None = None,
        metadata: dict[str, Any] | None = None,
        user_id: str | None = None,
        session_id: str | None = None,
    ) -> None:
        """
        Trace an LLM API call.

        Args:
            model: Model name used
            messages: Input messages
            response: Generated response
            usage: Token usage statistics
            metadata: Additional metadata
            user_id: Optional user identifier
            session_id: Optional session identifier

        """
        ...

    def trace_retrieval(
        self,
        query: str,
        results: list[dict[str, Any]],
        metadata: dict[str, Any] | None = None,
        user_id: str | None = None,
        session_id: str | None = None,
    ) -> None:
        """
        Trace a retrieval operation.

        Args:
            query: Search query
            results: Retrieved documents
            metadata: Additional metadata
            user_id: Optional user identifier
            session_id: Optional session identifier

        """
        ...

    def start_trace(
        self,
        name: str,
        user_id: str | None = None,
        session_id: str | None = None,
        **metadata,
    ) -> str:
        """
        Start a new trace.

        Args:
            name: Trace name
            user_id: Optional user identifier
            session_id: Optional session identifier
            **metadata: Additional metadata

        Returns:
            Trace ID

        """
        ...

    def end_trace(self, trace_id: str, output: Any | None = None, **metadata) -> None:
        """
        End a trace.

        Args:
            trace_id: Trace ID to end
            output: Final output
            **metadata: Additional metadata

        """
        ...

    async def flush(self) -> None:
        """Flush pending traces to Langfuse."""
        ...

    async def close(self) -> None:
        """Clean up resources."""
        ...

    def health_check(self) -> dict[str, str]:
        """Check service health status."""
        ...
