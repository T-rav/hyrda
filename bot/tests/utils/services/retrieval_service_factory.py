"""
RetrievalServiceFactory for test utilities
"""

from unittest.mock import AsyncMock, MagicMock


class RetrievalServiceFactory:
    """Factory for creating retrieval service mocks"""

    @staticmethod
    def create_mock_service() -> MagicMock:
        """Create basic mock retrieval service"""
        service = MagicMock()
        service.search = AsyncMock(return_value=[])
        service.initialize = AsyncMock()
        service.close = AsyncMock()
        return service

    @staticmethod
    def create_service_with_results(results: list) -> MagicMock:
        """Create retrieval service that returns specific results"""
        service = RetrievalServiceFactory.create_mock_service()
        service.search = AsyncMock(return_value=results)
        return service
