"""Unit tests for service account authentication dependency."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, Request

from dependencies.service_account_auth import (
    ServiceAccountAuth,
    verify_service_account_api_key,
)


@pytest.fixture
def mock_request():
    """Create a mock FastAPI request."""
    request = MagicMock(spec=Request)
    request.headers = {}
    request.client = MagicMock()
    request.client.host = "192.168.1.1"
    return request


@pytest.fixture
def mock_httpx_response():
    """Create a mock httpx response."""
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {
        "id": 1,
        "name": "Test Account",
        "scopes": "agents:read,agents:invoke",
        "allowed_agents": None,
        "rate_limit": 100,
    }
    return response


class TestServiceAccountAuth:
    """Tests for ServiceAccountAuth class."""

    def test_init(self):
        """Test ServiceAccountAuth initialization."""
        account_data = {
            "id": 1,
            "name": "Test",
            "scopes": "agents:read,agents:invoke",
            "allowed_agents": ["agent1", "agent2"],
            "rate_limit": 100,
        }

        auth = ServiceAccountAuth(account_data)

        assert auth.id == 1
        assert auth.name == "Test"
        assert auth.scopes == ["agents:read", "agents:invoke"]
        assert auth.allowed_agents == ["agent1", "agent2"]
        assert auth.rate_limit == 100


@pytest.mark.asyncio
class TestVerifyServiceAccountApiKey:
    """Tests for verify_service_account_api_key function."""

    async def test_no_api_key_returns_none(self, mock_request):
        """Test that missing API key returns None."""
        result = await verify_service_account_api_key(mock_request)
        assert result is None

    async def test_non_service_account_key_returns_none(self, mock_request):
        """Test that non-sa_ keys return None."""
        mock_request.headers = {"X-API-Key": "regular_key_12345"}
        result = await verify_service_account_api_key(mock_request)
        assert result is None

    async def test_extracts_from_x_api_key_header(
        self, mock_request, mock_httpx_response
    ):
        """Test extracting API key from X-API-Key header."""
        mock_request.headers = {"X-API-Key": "sa_test_key_12345"}

        with (
            patch.dict(
                "os.environ",
                {
                    "CONTROL_PLANE_URL": "http://control-plane:6001",
                    "AGENT_SERVICE_TOKEN": "test-token",
                },
            ),
            patch("httpx.AsyncClient") as mock_client,
        ):
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_httpx_response
            )

            result = await verify_service_account_api_key(mock_request)

            assert result is not None
            assert result.name == "Test Account"
            assert "agents:invoke" in result.scopes

    async def test_extracts_from_authorization_bearer(
        self, mock_request, mock_httpx_response
    ):
        """Test extracting API key from Authorization: Bearer header."""
        mock_request.headers = {"Authorization": "Bearer sa_test_key_12345"}

        with (
            patch.dict(
                "os.environ",
                {
                    "CONTROL_PLANE_URL": "http://control-plane:6001",
                    "AGENT_SERVICE_TOKEN": "test-token",
                },
            ),
            patch("httpx.AsyncClient") as mock_client,
        ):
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_httpx_response
            )

            result = await verify_service_account_api_key(mock_request)

            assert result is not None
            assert result.name == "Test Account"

    async def test_401_raises_http_exception(self, mock_request):
        """Test that 401 from control-plane raises HTTPException."""
        mock_request.headers = {"X-API-Key": "sa_invalid_key"}

        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"detail": "Invalid API key"}

        with (
            patch.dict(
                "os.environ",
                {
                    "CONTROL_PLANE_URL": "http://control-plane:6001",
                    "AGENT_SERVICE_TOKEN": "test-token",
                },
            ),
            patch("httpx.AsyncClient") as mock_client,
        ):
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            with pytest.raises(HTTPException) as exc_info:
                await verify_service_account_api_key(mock_request)

            assert exc_info.value.status_code == 401
            assert "Invalid API key" in exc_info.value.detail

    async def test_403_raises_http_exception(self, mock_request):
        """Test that 403 from control-plane raises HTTPException."""
        mock_request.headers = {"X-API-Key": "sa_revoked_key"}

        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.json.return_value = {"detail": "API key revoked"}

        with (
            patch.dict(
                "os.environ",
                {
                    "CONTROL_PLANE_URL": "http://control-plane:6001",
                    "AGENT_SERVICE_TOKEN": "test-token",
                },
            ),
            patch("httpx.AsyncClient") as mock_client,
        ):
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            with pytest.raises(HTTPException) as exc_info:
                await verify_service_account_api_key(mock_request)

            assert exc_info.value.status_code == 403
            assert "revoked" in exc_info.value.detail.lower()

    async def test_429_raises_http_exception(self, mock_request):
        """Test that 429 from control-plane raises HTTPException."""
        mock_request.headers = {"X-API-Key": "sa_rate_limited_key"}

        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.json.return_value = {"detail": "Rate limit exceeded"}

        with (
            patch.dict(
                "os.environ",
                {
                    "CONTROL_PLANE_URL": "http://control-plane:6001",
                    "AGENT_SERVICE_TOKEN": "test-token",
                },
            ),
            patch("httpx.AsyncClient") as mock_client,
        ):
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            with pytest.raises(HTTPException) as exc_info:
                await verify_service_account_api_key(mock_request)

            assert exc_info.value.status_code == 429

    async def test_missing_control_plane_url_raises_500(self, mock_request):
        """Test that missing CONTROL_PLANE_URL raises 500."""
        mock_request.headers = {"X-API-Key": "sa_test_key"}

        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(HTTPException) as exc_info:
                await verify_service_account_api_key(mock_request)

            assert exc_info.value.status_code == 500
            assert "not configured" in exc_info.value.detail

    async def test_request_error_raises_503(self, mock_request):
        """Test that httpx.RequestError raises 503."""
        mock_request.headers = {"X-API-Key": "sa_test_key"}

        with (
            patch.dict(
                "os.environ",
                {
                    "CONTROL_PLANE_URL": "http://control-plane:6001",
                    "AGENT_SERVICE_TOKEN": "test-token",
                },
            ),
            patch("httpx.AsyncClient") as mock_client,
        ):
            import httpx

            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=httpx.RequestError("Connection failed")
            )

            with pytest.raises(HTTPException) as exc_info:
                await verify_service_account_api_key(mock_request)

            assert exc_info.value.status_code == 503
            assert "unavailable" in exc_info.value.detail

    async def test_includes_client_ip_in_request(
        self, mock_request, mock_httpx_response
    ):
        """Test that client IP is included in validation request."""
        mock_request.headers = {"X-API-Key": "sa_test_key"}
        mock_request.client.host = "10.0.0.5"

        with (
            patch.dict(
                "os.environ",
                {
                    "CONTROL_PLANE_URL": "http://control-plane:6001",
                    "AGENT_SERVICE_TOKEN": "test-token",
                },
            ),
            patch("httpx.AsyncClient") as mock_client,
        ):
            mock_post = AsyncMock(return_value=mock_httpx_response)
            mock_client.return_value.__aenter__.return_value.post = mock_post

            await verify_service_account_api_key(mock_request)

            # Verify client IP was included in request
            call_args = mock_post.call_args
            assert call_args.kwargs["json"]["client_ip"] == "10.0.0.5"
