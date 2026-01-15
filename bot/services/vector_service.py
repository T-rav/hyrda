"""
Vector Service Factory

Factory for creating Qdrant vector store instances.
"""

from config.settings import VectorSettings
from services.vector_stores import QdrantVectorStore, VectorStore


def create_vector_store(settings: VectorSettings) -> VectorStore | None:
    """
    Factory function to create Qdrant vector store instance.

    Args:
        settings: Vector database configuration settings

    Returns:
        Initialized Qdrant vector store instance, or None if disabled

    """
    if not settings.enabled:
        return None
    return QdrantVectorStore(settings)
