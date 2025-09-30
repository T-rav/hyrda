"""
RAGServiceFactory for test utilities
"""

from unittest.mock import AsyncMock, MagicMock


class RAGServiceFactory:
    """Factory for creating RAG service mocks"""

    @staticmethod
    def create_service_with_response(response: str) -> MagicMock:
        """Create RAG service that returns specified response"""
        service = MagicMock()
        service.generate_response = AsyncMock(return_value=response)
        return service

    @staticmethod
    def create_service_with_error(error: Exception) -> MagicMock:
        """Create RAG service that raises errors"""
        service = MagicMock()
        service.generate_response = AsyncMock(side_effect=error)
        return service
