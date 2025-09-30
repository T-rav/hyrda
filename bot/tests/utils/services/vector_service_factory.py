"""
VectorServiceFactory for test utilities
"""

from unittest.mock import AsyncMock, MagicMock


class VectorServiceFactory:
    """Factory for creating vector service mocks"""

    @staticmethod
    def create_mock_service() -> MagicMock:
        """Create basic mock vector service"""
        service = MagicMock()
        service.search = AsyncMock(return_value=[])
        service.add_documents = AsyncMock(return_value=True)
        service.delete_documents = AsyncMock(return_value=True)
        service.initialize = AsyncMock()
        service.close = AsyncMock()
        return service

    @staticmethod
    def create_service_with_results(results: list) -> MagicMock:
        """Create vector service that returns specific search results"""
        service = VectorServiceFactory.create_mock_service()
        service.search = AsyncMock(return_value=results)
        return service
