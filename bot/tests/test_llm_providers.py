"""
Tests for LLM provider implementations.

Tests OpenAI, Anthropic, and Ollama providers with proper mocking.
"""

from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest
from pydantic import SecretStr

from bot.services.llm_providers import (
    AnthropicProvider,
    LLMProvider,
    OllamaProvider,
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
        kwargs = {
            "provider": self._provider,
            "api_key": SecretStr(self._api_key),
            "model": self._model,
            "temperature": self._temperature,
            "max_tokens": self._max_tokens,
        }
        if self._base_url:
            kwargs["base_url"] = self._base_url
        return LLMSettings(**kwargs)

    @classmethod
    def openai(cls, model: str = "gpt-4") -> "LLMSettingsBuilder":
        return (
            cls()
            .with_provider("openai")
            .with_model(model)
            .with_api_key("test-openai-key")
        )

    @classmethod
    def anthropic(cls, model: str = "claude-3-haiku") -> "LLMSettingsBuilder":
        return (
            cls()
            .with_provider("anthropic")
            .with_model(model)
            .with_api_key("test-anthropic-key")
        )

    @classmethod
    def ollama(cls, model: str = "llama2") -> "LLMSettingsBuilder":
        return (
            cls()
            .with_provider("ollama")
            .with_model(model)
            .with_base_url("http://localhost:11434")
        )


class UsageStatsBuilder:
    """Builder for creating usage statistics mocks"""

    def __init__(self):
        self._prompt_tokens = 10
        self._completion_tokens = 5
        self._total_tokens = 15
        self._input_tokens = None
        self._output_tokens = None

    def with_prompt_tokens(self, tokens: int) -> "UsageStatsBuilder":
        self._prompt_tokens = tokens
        self._total_tokens = self._prompt_tokens + self._completion_tokens
        return self

    def with_completion_tokens(self, tokens: int) -> "UsageStatsBuilder":
        self._completion_tokens = tokens
        self._total_tokens = self._prompt_tokens + self._completion_tokens
        return self

    def with_anthropic_tokens(
        self, input_tokens: int, output_tokens: int
    ) -> "UsageStatsBuilder":
        self._input_tokens = input_tokens
        self._output_tokens = output_tokens
        return self

    def build_openai(self) -> Mock:
        mock_usage = Mock()
        mock_usage.prompt_tokens = self._prompt_tokens
        mock_usage.completion_tokens = self._completion_tokens
        mock_usage.total_tokens = self._total_tokens
        return mock_usage

    def build_anthropic(self) -> Mock:
        mock_usage = Mock()
        if self._input_tokens is not None:
            mock_usage.input_tokens = self._input_tokens
        if self._output_tokens is not None:
            mock_usage.output_tokens = self._output_tokens
        return mock_usage


class MessageBuilder:
    """Builder for creating LLM messages (reusable from conversation cache tests)"""

    def __init__(self):
        self._role = "user"
        self._content = "Hello"

    def with_role(self, role: str) -> "MessageBuilder":
        self._role = role
        return self

    def with_content(self, content: str) -> "MessageBuilder":
        self._content = content
        return self

    def build(self) -> dict[str, Any]:
        return {"role": self._role, "content": self._content}

    @classmethod
    def user_message(cls, content: str = "Hello") -> "MessageBuilder":
        return cls().with_role("user").with_content(content)

    @classmethod
    def system_message(cls, content: str = "You are helpful") -> "MessageBuilder":
        return cls().with_role("system").with_content(content)

    @classmethod
    def assistant_message(cls, content: str = "Hi there!") -> "MessageBuilder":
        return cls().with_role("assistant").with_content(content)


# Response Mock Factories
class OpenAIResponseFactory:
    """Factory for creating OpenAI API response mocks"""

    @staticmethod
    def create_successful_response(
        content: str = "Test response", usage_stats: UsageStatsBuilder | None = None
    ) -> Mock:
        """Create a successful OpenAI response mock"""
        mock_choice = Mock()
        mock_choice.message.content = content

        mock_response = Mock()
        mock_response.choices = [mock_choice]

        if usage_stats:
            mock_response.usage = usage_stats.build_openai()
        else:
            mock_response.usage = UsageStatsBuilder().build_openai()

        return mock_response

    @staticmethod
    def create_response_without_usage(content: str = "Response") -> Mock:
        """Create OpenAI response without usage stats"""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = content
        mock_response.usage = None
        return mock_response

    @staticmethod
    def create_empty_response() -> Mock:
        """Create OpenAI response with empty content"""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = None
        mock_response.usage = None
        return mock_response

    @staticmethod
    def create_error_response(error_message: str = "API Error") -> Exception:
        """Create an exception for error scenarios"""
        return Exception(error_message)


class AnthropicResponseFactory:
    """Factory for creating Anthropic API response mocks"""

    @staticmethod
    def create_successful_response(
        content: str = "Test response", usage_stats: UsageStatsBuilder | None = None
    ) -> Mock:
        """Create a successful Anthropic response mock"""
        mock_content = Mock()
        mock_content.text = content

        mock_response = Mock()
        mock_response.content = [mock_content]

        if usage_stats:
            mock_response.usage = usage_stats.build_anthropic()
        else:
            mock_response.usage = (
                UsageStatsBuilder().with_anthropic_tokens(20, 10).build_anthropic()
            )

        return mock_response

    @staticmethod
    def create_response_without_usage(content: str = "Response") -> Mock:
        """Create Anthropic response without usage stats"""
        mock_response = Mock()
        mock_response.content = [Mock()]
        mock_response.content[0].text = content
        mock_response.usage = None
        return mock_response

    @staticmethod
    def create_response_with_usage(
        content: str = "Response", input_tokens: int = 10, output_tokens: int = 5
    ) -> Mock:
        """Create Anthropic response with usage stats"""
        mock_response = Mock()
        mock_response.content = [Mock()]
        mock_response.content[0].text = content
        mock_response.usage = (
            UsageStatsBuilder()
            .with_anthropic_tokens(input_tokens, output_tokens)
            .build_anthropic()
        )
        return mock_response

    @staticmethod
    def create_error_response(error_message: str = "API Error") -> Exception:
        """Create an exception for error scenarios"""
        return Exception(error_message)


class OllamaResponseFactory:
    """Factory for creating Ollama API response mocks"""

    @staticmethod
    def create_successful_response(content: str = "Test response") -> dict[str, Any]:
        """Create a successful Ollama response"""
        return {"message": {"role": "assistant", "content": content}, "done": True}

    @staticmethod
    def create_http_response_mock(json_data: dict[str, Any], status: int = 200) -> Mock:
        """Create HTTP response mock for Ollama"""
        mock_response = Mock()
        mock_response.status = status
        mock_response.json = AsyncMock(return_value=json_data)
        return mock_response

    @staticmethod
    def create_error_response(
        status: int = 500, error_text: str = "Internal server error"
    ) -> Mock:
        """Create error HTTP response for Ollama"""
        mock_response = AsyncMock()
        mock_response.status = status
        mock_response.text = AsyncMock(return_value=error_text)
        return mock_response


class SessionMockFactory:
    """Factory for creating session and client mocks"""

    @staticmethod
    def create_http_session() -> Mock:
        """Create basic HTTP session mock"""
        mock_session = Mock()
        mock_session.closed = False
        return mock_session

    @staticmethod
    def create_async_session() -> AsyncMock:
        """Create async HTTP session mock"""
        mock_session = AsyncMock()
        return mock_session

    @staticmethod
    def create_client_mock() -> Mock:
        """Create client mock for OpenAI/Anthropic"""
        client_mock = Mock()
        client_mock._client = Mock()
        client_mock.close = AsyncMock()
        return client_mock

    @staticmethod
    def create_langfuse_mock() -> Mock:
        """Create Langfuse service mock"""
        langfuse_mock = Mock()
        langfuse_mock.trace_llm_call = Mock()
        return langfuse_mock


class AsyncContextFactory:
    """Factory for creating async context managers"""

    @staticmethod
    def create_http_context(response_mock: Mock) -> AsyncMock:
        """Create async HTTP context manager"""
        async_context_mock = AsyncMock()
        async_context_mock.__aenter__ = AsyncMock(return_value=response_mock)
        async_context_mock.__aexit__ = AsyncMock(return_value=None)
        return async_context_mock


class LLMProviderFactory:
    """Factory for creating LLM provider instances with mocked clients"""

    @staticmethod
    def create_openai_provider(settings: LLMSettings | None = None) -> OpenAIProvider:
        """Create OpenAI provider with mocked client"""
        if settings is None:
            settings = LLMSettingsBuilder.openai().build()

        with patch("bot.services.llm_providers.AsyncOpenAI"):
            return OpenAIProvider(settings)

    @staticmethod
    def create_anthropic_provider(
        settings: LLMSettings | None = None,
    ) -> AnthropicProvider:
        """Create Anthropic provider with mocked client"""
        if settings is None:
            settings = LLMSettingsBuilder.anthropic().build()

        with patch("bot.services.llm_providers.AsyncAnthropic"):
            return AnthropicProvider(settings)

    @staticmethod
    def create_ollama_provider(settings: LLMSettings | None = None) -> OllamaProvider:
        """Create Ollama provider with mocked client"""
        if settings is None:
            settings = LLMSettingsBuilder.ollama().build()

        return OllamaProvider(settings)


class TestLLMProvider:
    """Test cases for abstract LLMProvider base class"""

    def test_llm_provider_is_abstract(self):
        """Test that LLMProvider cannot be instantiated directly"""
        settings = (
            LLMSettingsBuilder().with_provider("test").with_model("test-model").build()
        )
        with pytest.raises(TypeError):
            LLMProvider(settings)


class TestOpenAIProvider:
    """Test cases for OpenAIProvider"""

    @pytest.fixture
    def settings(self):
        """Create OpenAI settings for testing"""
        return (
            LLMSettingsBuilder.openai()
            .with_temperature(0.7)
            .with_max_tokens(1000)
            .build()
        )

    @pytest.fixture
    def provider(self, settings):
        """Create OpenAI provider for testing"""
        return LLMProviderFactory.create_openai_provider(settings)

    def test_init_basic(self, settings):
        """Test basic initialization"""
        with patch("bot.services.llm_providers.AsyncOpenAI") as mock_openai:
            provider = OpenAIProvider(settings)

            mock_openai.assert_called_once_with(api_key="test-openai-key")
            assert provider.model == "gpt-4"
            assert provider.temperature == 0.7
            assert provider.max_tokens == 1000

    def test_init_with_base_url(self):
        """Test initialization with custom base URL"""
        settings = (
            LLMSettingsBuilder.openai()
            .with_api_key("key")
            .with_base_url("https://custom.openai.com")
            .build()
        )

        with patch("bot.services.llm_providers.AsyncOpenAI") as mock_openai:
            OpenAIProvider(settings)

            mock_openai.assert_called_once_with(
                api_key="key", base_url="https://custom.openai.com"
            )

    @pytest.mark.asyncio
    async def test_get_response_success(self, provider):
        """Test successful response generation"""
        # Create mock response using factory
        usage_stats = (
            UsageStatsBuilder().with_prompt_tokens(10).with_completion_tokens(5)
        )
        mock_response = OpenAIResponseFactory.create_successful_response(
            "Test response", usage_stats
        )

        provider.client.chat.completions.create = AsyncMock(return_value=mock_response)

        messages = [MessageBuilder.user_message("Hello").build()]
        response = await provider.get_response(messages, "You are helpful")

        assert response == "Test response"
        provider.client.chat.completions.create.assert_called_once()
        call_args = provider.client.chat.completions.create.call_args[1]
        assert call_args["model"] == "gpt-4"
        assert call_args["temperature"] == 0.7
        assert call_args["max_tokens"] == 1000
        assert len(call_args["messages"]) == 2  # system + user message

    @pytest.mark.asyncio
    async def test_get_response_with_session_metadata(self, provider):
        """Test response generation with session metadata"""
        mock_response = OpenAIResponseFactory.create_response_without_usage("Response")

        provider.client.chat.completions.create = AsyncMock(return_value=mock_response)

        messages = [MessageBuilder.user_message("Hello").build()]
        await provider.get_response(
            messages,
            session_id="session123",
            user_id="user456",
        )

        call_args = provider.client.chat.completions.create.call_args[1]
        assert "metadata" in call_args
        assert call_args["metadata"]["langfuse_session_id"] == "session123"
        assert call_args["metadata"]["langfuse_user_id"] == "user456"

    @pytest.mark.asyncio
    async def test_get_response_error(self, provider):
        """Test error handling in response generation"""
        provider.client.chat.completions.create = AsyncMock(
            side_effect=OpenAIResponseFactory.create_error_response("API Error")
        )

        messages = [MessageBuilder.user_message("Hello").build()]
        response = await provider.get_response(messages)

        assert response is None

    @pytest.mark.asyncio
    async def test_get_response_empty_content(self, provider):
        """Test handling of empty response content"""
        mock_response = OpenAIResponseFactory.create_empty_response()

        provider.client.chat.completions.create = AsyncMock(return_value=mock_response)

        messages = [MessageBuilder.user_message("Hello").build()]
        response = await provider.get_response(messages)

        assert response is None

    @pytest.mark.asyncio
    async def test_close(self, provider):
        """Test closing the provider"""
        provider.client = SessionMockFactory.create_client_mock()

        await provider.close()

        provider.client.close.assert_called_once()


class TestAnthropicProvider:
    """Test cases for AnthropicProvider"""

    @pytest.fixture
    def settings(self):
        """Create Anthropic settings for testing"""
        return (
            LLMSettingsBuilder.anthropic("claude-3-haiku-20240307")
            .with_temperature(0.5)
            .with_max_tokens(2000)
            .build()
        )

    @pytest.fixture
    def provider(self, settings):
        """Create Anthropic provider for testing"""
        return LLMProviderFactory.create_anthropic_provider(settings)

    def test_init(self, settings):
        """Test initialization"""
        with patch("bot.services.llm_providers.AsyncAnthropic") as mock_anthropic:
            provider = AnthropicProvider(settings)

            mock_anthropic.assert_called_once_with(api_key="test-anthropic-key")
            assert provider.model == "claude-3-haiku-20240307"

    @pytest.mark.asyncio
    async def test_get_response_success(self, provider):
        """Test successful response generation"""
        # Create mock response using factory
        usage_stats = UsageStatsBuilder().with_anthropic_tokens(20, 10)
        mock_response = AnthropicResponseFactory.create_successful_response(
            "Anthropic response", usage_stats
        )

        provider.client.messages.create = AsyncMock(return_value=mock_response)

        with patch(
            "bot.services.llm_providers.get_langfuse_service", return_value=None
        ):
            messages = [MessageBuilder.user_message("Hello").build()]
            response = await provider.get_response(messages, "You are Claude")

            assert response == "Anthropic response"
            provider.client.messages.create.assert_called_once()
            call_args = provider.client.messages.create.call_args[1]
            assert call_args["model"] == "claude-3-haiku-20240307"
            assert call_args["system"] == "You are Claude"
            assert len(call_args["messages"]) == 1

    @pytest.mark.asyncio
    async def test_get_response_filters_messages(self, provider):
        """Test that only user/assistant messages are included"""
        mock_response = AnthropicResponseFactory.create_response_without_usage(
            "Response"
        )

        provider.client.messages.create = AsyncMock(return_value=mock_response)

        with patch(
            "bot.services.llm_providers.get_langfuse_service", return_value=None
        ):
            messages = [
                MessageBuilder.system_message(
                    "System message"
                ).build(),  # Should be filtered
                MessageBuilder.user_message("User message").build(),
                MessageBuilder.assistant_message("Assistant message").build(),
                {"role": "tool", "content": "Tool message"},  # Should be filtered
            ]

            await provider.get_response(messages)

            call_args = provider.client.messages.create.call_args[1]
            # Only user and assistant messages should remain
            assert len(call_args["messages"]) == 2
            assert call_args["messages"][0]["role"] == "user"
            assert call_args["messages"][1]["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_get_response_with_langfuse(self, provider):
        """Test response generation with Langfuse tracing"""
        mock_response = AnthropicResponseFactory.create_response_with_usage(
            "Response", input_tokens=10, output_tokens=5
        )

        provider.client.messages.create = AsyncMock(return_value=mock_response)

        langfuse_mock = SessionMockFactory.create_langfuse_mock()
        with patch(
            "bot.services.llm_providers.get_langfuse_service",
            return_value=langfuse_mock,
        ):
            messages = [MessageBuilder.user_message("Hello").build()]
            await provider.get_response(messages)

            langfuse_mock.trace_llm_call.assert_called_once()
            call_args = langfuse_mock.trace_llm_call.call_args[1]
            assert call_args["provider"] == "anthropic"
            assert call_args["model"] == "claude-3-haiku-20240307"
            assert call_args["response"] == "Response"

    @pytest.mark.asyncio
    async def test_get_response_error(self, provider):
        """Test error handling"""
        provider.client.messages.create = AsyncMock(side_effect=Exception("API Error"))

        with patch(
            "bot.services.llm_providers.get_langfuse_service", return_value=None
        ):
            response = await provider.get_response(
                [{"role": "user", "content": "Hello"}]
            )

            assert response is None

    @pytest.mark.asyncio
    async def test_close(self, provider):
        """Test closing the provider"""
        provider.client = SessionMockFactory.create_client_mock()

        await provider.close()

        provider.client.close.assert_called_once()


class TestOllamaProvider:
    """Test cases for OllamaProvider"""

    @pytest.fixture
    def settings(self):
        """Create Ollama settings for testing"""
        return (
            LLMSettingsBuilder.ollama("llama2")
            .with_temperature(0.8)
            .with_max_tokens(500)
            .build()
        )

    @pytest.fixture
    def provider(self, settings):
        """Create Ollama provider for testing"""
        return LLMProviderFactory.create_ollama_provider(settings)

    def test_init(self, settings):
        """Test initialization"""
        provider = OllamaProvider(settings)
        assert provider.base_url == "http://localhost:11434"
        assert provider.model == "llama2"
        assert provider.session is None

    def test_init_default_base_url(self):
        """Test initialization with default base URL"""
        settings = LLMSettingsBuilder.ollama("llama2").build()
        provider = OllamaProvider(settings)
        assert provider.base_url == "http://localhost:11434"

    @pytest.mark.asyncio
    async def test_ensure_session_creates_new(self, provider):
        """Test session creation"""
        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = SessionMockFactory.create_http_session()
            mock_session_class.return_value = mock_session

            session = await provider.ensure_session()

            assert session == mock_session
            assert provider.session == mock_session
            mock_session_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_ensure_session_reuses_existing(self, provider):
        """Test session reuse"""
        mock_session = SessionMockFactory.create_http_session()
        provider.session = mock_session

        session = await provider.ensure_session()

        assert session == mock_session

    @pytest.mark.asyncio
    async def test_get_response_success(self, provider):
        """Test successful response generation"""
        # Create the mock response using factory
        json_data = OllamaResponseFactory.create_successful_response("Ollama response")
        mock_response = OllamaResponseFactory.create_http_response_mock(json_data, 200)

        # Create async context manager mock
        async_context_mock = AsyncContextFactory.create_http_context(mock_response)

        mock_session = SessionMockFactory.create_async_session()
        mock_session.post = Mock(return_value=async_context_mock)

        with (
            patch.object(provider, "ensure_session", return_value=mock_session),
            patch("bot.services.llm_providers.get_langfuse_service", return_value=None),
        ):
            messages = [MessageBuilder.user_message("Hello").build()]
            response = await provider.get_response(messages, "You are helpful")

            assert response == "Ollama response"
            mock_session.post.assert_called_once_with(
                "http://localhost:11434/api/chat",
                json={
                    "model": "llama2",
                    "messages": [
                        {"role": "system", "content": "You are helpful"},
                        {"role": "user", "content": "Hello"},
                    ],
                    "options": {"temperature": 0.8, "num_predict": 500},
                },
            )

    @pytest.mark.asyncio
    async def test_get_response_http_error(self, provider):
        """Test HTTP error handling"""
        mock_session = SessionMockFactory.create_async_session()
        mock_response = OllamaResponseFactory.create_error_response(
            500, "Internal server error"
        )
        mock_session.post.return_value.__aenter__.return_value = mock_response

        with (
            patch.object(provider, "ensure_session", return_value=mock_session),
            patch("bot.services.llm_providers.get_langfuse_service", return_value=None),
        ):
            messages = [MessageBuilder.user_message("Hello").build()]
            response = await provider.get_response(messages)

            assert response is None

    @pytest.mark.asyncio
    async def test_get_response_exception(self, provider):
        """Test exception handling"""
        with (
            patch.object(
                provider, "ensure_session", side_effect=Exception("Network error")
            ),
            patch("bot.services.llm_providers.get_langfuse_service", return_value=None),
        ):
            response = await provider.get_response(
                [{"role": "user", "content": "Hello"}]
            )

            assert response is None

    @pytest.mark.asyncio
    async def test_get_response_with_langfuse(self, provider):
        """Test response with Langfuse tracing"""
        mock_session = SessionMockFactory.create_async_session()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={"message": {"content": "Response"}}
        )
        mock_session.post.return_value.__aenter__.return_value = mock_response

        langfuse_mock = SessionMockFactory.create_langfuse_mock()

        with (
            patch.object(provider, "ensure_session", return_value=mock_session),
            patch(
                "bot.services.llm_providers.get_langfuse_service",
                return_value=langfuse_mock,
            ),
        ):
            await provider.get_response([{"role": "user", "content": "Hello"}])

            langfuse_mock.trace_llm_call.assert_called_once()
            call_args = langfuse_mock.trace_llm_call.call_args[1]
            assert call_args["provider"] == "ollama"
            assert call_args["model"] == "llama2"

    @pytest.mark.asyncio
    async def test_close_with_session(self, provider):
        """Test closing with active session"""
        mock_session = SessionMockFactory.create_async_session()
        mock_session.closed = False
        provider.session = mock_session

        await provider.close()

        mock_session.close.assert_called_once()
        assert provider.session is None

    @pytest.mark.asyncio
    async def test_close_without_session(self, provider):
        """Test closing without session"""
        await provider.close()  # Should not raise error
        assert provider.session is None


class TestCreateLLMProvider:
    """Test cases for provider factory function"""

    def test_create_openai_provider(self):
        """Test creating OpenAI provider"""
        settings = LLMSettingsBuilder.openai("gpt-4").with_api_key("key").build()

        with patch("bot.services.llm_providers.AsyncOpenAI"):
            provider = create_llm_provider(settings)

            assert isinstance(provider, OpenAIProvider)

    def test_create_anthropic_provider(self):
        """Test creating Anthropic provider"""
        settings = (
            LLMSettingsBuilder.anthropic("claude-3-haiku-20240307")
            .with_api_key("key")
            .build()
        )

        with patch("bot.services.llm_providers.AsyncAnthropic"):
            provider = create_llm_provider(settings)

            assert isinstance(provider, AnthropicProvider)

    def test_create_ollama_provider(self):
        """Test creating Ollama provider"""
        settings = LLMSettingsBuilder.ollama("llama2").build()

        provider = create_llm_provider(settings)

        assert isinstance(provider, OllamaProvider)

    def test_create_unsupported_provider(self):
        """Test creating unsupported provider"""
        settings = (
            LLMSettingsBuilder()
            .with_provider("unsupported")
            .with_api_key("key")
            .with_model("model")
            .build()
        )

        with pytest.raises(ValueError, match="Unsupported LLM provider"):
            create_llm_provider(settings)

    def test_case_insensitive_provider_names(self):
        """Test that provider names are case-insensitive"""
        settings = LLMSettings(
            provider="OPENAI",  # Uppercase
            api_key=SecretStr("key"),
            model="gpt-4",
        )

        with patch("bot.services.llm_providers.AsyncOpenAI"):
            provider = create_llm_provider(settings)

            assert isinstance(provider, OpenAIProvider)
