"""
EmbeddingProviderMockFactory for test utilities
"""

from unittest.mock import AsyncMock, MagicMock


class EmbeddingProviderMockFactory:
    """Factory for creating mock embedding provider objects"""

    @staticmethod
    def create_mock_provider(
        embeddings: list[list[float]] | None = None,
        dimensions: int = 1536,
    ) -> MagicMock:
        """Create basic mock embedding provider"""
        provider = MagicMock()

        if embeddings is None:
            embeddings = [[0.1] * dimensions]

        provider.get_embeddings = AsyncMock(return_value=embeddings)
        provider.get_embedding = AsyncMock(return_value=embeddings[0])
        provider.close = AsyncMock()
        provider.model = "test-embedding-model"

        return provider

    @staticmethod
    def create_provider_with_error(error: Exception) -> MagicMock:
        """Create embedding provider that raises errors"""
        provider = EmbeddingProviderMockFactory.create_mock_provider()
        provider.get_embeddings = AsyncMock(side_effect=error)
        provider.get_embedding = AsyncMock(side_effect=error)
        return provider
