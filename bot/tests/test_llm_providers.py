"""
Tests for LLM provider implementations.

Tests OpenAI provider with proper mocking.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from pydantic import SecretStr

from bot.services.llm_providers import (
    LLMProvider,
    OpenAIProvider,
    create_llm_provider,
)
from config.settings import LLMSettings


# Test Data Builders and Factories
class LLMSettingsBuilder:
    """Builder for creating LLM settings with different configurations"""

    def __init__(self):
        self._provider = "openai"
        self._api_key = "test-api-key"
        self._model = "gpt-4"
        self._temperature = 0.7
        self._max_tokens = 1000
        self._base_url = None

    def with_provider(self, provider: str) -> "LLMSettingsBuilder":
        self._provider = provider
        return self

    def with_api_key(self, api_key: str) -> "LLMSettingsBuilder":
        self._api_key = api_key
        return self

    def with_model(self, model: str) -> "LLMSettingsBuilder":
        self._model = model
        return self

    def with_temperature(self, temperature: float) -> "LLMSettingsBuilder":
        self._temperature = temperature
        return self

    def with_max_tokens(self, max_tokens: int) -> "LLMSettingsBuilder":
        self._max_tokens = max_tokens
        return self

    def with_base_url(self, base_url: str) -> "LLMSettingsBuilder":
        self._base_url = base_url
        return self

    def build(self) -> LLMSettings:
        return LLMSettings(
            provider=self._provider,
            api_key=SecretStr(self._api_key),
            model=self._model,
            temperature=self._temperature,
            max_tokens=self._max_tokens,
            base_url=self._base_url,
        )


class MockResponseFactory:
    """Factory for creating mock API responses"""

    @staticmethod
    def create_openai_response(
        content: str = "Test response",
        prompt_tokens: int = 10,
        completion_tokens: int = 20,
        total_tokens: int = 30,
    ) -> Mock:
        """Create a mock OpenAI API response"""
        response = Mock()
        response.choices = [Mock()]
        response.choices[0].message.content = content
        response.usage = Mock()
        response.usage.prompt_tokens = prompt_tokens
        response.usage.completion_tokens = completion_tokens
        response.usage.total_tokens = total_tokens
        return response


# Test Classes
class TestLLMProvider:
    """Test the abstract LLMProvider class"""

    def test_llm_provider_is_abstract(self):
        """Test that LLMProvider cannot be instantiated directly"""
        settings = LLMSettingsBuilder().build()
        with pytest.raises(TypeError):
            LLMProvider(settings)  # type: ignore[abstract]


class TestOpenAIProvider:
    """Test OpenAI provider implementation"""

    def test_init_basic(self):
        """Test basic initialization"""
        settings = LLMSettingsBuilder().build()

        with patch("bot.services.llm_providers.AsyncOpenAI") as mock_client:
            provider = OpenAIProvider(settings)

            assert provider.model == "gpt-4"
            assert provider.temperature == 0.7
            assert provider.max_tokens == 1000
            mock_client.assert_called_once_with(api_key="test-api-key")

    def test_init_with_base_url(self):
        """Test initialization with custom base URL"""
        settings = LLMSettingsBuilder().with_base_url("https://custom.api.com").build()

        with patch("bot.services.llm_providers.AsyncOpenAI") as mock_client:
            OpenAIProvider(settings)

            mock_client.assert_called_once_with(
                api_key="test-api-key", base_url="https://custom.api.com"
            )

    @pytest.mark.asyncio
    async def test_get_response_success(self):
        """Test successful response generation"""
        settings = LLMSettingsBuilder().build()
        mock_response = MockResponseFactory.create_openai_response("Hello!")

        with patch("bot.services.llm_providers.AsyncOpenAI") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.chat.completions.create.return_value = mock_response
            mock_client_class.return_value = mock_client

            provider = OpenAIProvider(settings)

            messages = [{"role": "user", "content": "Hi"}]
            result = await provider.get_response(
                messages, system_message="You are helpful"
            )

            assert result == "Hello!"
            mock_client.chat.completions.create.assert_called_once()
            call_args = mock_client.chat.completions.create.call_args[1]
            assert call_args["model"] == "gpt-4"
            assert call_args["temperature"] == 0.7
            assert call_args["max_tokens"] == 1000
            assert len(call_args["messages"]) == 2  # system + user message

    @pytest.mark.asyncio
    async def test_get_response_with_session_metadata(self):
        """Test response generation with session metadata"""
        settings = LLMSettingsBuilder().build()
        mock_response = MockResponseFactory.create_openai_response("Response")

        with patch("bot.services.llm_providers.AsyncOpenAI") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.chat.completions.create.return_value = mock_response
            mock_client_class.return_value = mock_client

            provider = OpenAIProvider(settings)

            messages = [{"role": "user", "content": "Hi"}]
            result = await provider.get_response(
                messages, session_id="session123", user_id="user456"
            )

            assert result == "Response"
            call_args = mock_client.chat.completions.create.call_args[1]
            assert "metadata" in call_args
            assert call_args["metadata"]["langfuse_session_id"] == "session123"
            assert call_args["metadata"]["langfuse_user_id"] == "user456"

    @pytest.mark.asyncio
    async def test_get_response_error(self):
        """Test error handling during response generation"""
        settings = LLMSettingsBuilder().build()

        with patch("bot.services.llm_providers.AsyncOpenAI") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.chat.completions.create.side_effect = Exception("API Error")
            mock_client_class.return_value = mock_client

            provider = OpenAIProvider(settings)

            messages = [{"role": "user", "content": "Hi"}]
            result = await provider.get_response(messages)

            assert result is None

    @pytest.mark.asyncio
    async def test_get_response_none_content(self):
        """Test handling of None response content"""
        settings = LLMSettingsBuilder().build()
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = None
        mock_response.usage = Mock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 0
        mock_response.usage.total_tokens = 10

        with patch("bot.services.llm_providers.AsyncOpenAI") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.chat.completions.create.return_value = mock_response
            mock_client_class.return_value = mock_client

            provider = OpenAIProvider(settings)

            messages = [{"role": "user", "content": "Hi"}]
            result = await provider.get_response(messages)

            assert result is None

    @pytest.mark.asyncio
    async def test_close(self):
        """Test client cleanup"""
        settings = LLMSettingsBuilder().build()

        with patch("bot.services.llm_providers.AsyncOpenAI") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client

            provider = OpenAIProvider(settings)
            await provider.close()

            # Should not raise an error


class TestCreateLLMProvider:
    """Test the provider factory function"""

    def test_create_openai_provider(self):
        """Test creating OpenAI provider"""
        settings = LLMSettingsBuilder().with_provider("openai").build()

        with patch("bot.services.llm_providers.AsyncOpenAI"):
            provider = create_llm_provider(settings)
            assert isinstance(provider, OpenAIProvider)

    def test_create_unsupported_provider(self):
        """Test error for unsupported provider"""
        settings = LLMSettingsBuilder().with_provider("unsupported").build()

        with pytest.raises(ValueError, match="Unsupported LLM provider: unsupported"):
            create_llm_provider(settings)

    def test_case_insensitive_provider_names(self):
        """Test that provider names are case insensitive"""
        settings = LLMSettingsBuilder().with_provider("OPENAI").build()

        with patch("bot.services.llm_providers.AsyncOpenAI"):
            provider = create_llm_provider(settings)
            assert isinstance(provider, OpenAIProvider)
