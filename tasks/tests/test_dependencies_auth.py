"""Tests for authentication dependencies."""

import pytest
from fastapi import HTTPException, Request
from unittest.mock import AsyncMock, Mock, patch

from dependencies.auth import get_current_user, get_optional_user


class TestGetCurrentUser:
    """Test get_current_user dependency."""

    @pytest.mark.asyncio
    async def test_get_current_user_with_jwt_success(self):
        """Test successful authentication with JWT token."""
        mock_request = Mock(spec=Request)
        mock_request.headers.get.return_value = "Bearer test-token"
        mock_request.cookies = {}

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "email": "user@test.com",
            "name": "Test User",
            "is_admin": True,
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            user = await get_current_user(mock_request)

            assert user["email"] == "user@test.com"
            assert user["name"] == "Test User"
            assert user["is_admin"] is True

    @pytest.mark.asyncio
    async def test_get_current_user_with_cookies_success(self):
        """Test successful authentication with session cookies."""
        mock_request = Mock(spec=Request)
        mock_request.headers.get.return_value = None
        mock_request.cookies = {"session_id": "test-session"}

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "email": "user@test.com",
            "name": "Test User",
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            user = await get_current_user(mock_request)

            assert user["email"] == "user@test.com"

    @pytest.mark.asyncio
    async def test_get_current_user_unauthorized(self):
        """Test authentication failure returns 401."""
        mock_request = Mock(spec=Request)
        mock_request.headers.get.return_value = "Bearer invalid-token"
        mock_request.cookies = {}

        mock_response = Mock()
        mock_response.status_code = 401

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(mock_request)

            assert exc_info.value.status_code == 401
            assert "Not authenticated" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_current_user_control_plane_unavailable(self):
        """Test handling when control-plane is unavailable."""
        import httpx

        mock_request = Mock(spec=Request)
        mock_request.headers.get.return_value = None
        mock_request.cookies = {}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.get = AsyncMock(side_effect=httpx.RequestError("Connection refused"))
            mock_client_class.return_value = mock_client

            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(mock_request)

            assert exc_info.value.status_code == 503
            assert "Auth service unavailable" in exc_info.value.detail


class TestGetOptionalUser:
    """Test get_optional_user dependency."""

    @pytest.mark.asyncio
    async def test_get_optional_user_authenticated(self):
        """Test optional user returns user info when authenticated."""
        mock_request = Mock(spec=Request)
        mock_request.session = {
            "user_email": "user@8thlight.com",
            "user_info": {"email": "user@8thlight.com", "name": "Test User"},
        }

        with patch("dependencies.auth.verify_domain", return_value=True):
            user = await get_optional_user(mock_request)

            assert user is not None
            assert user["email"] == "user@8thlight.com"

    @pytest.mark.asyncio
    async def test_get_optional_user_no_session(self):
        """Test optional user returns None when no session."""
        mock_request = Mock(spec=Request)
        mock_request.session = {}

        user = await get_optional_user(mock_request)

        assert user is None

    @pytest.mark.asyncio
    async def test_get_optional_user_invalid_domain(self):
        """Test optional user returns None for invalid domain."""
        mock_request = Mock(spec=Request)
        mock_request.session = {
            "user_email": "user@invalid.com",
            "user_info": {"email": "user@invalid.com", "name": "Test User"},
        }

        with patch("dependencies.auth.verify_domain", return_value=False):
            user = await get_optional_user(mock_request)

            assert user is None

    @pytest.mark.asyncio
    async def test_get_optional_user_missing_user_email(self):
        """Test optional user returns None when user_email missing."""
        mock_request = Mock(spec=Request)
        mock_request.session = {
            "user_info": {"email": "user@test.com", "name": "Test User"},
        }

        user = await get_optional_user(mock_request)

        assert user is None

    @pytest.mark.asyncio
    async def test_get_optional_user_missing_user_info(self):
        """Test optional user returns None when user_info missing."""
        mock_request = Mock(spec=Request)
        mock_request.session = {
            "user_email": "user@test.com",
        }

        user = await get_optional_user(mock_request)

        assert user is None
