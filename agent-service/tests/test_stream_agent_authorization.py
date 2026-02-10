"""Tests for stream_agent authorization flow.

Tests all authentication and authorization paths in api/agents.py stream_agent().
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, Request

from api.agents import AgentInvokeRequest, stream_agent


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
def mock_system_agent_info():
    """Mock system agent discovery result."""
    return {
        "agent_name": "help",
        "display_name": "Help Agent",
        "endpoint_url": "http://agent-service:8000/api/agents/help/invoke",
        "is_cloud": False,
        "is_system": True,
    }


@pytest.mark.asyncio
class TestStreamAgentAuthentication:
    """Test authentication methods for stream_agent."""

    async def test_no_auth_raises_401(
        self, mock_request, mock_invoke_request, mock_agent_info
    ):
        """Test that missing authentication raises 401."""
        with patch(
            "api.agents.agent_client.discover_agent",
            return_value=mock_agent_info,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await stream_agent("test_agent", mock_invoke_request, mock_request)

            assert exc_info.value.status_code == 401
            assert "Authentication required" in exc_info.value.detail

    async def test_jwt_authentication_success(
        self, mock_request, mock_invoke_request, mock_agent_info
    ):
        """Test successful JWT authentication."""
        mock_request.headers = {"Authorization": "Bearer valid_jwt_token"}

        mock_user_info = {"user_id": "user123", "email": "test@example.com"}
        mock_permissions = [{"agent_name": "test_agent"}]

        with (
            patch(
                "api.agents.agent_client.discover_agent",
                return_value=mock_agent_info,
            ),
            patch("dependencies.auth.get_current_user", return_value=mock_user_info),
            patch("httpx.AsyncClient") as mock_httpx,
            patch("services.agent_registry.get_agent", return_value=MagicMock()),
            patch("api.agents.StreamingResponse", return_value=MagicMock()),
        ):
            # Mock control plane permissions check
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"permissions": mock_permissions}
            mock_httpx.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            # Should not raise
            result = await stream_agent("test_agent", mock_invoke_request, mock_request)
            assert result is not None

    async def test_service_token_authentication_success(
        self, mock_request, mock_invoke_request, mock_agent_info
    ):
        """Test successful internal service token authentication."""
        mock_request.headers = {"X-Service-Token": "dev-bot-service-token"}

        with (
            patch(
                "api.agents.agent_client.discover_agent",
                return_value=mock_agent_info,
            ),
            patch(
                "shared.utils.service_auth.verify_service_token",
                return_value={"service": "bot", "valid": True},
            ),
            patch("services.agent_registry.get_agent", return_value=MagicMock()),
            patch("api.agents.StreamingResponse", return_value=MagicMock()),
        ):
            # Should not raise
            result = await stream_agent("test_agent", mock_invoke_request, mock_request)
            assert result is not None


@pytest.mark.asyncio
class TestJWTUserPermissions:
    """Test JWT user permission checks."""

    async def test_jwt_user_without_permission_raises_403(
        self, mock_request, mock_invoke_request, mock_agent_info
    ):
        """Test that JWT user without permission raises 403."""
        mock_request.headers = {"Authorization": "Bearer valid_jwt_token"}

        mock_user_info = {"user_id": "user123"}
        mock_permissions = [{"agent_name": "other_agent"}]  # Wrong agent

        with (
            patch(
                "api.agents.agent_client.discover_agent",
                return_value=mock_agent_info,
            ),
            patch("dependencies.auth.get_current_user", return_value=mock_user_info),
            patch("httpx.AsyncClient") as mock_httpx,
        ):
            # Mock control plane permissions check
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"permissions": mock_permissions}
            mock_httpx.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            with pytest.raises(HTTPException) as exc_info:
                await stream_agent("test_agent", mock_invoke_request, mock_request)

            assert exc_info.value.status_code == 403
            assert "does not have permission" in exc_info.value.detail

    async def test_jwt_permission_check_unavailable_raises_503(
        self, mock_request, mock_invoke_request, mock_agent_info
    ):
        """Test that control plane unavailability raises 503."""
        mock_request.headers = {"Authorization": "Bearer valid_jwt_token"}
        mock_user_info = {"user_id": "user123"}

        with (
            patch(
                "api.agents.agent_client.discover_agent",
                return_value=mock_agent_info,
            ),
            patch("dependencies.auth.get_current_user", return_value=mock_user_info),
            patch("httpx.AsyncClient") as mock_httpx,
        ):
            import httpx

            mock_httpx.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=httpx.RequestError("Connection failed")
            )

            with pytest.raises(HTTPException) as exc_info:
                await stream_agent("test_agent", mock_invoke_request, mock_request)

            assert exc_info.value.status_code == 503
            assert "unavailable" in exc_info.value.detail.lower()

    async def test_jwt_permission_check_403_response(
        self, mock_request, mock_invoke_request, mock_agent_info
    ):
        """Test that 403 from permission check is propagated."""
        mock_request.headers = {"Authorization": "Bearer valid_jwt_token"}
        mock_user_info = {"user_id": "user123"}

        with (
            patch(
                "api.agents.agent_client.discover_agent",
                return_value=mock_agent_info,
            ),
            patch("dependencies.auth.get_current_user", return_value=mock_user_info),
            patch("httpx.AsyncClient") as mock_httpx,
        ):
            # Mock control plane returns 403
            mock_response = MagicMock()
            mock_response.status_code = 403
            mock_httpx.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            with pytest.raises(HTTPException) as exc_info:
                await stream_agent("test_agent", mock_invoke_request, mock_request)

            assert exc_info.value.status_code == 403


@pytest.mark.asyncio
class TestServiceAccountAuthorization:
    """Test service account authorization checks."""

    async def test_service_account_system_agent_blocked(
        self, mock_request, mock_invoke_request, mock_system_agent_info
    ):
        """Test that service accounts cannot access system agents."""
        mock_request.headers = {"X-API-Key": "sa_test_key_12345"}

        mock_service_account = MagicMock()
        mock_service_account.name = "Test Account"
        mock_service_account.scopes = ["agents:invoke"]
        mock_service_account.allowed_agents = None

        with (
            patch(
                "api.agents.agent_client.discover_agent",
                return_value=mock_system_agent_info,
            ),
            patch(
                "dependencies.service_account_auth.verify_service_account_api_key",
                return_value=mock_service_account,
            ),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await stream_agent("help", mock_invoke_request, mock_request)

            assert exc_info.value.status_code == 403
            assert "System agent" in exc_info.value.detail
            assert "Slack users" in exc_info.value.detail

    async def test_service_account_agent_not_allowed(
        self, mock_request, mock_invoke_request, mock_agent_info
    ):
        """Test that service account blocked from unauthorized agent."""
        mock_request.headers = {"X-API-Key": "sa_test_key_12345"}

        mock_service_account = MagicMock()
        mock_service_account.name = "Test Account"
        mock_service_account.scopes = ["agents:invoke"]
        mock_service_account.allowed_agents = ["other_agent"]  # Not test_agent

        with (
            patch(
                "api.agents.agent_client.discover_agent",
                return_value=mock_agent_info,
            ),
            patch(
                "dependencies.service_account_auth.verify_service_account_api_key",
                return_value=mock_service_account,
            ),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await stream_agent("test_agent", mock_invoke_request, mock_request)

            assert exc_info.value.status_code == 403
            assert "not authorized" in exc_info.value.detail

    async def test_service_account_missing_invoke_scope(
        self, mock_request, mock_invoke_request, mock_agent_info
    ):
        """Test that service account without agents:invoke scope is blocked."""
        mock_request.headers = {"X-API-Key": "sa_test_key_12345"}

        mock_service_account = MagicMock()
        mock_service_account.name = "Test Account"
        mock_service_account.scopes = ["agents:read"]  # No invoke scope
        mock_service_account.allowed_agents = ["test_agent"]

        with (
            patch(
                "api.agents.agent_client.discover_agent",
                return_value=mock_agent_info,
            ),
            patch(
                "dependencies.service_account_auth.verify_service_account_api_key",
                return_value=mock_service_account,
            ),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await stream_agent("test_agent", mock_invoke_request, mock_request)

            assert exc_info.value.status_code == 403
            assert "agents:invoke" in exc_info.value.detail

    async def test_service_account_allowed_agents_none_grants_access(
        self, mock_request, mock_invoke_request, mock_agent_info
    ):
        """Test that allowed_agents=None grants access to all agents."""
        mock_request.headers = {"X-API-Key": "sa_test_key_12345"}

        mock_service_account = MagicMock()
        mock_service_account.name = "Test Account"
        mock_service_account.scopes = ["agents:invoke"]
        mock_service_account.allowed_agents = None  # Access to all

        with (
            patch(
                "api.agents.agent_client.discover_agent",
                return_value=mock_agent_info,
            ),
            patch(
                "dependencies.service_account_auth.verify_service_account_api_key",
                return_value=mock_service_account,
            ),
            patch("services.agent_registry.get_agent", return_value=MagicMock()),
            patch("api.agents.StreamingResponse", return_value=MagicMock()),
        ):
            # Should not raise
            result = await stream_agent("test_agent", mock_invoke_request, mock_request)
            assert result is not None

    async def test_service_account_in_allowed_list_grants_access(
        self, mock_request, mock_invoke_request, mock_agent_info
    ):
        """Test that agent in allowed_agents list grants access."""
        mock_request.headers = {"X-API-Key": "sa_test_key_12345"}

        mock_service_account = MagicMock()
        mock_service_account.name = "Test Account"
        mock_service_account.scopes = ["agents:invoke"]
        mock_service_account.allowed_agents = ["test_agent", "other_agent"]

        with (
            patch(
                "api.agents.agent_client.discover_agent",
                return_value=mock_agent_info,
            ),
            patch(
                "dependencies.service_account_auth.verify_service_account_api_key",
                return_value=mock_service_account,
            ),
            patch("services.agent_registry.get_agent", return_value=MagicMock()),
            patch("api.agents.StreamingResponse", return_value=MagicMock()),
        ):
            # Should not raise
            result = await stream_agent("test_agent", mock_invoke_request, mock_request)
            assert result is not None


@pytest.mark.asyncio
class TestAgentDiscovery:
    """Test agent discovery in stream_agent."""

    async def test_nonexistent_agent_raises_404(
        self, mock_request, mock_invoke_request
    ):
        """Test that nonexistent agent raises 404."""
        mock_request.headers = {"X-Service-Token": "dev-bot-service-token"}

        with (
            patch(
                "api.agents.agent_client.discover_agent",
                side_effect=ValueError("Agent 'missing' not found"),
            ),
            patch(
                "shared.utils.service_auth.verify_service_token",
                return_value={"service": "bot"},
            ),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await stream_agent("missing", mock_invoke_request, mock_request)

            assert exc_info.value.status_code == 404
            assert "not found" in str(exc_info.value.detail)

    async def test_invalid_agent_name_raises_400(
        self, mock_request, mock_invoke_request
    ):
        """Test that invalid agent name raises 400."""
        mock_request.headers = {"X-Service-Token": "dev-bot-service-token"}

        with patch(
            "shared.utils.service_auth.verify_service_token",
            return_value={"service": "bot"},
        ):
            # Agent name with invalid characters
            with pytest.raises(HTTPException) as exc_info:
                await stream_agent(
                    "agent;drop table", mock_invoke_request, mock_request
                )

            assert exc_info.value.status_code == 400
            assert "Invalid agent name" in exc_info.value.detail
