"""
LLMServiceFactory for test utilities
"""

from unittest.mock import AsyncMock, MagicMock


class LLMServiceFactory:
    """Factory for creating LLM service mocks"""

    @staticmethod
    def create_mock_service(response: str = "Test response") -> MagicMock:
        """Create basic mock LLM service"""
        service = MagicMock()
        service.get_response = AsyncMock(return_value=response)
        service.initialize = AsyncMock()
        service.close = AsyncMock()
        return service

    @staticmethod
    def create_service_with_rag(response: str = "RAG response") -> MagicMock:
        """Create LLM service mock with RAG enabled"""
        service = LLMServiceFactory.create_mock_service(response)
        service.rag_service = MagicMock()
        service.rag_service.generate_response = AsyncMock(return_value=response)
        return service
