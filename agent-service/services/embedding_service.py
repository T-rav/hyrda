"""
Embedding service for text vectorization

DEPRECATED: This module is maintained for backward compatibility.
Please import from services.embedding instead:
    from services.embedding import EmbeddingProvider, create_embedding_provider
"""

# Backward compatibility imports
from services.embedding import (
    EmbeddingProvider,
    OpenAIEmbeddingProvider,
    chunk_text,
    create_embedding_provider,
)

__all__ = [
    "EmbeddingProvider",
    "OpenAIEmbeddingProvider",
    "create_embedding_provider",
    "chunk_text",
]
