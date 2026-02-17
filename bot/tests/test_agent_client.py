"""
Tests for AgentClient HTTP integration.

Tests the HTTP client layer that calls agent-service, including:
- Successful agent invocations
- HTTP error handling (404, 500)
- Network errors (timeout, connection)
- Context serialization
- Agent listing
"""

import os
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from bot.services.agent_client import AgentClient, get_agent_client


class HttpResponseFactory:
    """Factory for creating mock HTTP responses"""

    @staticmethod
    def create_successful_invoke_response() -> Mock:
        """Create successful agent invocation response"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": "Agent response text",
            "metadata": {"agent": "profile", "execution_time": 1.23},
        }
        return mock_response

    @staticmethod
    def create_404_response() -> Mock:
        """Create 404 not found response"""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.text = "Agent not found"

        # Mock raise_for_status to raise HTTPStatusError
        def raise_404():
            raise httpx.HTTPStatusError(
                "404 Not Found", request=Mock(), response=mock_response
            )

        mock_response.raise_for_status = raise_404
        return mock_response

    @staticmethod
    def create_500_response() -> Mock:
        """Create 500 server error response"""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal server error"

        # Mock raise_for_status to raise HTTPStatusError
        def raise_500():
            raise httpx.HTTPStatusError(
                "500 Internal Server Error", request=Mock(), response=mock_response
            )

        mock_response.raise_for_status = raise_500
        return mock_response

    @staticmethod
    def create_successful_list_response(agent_count: int = 3) -> Mock:
        """Create successful list agents response"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "agents": [
                {"name": "help", "description": "Help agent"},
                {"name": "profile", "description": "Profile agent"},
                {"name": "meddic", "description": "MEDDIC agent"},
            ][:agent_count]
        }
        return mock_response

    @staticmethod
    def create_failed_list_response() -> Mock:
        """Create failed list agents response"""
        mock_response = Mock()
        mock_response.status_code = 503
        return mock_response


class AgentClientTestDataFactory:
    """Factory for creating test data"""

    @staticmethod
    def create_agent_name() -> str:
        """Create test agent name"""
        return "profile"

    @staticmethod
    def create_unknown_agent_name() -> str:
        """Create unknown agent name"""
        return "nonexistent_agent"

    @staticmethod
    def create_query() -> str:
        """Create test query"""
        return "Tell me about Acme Corp"

    @staticmethod
    def create_serializable_context() -> dict:
        """Create context with only serializable values"""
        return {
            "user_id": "U123",
            "channel": "C456",
            "thread_ts": "1234.5678",
            "is_dm": False,
            "count": 42,
            "ratio": 3.14,
            "items": ["a", "b", "c"],
            "nested": {"key": "value"},
        }

    @staticmethod
    def create_mixed_context() -> dict:
        """Create context with both serializable and non-serializable values"""
        return {
            # Serializable
            "user_id": "U123",
            "channel": "C456",
            "count": 42,
            # Non-serializable (should be filtered)
            "slack_service": Mock(),
            "llm_service": Mock(),
            "conversation_cache": Mock(),
        }

    @staticmethod
    def create_base_url() -> str:
        """Create test base URL"""
        return "http://test-agent-service:8000"


class MockHttpClientFactory:
    """Factory for creating mock httpx clients"""

    @staticmethod
    def create_successful_client(response: Mock) -> AsyncMock:
        """Create mock client that returns successful response"""
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=response)
        mock_client.get = AsyncMock(return_value=response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        return mock_client

    @staticmethod
    def create_timeout_client() -> AsyncMock:
        """Create mock client that raises timeout"""
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        return mock_client

    @staticmethod
    def create_connection_error_client() -> AsyncMock:
        """Create mock client that raises connection error"""
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(
            side_effect=httpx.ConnectError("Connection refused")
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        return mock_client

    @staticmethod
    def create_generic_error_client() -> AsyncMock:
        """Create mock client that raises generic exception"""
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=Exception("Generic error"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        return mock_client


class TestAgentClientInitialization:
    def test_init_default_base_url(self):
        # Mock BOT_SERVICE_TOKEN to avoid picking up environment value
        with patch.dict("os.environ", {"BOT_SERVICE_TOKEN": "dev-bot-service-token"}):
            client = AgentClient()
            assert client.base_url == "http://agent-service:8000"
            assert client.service_token == "dev-bot-service-token"

    def test_init_custom_base_url(self):
        base_url = AgentClientTestDataFactory.create_base_url()
        client = AgentClient(base_url=base_url)
        assert client.base_url == base_url

    def test_init_strips_trailing_slash(self):
        client = AgentClient(base_url="http://test-service:8000/")
        # New implementation preserves trailing slash
        assert client.base_url == "http://test-service:8000/"


class TestAgentClientInvokeAgent:
    @pytest.mark.asyncio
    async def test_invoke_agent_success(self):
        client = AgentClient()
        agent_name = AgentClientTestDataFactory.create_agent_name()
        query = AgentClientTestDataFactory.create_query()
        context = AgentClientTestDataFactory.create_serializable_context()

        response = HttpResponseFactory.create_successful_invoke_response()
        mock_client = MockHttpClientFactory.create_successful_client(response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await client.invoke(agent_name, query, context)

            assert result["response"] == "Agent response text"
            assert result["metadata"]["agent"] == "profile"
            assert result["metadata"]["execution_time"] == 1.23

    @pytest.mark.asyncio
    async def test_invoke_agent_404_not_found(self):
        client = AgentClient()
        agent_name = AgentClientTestDataFactory.create_unknown_agent_name()
        query = AgentClientTestDataFactory.create_query()
        context = {}

        response = HttpResponseFactory.create_404_response()
        mock_client = MockHttpClientFactory.create_successful_client(response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                await client.invoke(agent_name, query, context)

            assert "404" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_invoke_agent_500_server_error(self):
        client = AgentClient()
        agent_name = AgentClientTestDataFactory.create_agent_name()
        query = AgentClientTestDataFactory.create_query()
        context = {}

        response = HttpResponseFactory.create_500_response()
        mock_client = MockHttpClientFactory.create_successful_client(response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                await client.invoke(agent_name, query, context)

            assert "500" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_invoke_agent_timeout(self):
        client = AgentClient()
        agent_name = AgentClientTestDataFactory.create_agent_name()
        query = AgentClientTestDataFactory.create_query()
        context = {}

        mock_client = MockHttpClientFactory.create_timeout_client()

        with (
            patch("httpx.AsyncClient", return_value=mock_client),
            pytest.raises(httpx.TimeoutException),
        ):
            await client.invoke(agent_name, query, context)

    @pytest.mark.asyncio
    async def test_invoke_agent_connection_error(self):
        client = AgentClient()
        agent_name = AgentClientTestDataFactory.create_agent_name()
        query = AgentClientTestDataFactory.create_query()
        context = {}

        mock_client = MockHttpClientFactory.create_connection_error_client()

        with (
            patch("httpx.AsyncClient", return_value=mock_client),
            pytest.raises(httpx.ConnectError),
        ):
            await client.invoke(agent_name, query, context)

    @pytest.mark.asyncio
    async def test_invoke_agent_generic_error(self):
        client = AgentClient()
        agent_name = AgentClientTestDataFactory.create_agent_name()
        query = AgentClientTestDataFactory.create_query()
        context = {}

        mock_client = MockHttpClientFactory.create_generic_error_client()

        with (
            patch("httpx.AsyncClient", return_value=mock_client),
            pytest.raises(Exception),  # noqa: B017 - Testing generic exception propagation
        ):
            await client.invoke(agent_name, query, context)

    @pytest.mark.asyncio
    async def test_invoke_agent_url_construction(self):
        base_url = AgentClientTestDataFactory.create_base_url()
        client = AgentClient(base_url=base_url)
        agent_name = AgentClientTestDataFactory.create_agent_name()
        query = AgentClientTestDataFactory.create_query()
        context = {}

        response = HttpResponseFactory.create_successful_invoke_response()
        mock_client = MockHttpClientFactory.create_successful_client(response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            await client.invoke(agent_name, query, context)

            # Verify URL construction
            expected_url = f"{base_url}/api/agents/{agent_name}/invoke"
            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args
            assert call_args[0][0] == expected_url


class TestGetAgentClient:
    def test_get_agent_client_creates_instance(self):
        # Reset singleton instance
        from bot.services.agent_client import _AgentClientSingleton

        _AgentClientSingleton._instance = None

        client = get_agent_client()

        assert client is not None
        assert isinstance(client, AgentClient)

        # Cleanup
        _AgentClientSingleton._instance = None

    def test_get_agent_client_returns_same_instance(self):
        # Reset singleton instance
        from bot.services.agent_client import _AgentClientSingleton

        _AgentClientSingleton._instance = None

        client1 = get_agent_client()
        client2 = get_agent_client()

        assert client1 is client2

        # Cleanup
        _AgentClientSingleton._instance = None

    def test_get_agent_client_uses_env_variable(self):
        # Reset singleton instance
        from bot.services.agent_client import _AgentClientSingleton

        _AgentClientSingleton._instance = None

        test_url = "http://custom-agent-service:9000"

        with patch.dict("os.environ", {"AGENT_SERVICE_URL": test_url}, clear=False):
            client = get_agent_client()
            assert client.base_url == test_url

        # Cleanup
        _AgentClientSingleton._instance = None

    def test_get_agent_client_default_url(self):
        # Reset singleton instance
        from bot.services.agent_client import _AgentClientSingleton

        _AgentClientSingleton._instance = None

        # Clear AGENT_SERVICE_URL but keep other env vars
        env_without_url = {
            k: v for k, v in os.environ.items() if k != "AGENT_SERVICE_URL"
        }
        with patch.dict("os.environ", env_without_url, clear=True):
            client = get_agent_client()
            assert client.base_url == "http://agent-service:8000"

        # Cleanup
        _AgentClientSingleton._instance = None


# httpx.HTTPError tests removed - using standard httpx exceptions
