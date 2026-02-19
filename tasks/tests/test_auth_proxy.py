"""Tests for tasks service auth proxy (dependencies/auth.py).

Covers URL configuration, header/cookie forwarding,
verify_admin_from_database, and require_admin_from_database.
Core get_current_user and get_optional_user flow tests live in
test_dependencies_auth.py.
"""

from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest
from fastapi import HTTPException, Request

from dependencies.auth import (
    get_current_user,
    require_admin_from_database,
    verify_admin_from_database,
)


def _make_mock_client(response):
    """Build an httpx.AsyncClient mock that yields *response* from .get()."""
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.get = AsyncMock(return_value=response)
    return mock_client


class TestControlPlaneURLConfiguration:
    """Test that auth proxy reads the correct control-plane URL."""

    @pytest.mark.asyncio
    async def test_reads_control_plane_url_from_env(self, monkeypatch):
        """get_current_user uses CONTROL_PLANE_INTERNAL_URL env var."""
        monkeypatch.setenv("CONTROL_PLANE_INTERNAL_URL", "http://custom-plane:9999")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "email": "user@8thlight.com",
            "name": "Test User",
        }

        mock_request = Mock(spec=Request)
        mock_request.headers.get.return_value = None
        mock_request.cookies = {}

        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value = _make_mock_client(mock_response)
            await get_current_user(mock_request)

        call_url = MockClient.return_value.get.call_args[0][0]
        assert call_url == "http://custom-plane:9999/api/users/me"

    @pytest.mark.asyncio
    async def test_defaults_to_docker_hostname(self, monkeypatch):
        """get_current_user falls back to http://control-plane:6001 by default."""
        monkeypatch.delenv("CONTROL_PLANE_INTERNAL_URL", raising=False)

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "email": "user@8thlight.com",
            "name": "Test User",
        }

        mock_request = Mock(spec=Request)
        mock_request.headers.get.return_value = None
        mock_request.cookies = {}

        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value = _make_mock_client(mock_response)
            await get_current_user(mock_request)

        call_url = MockClient.return_value.get.call_args[0][0]
        assert call_url == "http://control-plane:6001/api/users/me"

    @pytest.mark.asyncio
    async def test_forwards_authorization_header(self, monkeypatch):
        """Authorization header from the incoming request is forwarded."""
        monkeypatch.delenv("CONTROL_PLANE_INTERNAL_URL", raising=False)

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"email": "user@8thlight.com"}

        mock_request = Mock(spec=Request)
        mock_request.headers.get.return_value = "Bearer my-jwt-token"
        mock_request.cookies = {}

        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value = _make_mock_client(mock_response)
            await get_current_user(mock_request)

        call_kwargs = MockClient.return_value.get.call_args[1]
        assert call_kwargs["headers"]["Authorization"] == "Bearer my-jwt-token"

    @pytest.mark.asyncio
    async def test_forwards_cookies(self, monkeypatch):
        """Cookies from the incoming request are forwarded to control-plane."""
        monkeypatch.delenv("CONTROL_PLANE_INTERNAL_URL", raising=False)

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"email": "user@8thlight.com"}

        mock_request = Mock(spec=Request)
        mock_request.headers.get.return_value = None
        mock_request.cookies = {"session": "abc123"}

        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value = _make_mock_client(mock_response)
            await get_current_user(mock_request)

        call_kwargs = MockClient.return_value.get.call_args[1]
        assert call_kwargs["cookies"] == {"session": "abc123"}

    @pytest.mark.asyncio
    async def test_no_authorization_header_when_absent(self, monkeypatch):
        """Authorization header is NOT forwarded when the request has none."""
        monkeypatch.delenv("CONTROL_PLANE_INTERNAL_URL", raising=False)

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"email": "user@8thlight.com"}

        mock_request = Mock(spec=Request)
        mock_request.headers.get.return_value = None  # No Authorization header
        mock_request.cookies = {}

        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value = _make_mock_client(mock_response)
            await get_current_user(mock_request)

        call_kwargs = MockClient.return_value.get.call_args[1]
        assert "Authorization" not in call_kwargs["headers"]


class TestVerifyAdminFromDatabase:
    """Tests for verify_admin_from_database — reads admin status from control-plane."""

    @pytest.mark.asyncio
    async def test_returns_true_for_admin(self, monkeypatch):
        """Returns True when control-plane responds with is_admin: true."""
        monkeypatch.delenv("CONTROL_PLANE_INTERNAL_URL", raising=False)

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"is_admin": True}

        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value = _make_mock_client(mock_response)
            result = await verify_admin_from_database("admin@8thlight.com")

        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_for_non_admin(self, monkeypatch):
        """Returns False when control-plane responds with is_admin: false."""
        monkeypatch.delenv("CONTROL_PLANE_INTERNAL_URL", raising=False)

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"is_admin": False}

        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value = _make_mock_client(mock_response)
            result = await verify_admin_from_database("user@8thlight.com")

        assert result is False

    @pytest.mark.asyncio
    async def test_fails_closed_on_non_200(self, monkeypatch):
        """Returns False (fail closed) when control-plane returns a non-200 status."""
        monkeypatch.delenv("CONTROL_PLANE_INTERNAL_URL", raising=False)

        mock_response = Mock()
        mock_response.status_code = 403

        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value = _make_mock_client(mock_response)
            result = await verify_admin_from_database("user@8thlight.com")

        assert result is False

    @pytest.mark.asyncio
    async def test_fails_closed_on_request_error(self, monkeypatch):
        """Returns False (fail closed) when control-plane is unreachable."""
        monkeypatch.delenv("CONTROL_PLANE_INTERNAL_URL", raising=False)

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.get = AsyncMock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value = mock_client
            result = await verify_admin_from_database("user@8thlight.com")

        assert result is False

    @pytest.mark.asyncio
    async def test_uses_email_as_query_param(self, monkeypatch):
        """The user email is passed as a query parameter to /api/users/verify-admin."""
        monkeypatch.delenv("CONTROL_PLANE_INTERNAL_URL", raising=False)

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"is_admin": True}

        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value = _make_mock_client(mock_response)
            await verify_admin_from_database("admin@8thlight.com")

        call_kwargs = MockClient.return_value.get.call_args[1]
        assert call_kwargs["params"] == {"email": "admin@8thlight.com"}


class TestRequireAdminFromDatabase:
    """Tests for require_admin_from_database — composes get_current_user + verify_admin."""

    @pytest.mark.asyncio
    async def test_returns_user_when_admin(self):
        """Returns user dict when authenticated and admin-verified."""
        user_data = {"email": "admin@8thlight.com", "name": "Admin User"}

        with (
            patch(
                "dependencies.auth.get_current_user",
                new=AsyncMock(return_value=user_data),
            ),
            patch(
                "dependencies.auth.verify_admin_from_database",
                new=AsyncMock(return_value=True),
            ),
        ):
            mock_request = Mock(spec=Request)
            result = await require_admin_from_database(mock_request)

        assert result == user_data

    @pytest.mark.asyncio
    async def test_raises_403_when_not_admin(self):
        """Raises HTTPException 403 when user is authenticated but not admin."""
        user_data = {"email": "user@8thlight.com", "name": "Regular User"}

        with (
            patch(
                "dependencies.auth.get_current_user",
                new=AsyncMock(return_value=user_data),
            ),
            patch(
                "dependencies.auth.verify_admin_from_database",
                new=AsyncMock(return_value=False),
            ),
        ):
            mock_request = Mock(spec=Request)
            with pytest.raises(HTTPException) as exc_info:
                await require_admin_from_database(mock_request)

        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_propagates_401_when_not_authenticated(self):
        """Propagates 401 HTTPException from get_current_user when unauthenticated."""
        with patch(
            "dependencies.auth.get_current_user",
            new=AsyncMock(
                side_effect=HTTPException(status_code=401, detail="Not authenticated")
            ),
        ):
            mock_request = Mock(spec=Request)
            with pytest.raises(HTTPException) as exc_info:
                await require_admin_from_database(mock_request)

        assert exc_info.value.status_code == 401
