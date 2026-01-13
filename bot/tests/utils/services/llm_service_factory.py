"""
LLMServiceFactory for test utilities
"""

from collections.abc import Callable
from typing import Any
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

    @staticmethod
    def create_service_with_side_effect(side_effect: Callable[..., Any]) -> MagicMock:
        """Create LLM service mock with custom side effect for get_response.

        Useful for tests that need dynamic behavior based on input parameters.

        Args:
            side_effect: Callable that will be used as AsyncMock side_effect

        Returns:
            MagicMock LLM service with configured side effect

        """
        service = MagicMock()
        service.get_response = AsyncMock(side_effect=side_effect)
        service.initialize = AsyncMock()
        service.close = AsyncMock()
        return service

    @staticmethod
    def create_service_with_error(error: Exception) -> MagicMock:
        """Create LLM service mock that raises an error.

        Args:
            error: Exception to raise when get_response is called

        Returns:
            MagicMock LLM service that raises the specified error

        """
        service = MagicMock()
        service.get_response = AsyncMock(side_effect=error)
        service.initialize = AsyncMock()
        service.close = AsyncMock()
        return service
