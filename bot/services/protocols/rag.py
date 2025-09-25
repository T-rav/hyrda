"""
RAG Service Protocol

Defines the interface for RAG (Retrieval-Augmented Generation) services.
"""

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class RAGServiceProtocol(Protocol):
    """Protocol for RAG service implementations."""

    async def generate_response(
        self,
        query: str,
        user_id: str | None = None,
        session_id: str | None = None,
        **kwargs,
    ) -> str | None:
        """
        Generate a response using retrieval-augmented generation.

        Args:
            query: User query
            user_id: Optional user identifier
            session_id: Optional session identifier
            **kwargs: Additional parameters

        Returns:
            Generated response or None if generation fails
        """
        ...

    async def ingest_documents(self, documents: list[dict[str, Any]], **kwargs) -> int:
        """
        Ingest documents into the knowledge base.

        Args:
            documents: List of document dictionaries with content and metadata
            **kwargs: Additional ingestion parameters

        Returns:
            Number of documents successfully ingested
        """
        ...

    async def search(
        self, query: str, limit: int = 5, similarity_threshold: float = 0.7, **kwargs
    ) -> list[dict[str, Any]]:
        """
        Search for relevant documents.

        Args:
            query: Search query
            limit: Maximum number of results to return
            similarity_threshold: Minimum similarity score
            **kwargs: Additional search parameters

        Returns:
            List of relevant document chunks with metadata
        """
        ...

    async def close(self) -> None:
        """Clean up resources."""
        ...

    def health_check(self) -> dict[str, str]:
        """Check service health status."""
        ...
