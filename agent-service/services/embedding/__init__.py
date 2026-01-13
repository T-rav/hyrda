"""
Embedding providers for text vectorization

Provides abstract base class and concrete implementations for generating
text embeddings using various providers.
"""

from .base import EmbeddingProvider
from .factory import create_embedding_provider
from .openai import OpenAIEmbeddingProvider
from .utils import chunk_text

__all__ = [
    "EmbeddingProvider",
    "OpenAIEmbeddingProvider",
    "create_embedding_provider",
    "chunk_text",
]
