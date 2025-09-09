"""
Vector Service Factory - Refactored

Factory for creating vector store instances using the new organized structure.
"""

from config.settings import VectorSettings
from services.vector_stores import (
    ElasticsearchVectorStore,
    PineconeVectorStore,
    VectorStore,
)


def create_vector_store(settings: VectorSettings) -> VectorStore:
    """
    Factory function to create vector store instances.

    Args:
        settings: Vector store configuration settings

    Returns:
        Initialized vector store instance

    Raises:
        ValueError: If unsupported provider is specified
    """
    store_map = {
        "elasticsearch": ElasticsearchVectorStore,
        "pinecone": PineconeVectorStore,
    }

    store_class = store_map.get(settings.provider.lower())
    if not store_class:
        supported = ", ".join(store_map.keys())
        raise ValueError(
            f"Unsupported vector store provider: {settings.provider}. Supported: {supported}"
        )

    return store_class(settings)
