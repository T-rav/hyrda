"""Tests for OAuth endpoints in api/auth.py."""

import os
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def auth_app():
    """Create app for auth testing."""
    os.environ.setdefault("TASK_DATABASE_URL", "sqlite:///:memory:")
    os.environ.setdefault("DATA_DATABASE_URL", "sqlite:///:memory:")
    os.environ.setdefault("SERVER_BASE_URL", "http://localhost:5001")
    os.environ.setdefault("SECRET_KEY", "test-secret")
    os.environ.setdefault("GOOGLE_OAUTH_CLIENT_ID", "test-client-id")
    os.environ.setdefault("GOOGLE_OAUTH_CLIENT_SECRET", "test-secret")

    from app import app

    return app


@pytest.fixture
def client(auth_app):
    """Create test client."""
    return TestClient(auth_app)


class TestAuthMeEndpoint:
    """Test /auth/me endpoint."""

    @pytest.mark.asyncio
    async def test_auth_me_authenticated_success(self, client):
        """Test /auth/me with valid authentication."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "email": "test@test.com",
                "name": "Test User",
            }
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            response = client.get("/auth/me")

            assert response.status_code == 200
            data = response.json()
            assert data["authenticated"] is True
            assert data["email"] == "test@test.com"

    @pytest.mark.asyncio
    async def test_auth_me_unauthenticated(self, client):
        """Test /auth/me with invalid authentication."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.status_code = 401
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            response = client.get("/auth/me")

            assert response.status_code == 401
            data = response.json()
            assert data["authenticated"] is False
            assert "Not authenticated" in data["error"]

    @pytest.mark.asyncio
    async def test_auth_me_service_unavailable(self, client):
        """Test /auth/me when control-plane is unavailable."""
        import httpx

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(
                side_effect=httpx.RequestError("Connection failed")
            )
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            response = client.get("/auth/me")

            assert response.status_code == 503
            data = response.json()
            assert data["authenticated"] is False
            assert "Auth service unavailable" in data["error"]


class TestLogoutEndpoint:
    """Test /auth/logout endpoint."""

    @pytest.mark.asyncio
    async def test_logout_success(self, client):
        """Test successful logout."""
        with patch("utils.auth.AuditLogger") as mock_audit:
            mock_audit.log_auth_event = Mock()

            # Mock session
            with patch("fastapi.Request.session", {"user_email": "test@test.com"}):
                response = client.post("/auth/logout")

                assert response.status_code == 200
                data = response.json()
                assert "Logged out successfully" in data["message"]

    @pytest.mark.asyncio
    async def test_logout_with_token_revocation(self, client):
        """Test logout with JWT token revocation."""
        with patch("utils.auth.AuditLogger") as mock_audit:
            mock_audit.log_auth_event = Mock()

            with patch("api.auth.revoke_token", return_value=True):
                response = client.post(
                    "/auth/logout",
                    headers={"Authorization": "Bearer test-token"},
                )

                assert response.status_code == 200
                data = response.json()
                assert data["token_revoked"] is True


class TestAuthEdgeCases:
    """Test edge cases in auth endpoints."""

    @pytest.mark.asyncio
    async def test_auth_me_with_cookies(self, client):
        """Test /auth/me using cookies instead of headers."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"email": "cookie@test.com"}
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            response = client.get(
                "/auth/me",
                cookies={"session_id": "test-session"},
            )

            # Should forward cookies to control-plane
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_auth_me_timeout(self, client):
        """Test /auth/me with timeout."""
        import httpx

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            response = client.get("/auth/me")

            # Should handle timeout gracefully
            assert response.status_code == 503
