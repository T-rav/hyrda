"""Tests for tasks service auth proxy to control-plane."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from httpx import ConnectError, RequestError
from starlette.requests import Request


class TestAuthMeProxy:
    """Test /auth/me endpoint proxying to control-plane."""

    @pytest.mark.asyncio
    async def test_auth_me_proxies_to_control_plane(self):
        """Test that /auth/me proxies request to control-plane."""
        from tasks.api.auth import get_current_user

        # Mock request with cookies
        mock_request = MagicMock(spec=Request)
        mock_request.cookies = {"session_id": "test-session-123"}

        # Mock httpx response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "authenticated": True,
            "email": "user@example.com",
            "user": {"name": "Test User"},
        }

        with patch("tasks.api.auth.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.get.return_value = mock_response
            mock_client_class.return_value = mock_client

            response = await get_current_user(mock_request)

        # Should return user data from control-plane
        assert response["authenticated"] is True
        assert response["email"] == "user@example.com"

        # Should have called control-plane with cookies
        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        assert "control_plane:6001" in call_args[0][0]
        assert call_args[1]["cookies"] == {"session_id": "test-session-123"}

    @pytest.mark.asyncio
    async def test_auth_me_returns_401_when_not_authenticated(self):
        """Test that /auth/me returns 401 when control-plane returns 401."""
        from tasks.api.auth import get_current_user

        mock_request = MagicMock(spec=Request)
        mock_request.cookies = {}

        # Mock httpx 401 response
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"detail": "Not authenticated"}

        with patch("tasks.api.auth.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.get.return_value = mock_response
            mock_client_class.return_value = mock_client

            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(mock_request)

        # Should raise 401
        assert exc_info.value.status_code == 401
        assert "Not authenticated" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_auth_me_handles_connection_error(self):
        """Test that /auth/me handles connection errors gracefully."""
        from tasks.api.auth import get_current_user

        mock_request = MagicMock(spec=Request)
        mock_request.cookies = {"session_id": "test-session-123"}

        # Mock connection error
        with patch("tasks.api.auth.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.get.side_effect = ConnectError("Connection refused")
            mock_client_class.return_value = mock_client

            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(mock_request)

        # Should raise 503 Service Unavailable
        assert exc_info.value.status_code == 503
        assert "Auth service unavailable" in exc_info.value.detail


class TestGetCurrentUserDependency:
    """Test get_current_user dependency injection."""

    @pytest.mark.asyncio
    async def test_get_current_user_uses_internal_docker_url(self):
        """Test that get_current_user uses internal Docker service name."""
        from tasks.dependencies.auth import get_current_user

        mock_request = MagicMock(spec=Request)
        mock_request.cookies = {"session_id": "test-session-123"}

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "email": "user@example.com",
            "name": "Test User",
        }

        with patch("tasks.dependencies.auth.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.get.return_value = mock_response
            mock_client_class.return_value = mock_client

            result = await get_current_user(mock_request)

        # Should use internal Docker service name
        call_args = mock_client.get.call_args[0][0]
        assert "control_plane:6001" in call_args
        assert "https://" in call_args

        # Should return user data
        assert result["email"] == "user@example.com"

    @pytest.mark.asyncio
    async def test_get_current_user_forwards_all_cookies(self):
        """Test that get_current_user forwards all cookies to control-plane."""
        from tasks.dependencies.auth import get_current_user

        mock_request = MagicMock(spec=Request)
        mock_request.cookies = {
            "session_id": "test-session-123",
            "access_token": "jwt-token-456",
            "other_cookie": "value",
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"email": "user@example.com"}

        with patch("tasks.dependencies.auth.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.get.return_value = mock_response
            mock_client_class.return_value = mock_client

            await get_current_user(mock_request)

        # Should forward all cookies
        call_kwargs = mock_client.get.call_args[1]
        assert call_kwargs["cookies"] == {
            "session_id": "test-session-123",
            "access_token": "jwt-token-456",
            "other_cookie": "value",
        }

    @pytest.mark.asyncio
    async def test_get_current_user_disables_ssl_verification(self):
        """Test that get_current_user disables SSL verification for self-signed certs."""
        from tasks.dependencies.auth import get_current_user

        mock_request = MagicMock(spec=Request)
        mock_request.cookies = {"session_id": "test"}

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"email": "user@example.com"}

        with patch("tasks.dependencies.auth.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.get.return_value = mock_response
            mock_client_class.return_value = mock_client

            await get_current_user(mock_request)

        # Should create client with verify=False
        mock_client_class.assert_called_once_with(verify=False)


class TestNginxCookieForwarding:
    """Test nginx cookie forwarding configuration."""

    def test_nginx_config_includes_cookie_header(self):
        """Test that nginx.conf includes proxy_set_header Cookie."""
        import os

        nginx_conf_path = os.path.join(
            os.path.dirname(__file__), "..", "nginx.conf"
        )

        with open(nginx_conf_path) as f:
            nginx_config = f.read()

        # Should include proxy_set_header Cookie in API location
        assert "proxy_set_header Cookie $http_cookie" in nginx_config

        # Should be in both /api/ and /auth/ locations
        api_section = nginx_config[nginx_config.find("location /api/") :]
        auth_section = nginx_config[nginx_config.find("location /auth/") :]

        assert "proxy_set_header Cookie $http_cookie" in api_section
        assert "proxy_set_header Cookie $http_cookie" in auth_section
