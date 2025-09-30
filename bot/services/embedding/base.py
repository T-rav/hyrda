"""
Abstract base class for embedding providers
"""

from abc import ABC, abstractmethod

from config.settings import EmbeddingSettings


class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers"""

    def __init__(self, settings: EmbeddingSettings):
        self.settings = settings
        self.model = settings.model

    @abstractmethod
    async def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for a list of texts

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        pass

    @abstractmethod
    async def get_embedding(self, text: str) -> list[float]:
        """
        Generate embedding for a single text

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        pass

    @abstractmethod
    async def close(self):
        """Clean up resources"""
        pass
