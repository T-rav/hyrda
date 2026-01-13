"""
Tests for AgentClient HTTP integration.

Tests the HTTP client layer that calls agent-service, including:
- Successful agent invocations
- HTTP error handling (404, 500)
- Network errors (timeout, connection)
- Context serialization
- Agent listing
"""

from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import httpx
import pytest


# Mock OpenTelemetry before importing agent_client
@contextmanager
def mock_create_span(*args, **kwargs):
    """Mock create_span as a proper context manager."""
    yield MagicMock()


def mock_record_exception(*args, **kwargs):
    """Mock record_exception as a no-op."""
    pass


# Apply mocks before importing
_create_span_patcher = patch(
    "shared.utils.otel_http_client.create_span", side_effect=mock_create_span
)
_record_exception_patcher = patch(
    "shared.utils.otel_http_client.record_exception", side_effect=mock_record_exception
)
_create_span_patcher.start()
_record_exception_patcher.start()

from bot.services.agent_client import AgentClient, get_agent_client


# TDD Factory Patterns for AgentClient Testing
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
        return mock_response

    @staticmethod
    def create_500_response() -> Mock:
        """Create 500 server error response"""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal server error"
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
    """Test AgentClient initialization"""

    def test_init_default_base_url(self):
        """Test initialization with default base URL"""
        client = AgentClient()
        assert client.base_url == "http://agent_service:8000"
        assert client.timeout.read == 30.0  # Reduced from 300.0 to fail fast
        assert client.timeout.connect == 5.0  # Reduced from 10.0
        # Check circuit breaker is initialized
        assert client.circuit_breaker is not None
        assert client.circuit_breaker.failure_threshold == 5

    def test_init_custom_base_url(self):
        """Test initialization with custom base URL"""
        base_url = AgentClientTestDataFactory.create_base_url()
        client = AgentClient(base_url=base_url)
        assert client.base_url == base_url

    def test_init_strips_trailing_slash(self):
        """Test that trailing slash is removed from base URL"""
        client = AgentClient(base_url="http://test-service:8000/")
        assert client.base_url == "http://test-service:8000"


class TestAgentClientInvokeAgent:
    """Test AgentClient.invoke() method"""

    @pytest.mark.asyncio
    async def test_invoke_agent_success(self):
        """Test successful agent invocation"""
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
        """Test agent invocation with 404 error"""
        client = AgentClient()
        agent_name = AgentClientTestDataFactory.create_unknown_agent_name()
        query = AgentClientTestDataFactory.create_query()
        context = {}

        response = HttpResponseFactory.create_404_response()
        mock_client = MockHttpClientFactory.create_successful_client(response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(httpx.HTTPError) as exc_info:
                await client.invoke(agent_name, query, context)

            assert "not found" in str(exc_info.value).lower()
            assert agent_name in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_invoke_agent_500_server_error(self):
        """Test agent invocation with 500 error"""
        client = AgentClient()
        agent_name = AgentClientTestDataFactory.create_agent_name()
        query = AgentClientTestDataFactory.create_query()
        context = {}

        response = HttpResponseFactory.create_500_response()
        mock_client = MockHttpClientFactory.create_successful_client(response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(httpx.HTTPError) as exc_info:
                await client.invoke(agent_name, query, context)

            assert "failed" in str(exc_info.value).lower()
            assert "500" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_invoke_agent_timeout(self):
        """Test agent invocation with timeout error"""
        client = AgentClient()
        agent_name = AgentClientTestDataFactory.create_agent_name()
        query = AgentClientTestDataFactory.create_query()
        context = {}

        mock_client = MockHttpClientFactory.create_timeout_client()

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(httpx.HTTPError) as exc_info:
                await client.invoke(agent_name, query, context)

            assert "timed out" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_invoke_agent_connection_error(self):
        """Test agent invocation with connection error"""
        client = AgentClient()
        agent_name = AgentClientTestDataFactory.create_agent_name()
        query = AgentClientTestDataFactory.create_query()
        context = {}

        mock_client = MockHttpClientFactory.create_connection_error_client()

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(httpx.HTTPError) as exc_info:
                await client.invoke(agent_name, query, context)

            assert "unable to connect" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_invoke_agent_generic_error(self):
        """Test agent invocation with generic error"""
        client = AgentClient()
        agent_name = AgentClientTestDataFactory.create_agent_name()
        query = AgentClientTestDataFactory.create_query()
        context = {}

        mock_client = MockHttpClientFactory.create_generic_error_client()

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(httpx.HTTPError) as exc_info:
                await client.invoke(agent_name, query, context)

            assert "failed" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_invoke_agent_url_construction(self):
        """Test that invoke_agent constructs correct URL"""
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


# Tests removed: list_agents() and _prepare_context() methods no longer exist
# These methods were removed as part of the HTTP agent client refactor


class TestGetAgentClient:
    """Test get_agent_client() global instance function"""

    def test_get_agent_client_creates_instance(self):
        """Test that get_agent_client creates instance on first call"""
        # Reset global instance
        import bot.services.agent_client as module

        module._agent_client = None

        client = get_agent_client()

        assert client is not None
        assert isinstance(client, AgentClient)

    def test_get_agent_client_returns_same_instance(self):
        """Test that get_agent_client returns same instance on multiple calls"""
        # Reset global instance
        import bot.services.agent_client as module

        module._agent_client = None

        client1 = get_agent_client()
        client2 = get_agent_client()

        assert client1 is client2

    def test_get_agent_client_uses_env_variable(self):
        """Test that get_agent_client uses AGENT_SERVICE_URL env variable"""
        # Reset global instance
        import bot.services.agent_client as module

        module._agent_client = None

        test_url = "http://custom-agent-service:9000"

        with patch.dict("os.environ", {"AGENT_SERVICE_URL": test_url}):
            client = get_agent_client()
            assert client.base_url == test_url

        # Cleanup
        module._agent_client = None

    def test_get_agent_client_default_url(self):
        """Test that get_agent_client uses default URL when env not set"""
        # Reset global instance
        import bot.services.agent_client as module

        module._agent_client = None

        with patch.dict("os.environ", {}, clear=True):
            client = get_agent_client()
            assert client.base_url == "http://agent_service:8000"

        # Cleanup
        module._agent_client = None


# httpx.HTTPError tests removed - using standard httpx exceptions
