"""
Vector Service Protocol

Defines the interface for vector storage and search services.
"""

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class VectorServiceProtocol(Protocol):
    """Protocol for vector service implementations."""

    async def add_documents(self, documents: list[dict[str, Any]], **kwargs) -> int:
        """
        Add documents to the vector store.

        Args:
            documents: List of document dictionaries with content and metadata
            **kwargs: Additional parameters

        Returns:
            Number of documents successfully added

        """
        ...

    async def search(
        self,
        query: str | list[float],
        limit: int = 5,
        similarity_threshold: float = 0.7,
        **kwargs,
    ) -> list[dict[str, Any]]:
        """
        Search for similar documents.

        Args:
            query: Search query (text or embedding vector)
            limit: Maximum number of results
            similarity_threshold: Minimum similarity score
            **kwargs: Additional search parameters

        Returns:
            List of similar documents with metadata and scores

        """
        ...

    async def delete_documents(self, document_ids: list[str], **kwargs) -> int:
        """
        Delete documents from the vector store.

        Args:
            document_ids: List of document IDs to delete
            **kwargs: Additional parameters

        Returns:
            Number of documents successfully deleted

        """
        ...

    async def initialize(self) -> None:
        """Initialize the vector store."""
        ...

    async def close(self) -> None:
        """Clean up resources."""
        ...

    def health_check(self) -> dict[str, str]:
        """Check service health status."""
        ...
