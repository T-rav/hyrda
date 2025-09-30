"""
LLMProviderMockFactory for test utilities
"""

from unittest.mock import AsyncMock, MagicMock


class LLMProviderMockFactory:
    """Factory for creating mock LLM provider objects"""

    @staticmethod
    def create_mock_provider(response: str = "Test response") -> MagicMock:
        """Create basic mock LLM provider"""
        provider = MagicMock()
        provider.get_response = AsyncMock(return_value=response)
        provider.close = AsyncMock()
        provider.model = "test-model"
        provider.temperature = 0.7
        provider.max_tokens = 2000
        return provider

    @staticmethod
    def create_provider_with_error(error: Exception) -> MagicMock:
        """Create LLM provider that raises errors"""
        provider = LLMProviderMockFactory.create_mock_provider()
        provider.get_response = AsyncMock(side_effect=error)
        return provider
