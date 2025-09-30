"""
EmbeddingServiceFactory for test utilities
"""

from unittest.mock import AsyncMock, MagicMock


class EmbeddingServiceFactory:
    """Factory for creating embedding service mocks"""

    @staticmethod
    def create_mock_service(embeddings: list[list[float]] | None = None) -> MagicMock:
        """Create basic mock embedding service"""
        service = MagicMock()
        default_embeddings = [[0.1] * 1536]
        service.get_embeddings = AsyncMock(
            return_value=embeddings or default_embeddings
        )
        service.get_embedding = AsyncMock(
            return_value=(embeddings or default_embeddings)[0]
        )
        service.close = AsyncMock()
        return service

    @staticmethod
    def create_service_with_dimension(dimensions: int = 1536) -> MagicMock:
        """Create embedding service with specific dimension size"""
        return EmbeddingServiceFactory.create_mock_service([[0.1] * dimensions])
