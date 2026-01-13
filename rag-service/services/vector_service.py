"""
Vector Service Factory

Factory for creating Qdrant vector store instances with singleton pattern.
"""

from config.settings import VectorSettings
from vector_stores.base import VectorStore
from vector_stores.qdrant_store import QdrantVectorStore

# Global singleton instance
_vector_store: VectorStore | None = None


def create_vector_store(settings: VectorSettings) -> VectorStore:
    """
    Factory function to create Qdrant vector store instance.

    Args:
        settings: Vector database configuration settings

    Returns:
        Initialized Qdrant vector store instance
    """
    return QdrantVectorStore(settings)


def set_vector_store(vector_store: VectorStore) -> None:
    """
    Set the global vector store singleton instance.

    Args:
        vector_store: Vector store instance to set as global singleton
    """
    global _vector_store  # noqa: PLW0603
    _vector_store = vector_store


def get_vector_store() -> VectorStore | None:
    """
    Get the global vector store singleton instance.

    Returns:
        Vector store instance or None if not initialized
    """
    return _vector_store
