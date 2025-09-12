"""
Tests for LLM provider implementations.

Tests OpenAI, Anthropic, and Ollama providers with proper mocking.
"""

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


class TestLLMProvider:
    """Test cases for abstract LLMProvider base class"""

    def test_llm_provider_is_abstract(self):
        """Test that LLMProvider cannot be instantiated directly"""
        settings = LLMSettings(
            provider="test",
            api_key=SecretStr("key"),
            model="test-model"
        )
        with pytest.raises(TypeError):
            LLMProvider(settings)


class TestOpenAIProvider:
    """Test cases for OpenAIProvider"""

    @pytest.fixture
    def settings(self):
        """Create OpenAI settings for testing"""
        return LLMSettings(
            provider="openai",
            api_key=SecretStr("test-openai-key"),
            model="gpt-4",
            temperature=0.7,
            max_tokens=1000
        )

    @pytest.fixture
    def provider(self, settings):
        """Create OpenAI provider for testing"""
        with patch('bot.services.llm_providers.AsyncOpenAI'):
            return OpenAIProvider(settings)

    def test_init_basic(self, settings):
        """Test basic initialization"""
        with patch('bot.services.llm_providers.AsyncOpenAI') as mock_openai:
            provider = OpenAIProvider(settings)

            mock_openai.assert_called_once_with(api_key="test-openai-key")
            assert provider.model == "gpt-4"
            assert provider.temperature == 0.7
            assert provider.max_tokens == 1000

    def test_init_with_base_url(self):
        """Test initialization with custom base URL"""
        settings = LLMSettings(
            provider="openai",
            api_key=SecretStr("key"),
            model="gpt-4",
            base_url="https://custom.openai.com"
        )

        with patch('bot.services.llm_providers.AsyncOpenAI') as mock_openai:
            OpenAIProvider(settings)

            mock_openai.assert_called_once_with(
                api_key="key",
                base_url="https://custom.openai.com"
            )

    @pytest.mark.asyncio
    async def test_get_response_success(self, provider):
        """Test successful response generation"""
        # Mock response
        mock_choice = Mock()
        mock_choice.message.content = "Test response"
        mock_usage = Mock()
        mock_usage.prompt_tokens = 10
        mock_usage.completion_tokens = 5
        mock_usage.total_tokens = 15
        mock_response = Mock()
        mock_response.choices = [mock_choice]
        mock_response.usage = mock_usage

        provider.client.chat.completions.create = AsyncMock(return_value=mock_response)

        messages = [{"role": "user", "content": "Hello"}]
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
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Response"
        mock_response.usage = None

        provider.client.chat.completions.create = AsyncMock(return_value=mock_response)

        await provider.get_response(
            [{"role": "user", "content": "Hello"}],
            session_id="session123",
            user_id="user456"
        )

        call_args = provider.client.chat.completions.create.call_args[1]
        assert "metadata" in call_args
        assert call_args["metadata"]["langfuse_session_id"] == "session123"
        assert call_args["metadata"]["langfuse_user_id"] == "user456"

    @pytest.mark.asyncio
    async def test_get_response_error(self, provider):
        """Test error handling in response generation"""
        provider.client.chat.completions.create = AsyncMock(side_effect=Exception("API Error"))

        response = await provider.get_response([{"role": "user", "content": "Hello"}])

        assert response is None

    @pytest.mark.asyncio
    async def test_get_response_empty_content(self, provider):
        """Test handling of empty response content"""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = None
        mock_response.usage = None

        provider.client.chat.completions.create = AsyncMock(return_value=mock_response)

        response = await provider.get_response([{"role": "user", "content": "Hello"}])

        assert response is None

    @pytest.mark.asyncio
    async def test_close(self, provider):
        """Test closing the provider"""
        provider.client._client = Mock()
        provider.client.close = AsyncMock()

        await provider.close()

        provider.client.close.assert_called_once()


class TestAnthropicProvider:
    """Test cases for AnthropicProvider"""

    @pytest.fixture
    def settings(self):
        """Create Anthropic settings for testing"""
        return LLMSettings(
            provider="anthropic",
            api_key=SecretStr("test-anthropic-key"),
            model="claude-3-haiku-20240307",
            temperature=0.5,
            max_tokens=2000
        )

    @pytest.fixture
    def provider(self, settings):
        """Create Anthropic provider for testing"""
        with patch('bot.services.llm_providers.AsyncAnthropic'):
            return AnthropicProvider(settings)

    def test_init(self, settings):
        """Test initialization"""
        with patch('bot.services.llm_providers.AsyncAnthropic') as mock_anthropic:
            provider = AnthropicProvider(settings)

            mock_anthropic.assert_called_once_with(api_key="test-anthropic-key")
            assert provider.model == "claude-3-haiku-20240307"

    @pytest.mark.asyncio
    async def test_get_response_success(self, provider):
        """Test successful response generation"""
        # Mock response
        mock_content = Mock()
        mock_content.text = "Anthropic response"
        mock_usage = Mock()
        mock_usage.input_tokens = 20
        mock_usage.output_tokens = 10
        mock_response = Mock()
        mock_response.content = [mock_content]
        mock_response.usage = mock_usage

        provider.client.messages.create = AsyncMock(return_value=mock_response)

        with patch('bot.services.llm_providers.get_langfuse_service', return_value=None):
            messages = [{"role": "user", "content": "Hello"}]
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
        mock_response = Mock()
        mock_response.content = [Mock()]
        mock_response.content[0].text = "Response"
        mock_response.usage = None

        provider.client.messages.create = AsyncMock(return_value=mock_response)

        with patch('bot.services.llm_providers.get_langfuse_service', return_value=None):
            messages = [
                {"role": "system", "content": "System message"},  # Should be filtered
                {"role": "user", "content": "User message"},
                {"role": "assistant", "content": "Assistant message"},
                {"role": "tool", "content": "Tool message"}  # Should be filtered
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
        mock_response = Mock()
        mock_response.content = [Mock()]
        mock_response.content[0].text = "Response"
        mock_response.usage = Mock()
        mock_response.usage.input_tokens = 10
        mock_response.usage.output_tokens = 5

        provider.client.messages.create = AsyncMock(return_value=mock_response)

        mock_langfuse = Mock()
        with patch('bot.services.llm_providers.get_langfuse_service', return_value=mock_langfuse):
            await provider.get_response([{"role": "user", "content": "Hello"}])

            mock_langfuse.trace_llm_call.assert_called_once()
            call_args = mock_langfuse.trace_llm_call.call_args[1]
            assert call_args["provider"] == "anthropic"
            assert call_args["model"] == "claude-3-haiku-20240307"
            assert call_args["response"] == "Response"

    @pytest.mark.asyncio
    async def test_get_response_error(self, provider):
        """Test error handling"""
        provider.client.messages.create = AsyncMock(side_effect=Exception("API Error"))

        with patch('bot.services.llm_providers.get_langfuse_service', return_value=None):
            response = await provider.get_response([{"role": "user", "content": "Hello"}])

            assert response is None

    @pytest.mark.asyncio
    async def test_close(self, provider):
        """Test closing the provider"""
        provider.client._client = Mock()
        provider.client.close = AsyncMock()

        await provider.close()

        provider.client.close.assert_called_once()


class TestOllamaProvider:
    """Test cases for OllamaProvider"""

    @pytest.fixture
    def settings(self):
        """Create Ollama settings for testing"""
        return LLMSettings(
            provider="ollama",
            api_key=SecretStr("not-used"),
            model="llama2",
            base_url="http://localhost:11434",
            temperature=0.8,
            max_tokens=500
        )

    @pytest.fixture
    def provider(self, settings):
        """Create Ollama provider for testing"""
        return OllamaProvider(settings)

    def test_init(self, settings):
        """Test initialization"""
        provider = OllamaProvider(settings)
        assert provider.base_url == "http://localhost:11434"
        assert provider.model == "llama2"
        assert provider.session is None

    def test_init_default_base_url(self):
        """Test initialization with default base URL"""
        settings = LLMSettings(
            provider="ollama",
            api_key=SecretStr("not-used"),
            model="llama2"
        )
        provider = OllamaProvider(settings)
        assert provider.base_url == "http://localhost:11434"

    @pytest.mark.asyncio
    async def test_ensure_session_creates_new(self, provider):
        """Test session creation"""
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = Mock()
            mock_session_class.return_value = mock_session

            session = await provider.ensure_session()

            assert session == mock_session
            assert provider.session == mock_session
            mock_session_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_ensure_session_reuses_existing(self, provider):
        """Test session reuse"""
        mock_session = Mock()
        mock_session.closed = False
        provider.session = mock_session

        session = await provider.ensure_session()

        assert session == mock_session

    @pytest.mark.asyncio
    async def test_get_response_success(self, provider):
        """Test successful response generation"""
        mock_session = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "message": {"content": "Ollama response"}
        })
        mock_session.post.return_value.__aenter__.return_value = mock_response

        with patch.object(provider, 'ensure_session', return_value=mock_session):
            with patch('bot.services.llm_providers.get_langfuse_service', return_value=None):
                messages = [{"role": "user", "content": "Hello"}]
                response = await provider.get_response(messages, "You are helpful")

                assert response == "Ollama response"
                mock_session.post.assert_called_once_with(
                    "http://localhost:11434/api/chat",
                    json={
                        "model": "llama2",
                        "messages": [
                            {"role": "system", "content": "You are helpful"},
                            {"role": "user", "content": "Hello"}
                        ],
                        "options": {
                            "temperature": 0.8,
                            "num_predict": 500
                        }
                    }
                )

    @pytest.mark.asyncio
    async def test_get_response_http_error(self, provider):
        """Test HTTP error handling"""
        mock_session = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.text = AsyncMock(return_value="Internal server error")
        mock_session.post.return_value.__aenter__.return_value = mock_response

        with patch.object(provider, 'ensure_session', return_value=mock_session):
            with patch('bot.services.llm_providers.get_langfuse_service', return_value=None):
                response = await provider.get_response([{"role": "user", "content": "Hello"}])

                assert response is None

    @pytest.mark.asyncio
    async def test_get_response_exception(self, provider):
        """Test exception handling"""
        with patch.object(provider, 'ensure_session', side_effect=Exception("Network error")):
            with patch('bot.services.llm_providers.get_langfuse_service', return_value=None):
                response = await provider.get_response([{"role": "user", "content": "Hello"}])

                assert response is None

    @pytest.mark.asyncio
    async def test_get_response_with_langfuse(self, provider):
        """Test response with Langfuse tracing"""
        mock_session = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "message": {"content": "Response"}
        })
        mock_session.post.return_value.__aenter__.return_value = mock_response

        mock_langfuse = Mock()

        with patch.object(provider, 'ensure_session', return_value=mock_session):
            with patch('bot.services.llm_providers.get_langfuse_service', return_value=mock_langfuse):
                await provider.get_response([{"role": "user", "content": "Hello"}])

                mock_langfuse.trace_llm_call.assert_called_once()
                call_args = mock_langfuse.trace_llm_call.call_args[1]
                assert call_args["provider"] == "ollama"
                assert call_args["model"] == "llama2"

    @pytest.mark.asyncio
    async def test_close_with_session(self, provider):
        """Test closing with active session"""
        mock_session = AsyncMock()
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
        settings = LLMSettings(
            provider="openai",
            api_key=SecretStr("key"),
            model="gpt-4"
        )

        with patch('bot.services.llm_providers.AsyncOpenAI'):
            provider = create_llm_provider(settings)

            assert isinstance(provider, OpenAIProvider)

    def test_create_anthropic_provider(self):
        """Test creating Anthropic provider"""
        settings = LLMSettings(
            provider="anthropic",
            api_key=SecretStr("key"),
            model="claude-3-haiku-20240307"
        )

        with patch('bot.services.llm_providers.AsyncAnthropic'):
            provider = create_llm_provider(settings)

            assert isinstance(provider, AnthropicProvider)

    def test_create_ollama_provider(self):
        """Test creating Ollama provider"""
        settings = LLMSettings(
            provider="ollama",
            api_key=SecretStr("not-used"),
            model="llama2"
        )

        provider = create_llm_provider(settings)

        assert isinstance(provider, OllamaProvider)

    def test_create_unsupported_provider(self):
        """Test creating unsupported provider"""
        settings = LLMSettings(
            provider="unsupported",
            api_key=SecretStr("key"),
            model="model"
        )

        with pytest.raises(ValueError, match="Unsupported LLM provider"):
            create_llm_provider(settings)

    def test_case_insensitive_provider_names(self):
        """Test that provider names are case-insensitive"""
        settings = LLMSettings(
            provider="OPENAI",  # Uppercase
            api_key=SecretStr("key"),
            model="gpt-4"
        )

        with patch('bot.services.llm_providers.AsyncOpenAI'):
            provider = create_llm_provider(settings)

            assert isinstance(provider, OpenAIProvider)
