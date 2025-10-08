"""
Vector Service Factory

Factory for creating vector store instances (Pinecone or Qdrant).
"""

from config.settings import VectorSettings
from services.vector_stores import PineconeVectorStore, QdrantVectorStore, VectorStore


def create_vector_store(settings: VectorSettings) -> VectorStore:
    """
    Factory function to create vector store instance based on provider.

    Args:
        settings: Vector database configuration settings

    Returns:
        Initialized vector store instance (Pinecone or Qdrant)

    Raises:
        ValueError: If provider is not supported
    """
    provider = settings.provider.lower()

    if provider == "pinecone":
        return PineconeVectorStore(settings)
    elif provider == "qdrant":
        return QdrantVectorStore(settings)
    else:
        raise ValueError(
            f"Unsupported vector provider: {provider}. Supported providers: pinecone, qdrant"
        )
