"""
Vector Service Factory

Factory for creating Pinecone vector store instances.
"""

from config.settings import VectorSettings
from services.vector_stores import PineconeVectorStore, VectorStore


def create_vector_store(settings: VectorSettings) -> VectorStore:
    """
    Factory function to create Pinecone vector store instance.

    Args:
        settings: Pinecone configuration settings

    Returns:
        Initialized Pinecone vector store instance
    """
    return PineconeVectorStore(settings)
