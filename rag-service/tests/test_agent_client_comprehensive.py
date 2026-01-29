"""
Comprehensive tests for agent client.

Tests HTTP agent invocation with mocked requests and circuit breaker.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from services.agent_client import (
    AgentClient,
    AgentClientError,
    CircuitBreaker,
    CircuitState,
)


class TestAgentClientInitialization:
    """Test agent client initialization."""

    def test_agent_client_can_be_imported(self):
        """Test that AgentClient can be imported."""
        assert AgentClient is not None

    def test_agent_client_initialization_default(self):
        """Test default initialization."""
        client = AgentClient()
        assert client.base_url == "http://agent_service:8000"
        assert client._client is None

    def test_agent_client_initialization_custom_url(self):
        """Test initialization with custom URL."""
        client = AgentClient(base_url="http://localhost:9000")
        assert client.base_url == "http://localhost:9000"

    def test_agent_client_has_circuit_breaker(self):
        """Test that circuit breaker is initialized."""
        client = AgentClient()
        assert client.circuit_breaker is not None


class TestCircuitBreaker:
    """Test circuit breaker functionality."""

    def test_circuit_breaker_initialization(self):
        """Test circuit breaker init with default params."""
        cb = CircuitBreaker()
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    def test_circuit_breaker_has_state(self):
        """Test that circuit breaker tracks state."""
        cb = CircuitBreaker()
        # Just verify it has the expected attributes
        assert hasattr(cb, "state")
        assert hasattr(cb, "failure_threshold")
        assert hasattr(cb, "recovery_timeout")


class TestPrepareContext:
    """Test context preparation."""

    def test_prepare_context_minimal(self):
        """Test preparing context with minimal data."""
        client = AgentClient()
        context = {
            "user_id": "U123",
            "channel_id": "C456",
        }

        prepared = client._prepare_context(context)

        assert "user_id" in prepared
        assert "channel_id" in prepared
        assert prepared["user_id"] == "U123"
        assert prepared["channel_id"] == "C456"

    def test_prepare_context_with_conversation_history(self):
        """Test preparing context with conversation history."""
        client = AgentClient()
        context = {
            "user_id": "U123",
            "conversation_history": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there!"},
            ],
        }

        prepared = client._prepare_context(context)

        assert "conversation_history" in prepared
        assert len(prepared["conversation_history"]) == 2

    def test_prepare_context_with_metadata(self):
        """Test preparing context with metadata."""
        client = AgentClient()
        context = {
            "user_id": "U123",
            "metadata": {
                "source": "slack",
                "timestamp": "2024-01-15",
            },
        }

        prepared = client._prepare_context(context)

        assert "metadata" in prepared
        assert prepared["metadata"]["source"] == "slack"


class TestListAgents:
    """Test listing available agents."""

    @pytest.mark.asyncio
    async def test_list_agents_success(self):
        """Test successfully listing agents."""
        client = AgentClient()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "agents": [
                {"name": "research", "description": "Research agent"},
                {"name": "company_profile", "description": "Company profiling"},
            ]
        }

        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            agents = await client.list_agents()

            assert len(agents) == 2
            assert agents[0]["name"] == "research"

    @pytest.mark.asyncio
    async def test_list_agents_handles_error(self):
        """Test handling error when listing agents."""
        client = AgentClient()

        mock_response = Mock()
        mock_response.status_code = 500

        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            with pytest.raises(AgentClientError):
                await client.list_agents()


class TestGetCircuitBreakerStatus:
    """Test circuit breaker status retrieval."""

    def test_get_circuit_breaker_status(self):
        """Test getting circuit breaker status."""
        client = AgentClient()

        status = client.get_circuit_breaker_status()

        assert "state" in status
        assert "failure_count" in status
        assert "last_failure_time" in status

    def test_get_circuit_breaker_status_includes_state(self):
        """Test status includes circuit state."""
        client = AgentClient()

        status = client.get_circuit_breaker_status()

        # Verify expected keys are present
        assert "state" in status
        assert isinstance(status["state"], str)


class TestClientLifecycle:
    """Test client lifecycle management."""

    @pytest.mark.asyncio
    async def test_close_client_when_none(self):
        """Test closing when client is None."""
        client = AgentClient()

        # Should not raise error
        await client.close()

        assert client._client is None
