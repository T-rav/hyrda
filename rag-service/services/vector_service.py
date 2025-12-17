"""
Vector Service Factory

Factory for creating Qdrant vector store instances.
"""

from config.settings import VectorSettings
from vector_stores.base import VectorStore
from vector_stores.qdrant_store import QdrantVectorStore


def create_vector_store(settings: VectorSettings) -> VectorStore:
    """
    Factory function to create Qdrant vector store instance.

    Args:
        settings: Vector database configuration settings

    Returns:
        Initialized Qdrant vector store instance
    """
    return QdrantVectorStore(settings)
