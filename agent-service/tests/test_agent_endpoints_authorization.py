"""Tests for agent endpoint authorization (invoke and stream).

Tests that both /invoke and /stream endpoints properly use centralized authorization.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request

from api.agents import AgentInvokeRequest, invoke_agent, stream_agent
from dependencies.agent_auth import AuthResult


@pytest.fixture
def mock_request():
    """Create mock FastAPI request."""
    request = MagicMock(spec=Request)
    request.headers = {}
    request.client = MagicMock()
    request.client.host = "127.0.0.1"
    return request


@pytest.fixture
def mock_invoke_request():
    """Create mock agent invoke request."""
    return AgentInvokeRequest(query="test query", context={})


@pytest.fixture
def mock_agent_info():
    """Mock agent discovery result."""
    return {
        "agent_name": "test_agent",
        "display_name": "Test Agent",
        "endpoint_url": "http://agent-service:8000/api/agents/test_agent/invoke",
        "is_cloud": False,
        "is_system": False,
    }


@pytest.fixture
def mock_auth_result_jwt():
    """Mock AuthResult for JWT authentication."""
    return AuthResult(auth_type="jwt", user_id="user123")


@pytest.fixture
def mock_auth_result_service():
    """Mock AuthResult for service token authentication."""
    return AuthResult(auth_type="service", user_id=None)


@pytest.mark.asyncio
class TestInvokeAgentAuthorization:
    """Test invoke_agent endpoint authorization."""

    async def test_invoke_uses_centralized_auth(
        self, mock_request, mock_invoke_request, mock_agent_info, mock_auth_result_jwt
    ):
        """Test that invoke_agent uses centralized authorization."""
        with (
            patch(
                "api.agents.agent_client.discover_agent",
                return_value=mock_agent_info,
            ),
            patch(
                "dependencies.agent_auth.authorize_agent_request",
                return_value=mock_auth_result_jwt,
            ) as mock_authorize,
            patch("api.agents.agent_client.invoke", return_value={"response": "ok"}),
            patch("services.metrics_service.get_metrics_service", return_value=None),
            patch(
                "shared.services.langfuse_service.get_langfuse_service",
                return_value=None,
            ),
            patch(
                "shared.utils.trace_propagation.extract_trace_context",
                return_value=None,
            ),
        ):
            result = await invoke_agent("test_agent", mock_invoke_request, mock_request)

            # Verify centralized auth was called
            mock_authorize.assert_called_once_with(
                "test_agent", mock_agent_info, mock_request
            )

            # Verify response
            assert result.agent_name == "test_agent"
            assert result.output.get("response") == "ok"

    async def test_invoke_passes_user_context_from_jwt(
        self, mock_request, mock_invoke_request, mock_agent_info, mock_auth_result_jwt
    ):
        """Test that invoke_agent passes user_id from JWT auth."""
        with (
            patch(
                "api.agents.agent_client.discover_agent",
                return_value=mock_agent_info,
            ),
            patch(
                "dependencies.agent_auth.authorize_agent_request",
                return_value=mock_auth_result_jwt,
            ),
            patch(
                "api.agents.agent_client.invoke", return_value={"response": "ok"}
            ) as mock_invoke,
            patch("services.metrics_service.get_metrics_service", return_value=None),
            patch(
                "shared.services.langfuse_service.get_langfuse_service",
                return_value=None,
            ),
            patch(
                "shared.utils.trace_propagation.extract_trace_context",
                return_value=None,
            ),
        ):
            await invoke_agent("test_agent", mock_invoke_request, mock_request)

            # Verify user_id was passed to agent
            call_kwargs = mock_invoke.call_args[1]
            assert call_kwargs["context"]["user_id"] == "user123"
            assert call_kwargs["context"]["auth_type"] == "jwt"

    async def test_invoke_passes_auth_context_from_service(
        self,
        mock_request,
        mock_invoke_request,
        mock_agent_info,
        mock_auth_result_service,
    ):
        """Test that invoke_agent passes auth context from service token."""
        with (
            patch(
                "api.agents.agent_client.discover_agent",
                return_value=mock_agent_info,
            ),
            patch(
                "dependencies.agent_auth.authorize_agent_request",
                return_value=mock_auth_result_service,
            ),
            patch(
                "api.agents.agent_client.invoke", return_value={"response": "ok"}
            ) as mock_invoke,
            patch("services.metrics_service.get_metrics_service", return_value=None),
            patch(
                "shared.services.langfuse_service.get_langfuse_service",
                return_value=None,
            ),
            patch(
                "shared.utils.trace_propagation.extract_trace_context",
                return_value=None,
            ),
        ):
            await invoke_agent("test_agent", mock_invoke_request, mock_request)

            # Verify user_id was NOT passed (service auth)
            call_kwargs = mock_invoke.call_args[1]
            assert "user_id" not in call_kwargs["context"]
            assert call_kwargs["context"]["auth_type"] == "service"


@pytest.mark.asyncio
class TestStreamAgentAuthorization:
    """Test stream_agent endpoint authorization."""

    async def test_stream_uses_centralized_auth(
        self, mock_request, mock_invoke_request, mock_agent_info, mock_auth_result_jwt
    ):
        """Test that stream_agent uses centralized authorization."""
        with (
            patch(
                "api.agents.agent_client.discover_agent",
                return_value=mock_agent_info,
            ),
            patch(
                "dependencies.agent_auth.authorize_agent_request",
                return_value=mock_auth_result_jwt,
            ) as mock_authorize,
            patch("api.agents.agent_client.stream", return_value=AsyncMock()),
        ):
            # Call stream_agent (returns StreamingResponse)
            result = await stream_agent("test_agent", mock_invoke_request, mock_request)

            # Verify centralized auth was called
            mock_authorize.assert_called_once_with(
                "test_agent", mock_agent_info, mock_request
            )

            # Verify StreamingResponse returned
            assert result is not None

    async def test_stream_passes_user_context_from_jwt(
        self, mock_request, mock_invoke_request, mock_agent_info, mock_auth_result_jwt
    ):
        """Test that stream_agent passes user_id from JWT auth."""

        async def mock_stream_generator(*args, **kwargs):
            # Capture context from stream call
            TestStreamAgentAuthorization._captured_context = kwargs.get("context", {})
            yield "test chunk"

        with (
            patch(
                "api.agents.agent_client.discover_agent",
                return_value=mock_agent_info,
            ),
            patch(
                "dependencies.agent_auth.authorize_agent_request",
                return_value=mock_auth_result_jwt,
            ),
            patch("api.agents.agent_client.stream", side_effect=mock_stream_generator),
            patch(
                "shared.utils.trace_propagation.extract_trace_context",
                return_value=None,
            ),
        ):
            response = await stream_agent(
                "test_agent", mock_invoke_request, mock_request
            )

            # Consume the streaming response to trigger the generator
            async for _ in response.body_iterator:
                pass

            # Verify user_id was passed to agent
            captured = TestStreamAgentAuthorization._captured_context
            assert captured["user_id"] == "user123"
            assert captured["auth_type"] == "jwt"

    async def test_stream_passes_auth_context_from_service(
        self,
        mock_request,
        mock_invoke_request,
        mock_agent_info,
        mock_auth_result_service,
    ):
        """Test that stream_agent passes auth context from service token."""

        async def mock_stream_generator(*args, **kwargs):
            # Capture context from stream call
            TestStreamAgentAuthorization._captured_context = kwargs.get("context", {})
            yield "test chunk"

        with (
            patch(
                "api.agents.agent_client.discover_agent",
                return_value=mock_agent_info,
            ),
            patch(
                "dependencies.agent_auth.authorize_agent_request",
                return_value=mock_auth_result_service,
            ),
            patch("api.agents.agent_client.stream", side_effect=mock_stream_generator),
            patch(
                "shared.utils.trace_propagation.extract_trace_context",
                return_value=None,
            ),
        ):
            response = await stream_agent(
                "test_agent", mock_invoke_request, mock_request
            )

            # Consume the streaming response to trigger the generator
            async for _ in response.body_iterator:
                pass

            # Verify user_id was NOT passed (service auth)
            captured = TestStreamAgentAuthorization._captured_context
            assert "user_id" not in captured
            assert captured["auth_type"] == "service"


@pytest.mark.asyncio
class TestBothEndpointsConsistency:
    """Test that both endpoints have consistent authorization behavior."""

    async def test_both_endpoints_reject_invalid_agent_name(
        self, mock_request, mock_invoke_request
    ):
        """Test that both endpoints reject invalid agent names."""
        with pytest.raises(Exception) as exc_invoke:
            await invoke_agent("agent;drop table", mock_invoke_request, mock_request)

        with pytest.raises(Exception) as exc_stream:
            await stream_agent("agent;drop table", mock_invoke_request, mock_request)

        # Both should raise HTTPException with 400 status
        assert exc_invoke.value.status_code == 400
        assert exc_stream.value.status_code == 400
        assert "Invalid agent name" in str(exc_invoke.value.detail)
        assert "Invalid agent name" in str(exc_stream.value.detail)

    async def test_both_endpoints_use_same_auth_function(
        self, mock_request, mock_invoke_request, mock_agent_info, mock_auth_result_jwt
    ):
        """Test that both endpoints call the same authorize_agent_request."""
        auth_calls = []

        async def track_auth_calls(*args, **kwargs):
            auth_calls.append(("auth_called", args, kwargs))
            return mock_auth_result_jwt

        with (
            patch(
                "api.agents.agent_client.discover_agent",
                return_value=mock_agent_info,
            ),
            patch(
                "dependencies.agent_auth.authorize_agent_request",
                side_effect=track_auth_calls,
            ),
            patch("api.agents.agent_client.invoke", return_value={"response": "ok"}),
            patch("api.agents.agent_client.stream", return_value=AsyncMock()),
            patch("services.metrics_service.get_metrics_service", return_value=None),
            patch(
                "shared.services.langfuse_service.get_langfuse_service",
                return_value=None,
            ),
            patch(
                "shared.utils.trace_propagation.extract_trace_context",
                return_value=None,
            ),
        ):
            # Call both endpoints
            await invoke_agent("test_agent", mock_invoke_request, mock_request)
            await stream_agent("test_agent", mock_invoke_request, mock_request)

            # Both should have called authorize_agent_request with same args
            assert len(auth_calls) == 2
            # Verify both calls have same arguments
            assert auth_calls[0][1] == auth_calls[1][1]  # Same positional args
