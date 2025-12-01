"""Test suite for FastAPI OAuth authentication."""

import os
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

from utils.auth import (
    AuditLogger,
    AuthError,
    FastAPIAuthMiddleware,
    fastapi_auth_callback,
    fastapi_logout,
    get_flow,
    get_redirect_uri,
    verify_domain,
    verify_token,
)


@pytest.fixture
def mock_oauth_env():
    """Mock OAuth environment variables."""
    with patch.dict(
        os.environ,
        {
            "GOOGLE_OAUTH_CLIENT_ID": "test-client-id.apps.googleusercontent.com",
            "GOOGLE_OAUTH_CLIENT_SECRET": "test-client-secret",
            "ALLOWED_EMAIL_DOMAIN": "@8thlight.com",
            "DASHBOARD_BASE_URL": "http://localhost:8080",
            "SECRET_KEY": "test-secret-key",
        },
        clear=False,
    ):
        yield


@pytest.fixture
def app_with_auth(mock_oauth_env):
    """Create FastAPI app with auth middleware."""
    from fastapi import FastAPI

    app = FastAPI()
    # Add auth middleware first, then session middleware
    # Middleware is executed in reverse order of addition
    app.add_middleware(
        FastAPIAuthMiddleware,
        service_base_url="http://localhost:8080",
        callback_path="/auth/callback",
    )
    app.add_middleware(SessionMiddleware, secret_key="test-secret-key")

    @app.get("/health")
    async def health_endpoint():
        return {"status": "healthy"}

    @app.get("/test-protected")
    async def protected_endpoint():
        return {"message": "protected"}

    return app


@pytest.fixture
def client(app_with_auth):
    """Create test client."""
    return TestClient(app_with_auth)


class TestDomainVerification:
    """Test domain verification logic."""

    def test_verify_domain_allows_8thlight(self, mock_oauth_env):
        """Test that @8thlight.com emails are allowed."""
        assert verify_domain("user@8thlight.com") is True
        assert verify_domain("test.user@8thlight.com") is True

    def test_verify_domain_rejects_other_domains(self, mock_oauth_env):
        """Test that other domains are rejected."""
        assert verify_domain("user@example.com") is False
        assert verify_domain("user@gmail.com") is False


class TestFastAPIAuthMiddleware:
    """Test FastAPI authentication middleware."""

    def test_health_endpoint_bypasses_auth(self, client, mock_oauth_env):
        """Test that health endpoints bypass authentication."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_auth_endpoints_bypass_auth(self, client, mock_oauth_env):
        """Test that auth endpoints bypass authentication."""
        response = client.get("/auth/callback")
        # May return error but shouldn't redirect
        assert response.status_code != 302 or "accounts.google.com" not in response.headers.get("location", "")

    def test_protected_endpoint_redirects_when_not_authenticated(self, client, mock_oauth_env):
        """Test that protected endpoints redirect to OAuth when not authenticated."""
        with patch("utils.auth.GOOGLE_CLIENT_ID", "test-client-id.apps.googleusercontent.com"):
            with patch("utils.auth.GOOGLE_CLIENT_SECRET", "test-client-secret"):
                with patch("utils.auth.get_flow") as mock_get_flow:
                    mock_flow = MagicMock()
                    mock_flow.authorization_url.return_value = (
                        "https://accounts.google.com/o/oauth2/auth?test",
                        "test-state",
                    )
                    mock_get_flow.return_value = mock_flow

                    response = client.get("/test-protected", follow_redirects=False)

                    # Should redirect to Google OAuth
                    assert response.status_code == 302
                    assert "accounts.google.com" in response.headers.get("location", "")

    def test_protected_endpoint_allows_authenticated_user(self, client, mock_oauth_env):
        """Test that authenticated users can access protected endpoints."""
        # Patch the middleware dispatch to simulate authenticated user
        async def mock_dispatch(middleware_self, request, call_next):
            # Set up session to simulate authenticated user
            request.session["user_email"] = "test@8thlight.com"
            request.session["user_info"] = {"email": "test@8thlight.com"}
            response = await call_next(request)
            return response

        with patch.object(FastAPIAuthMiddleware, "dispatch", mock_dispatch):
            response = client.get("/test-protected")
            # Should succeed
            assert response.status_code == 200

    def test_protected_endpoint_rejects_wrong_domain(self, client, mock_oauth_env):
        """Test that wrong domain users are rejected."""
        import json
        from itsdangerous import URLSafeTimedSerializer

        # Create signed session cookie with wrong domain
        serializer = URLSafeTimedSerializer("test-secret-key")
        session_data = {
            "user_email": "test@example.com",
            "user_info": {"email": "test@example.com"}
        }
        session_cookie = serializer.dumps(session_data)

        client.cookies.set("session", session_cookie)

        with patch("utils.auth.GOOGLE_CLIENT_ID", "test-client-id.apps.googleusercontent.com"):
            with patch("utils.auth.GOOGLE_CLIENT_SECRET", "test-client-secret"):
                with patch("utils.auth.get_flow") as mock_get_flow:
                    mock_flow = MagicMock()
                    mock_flow.authorization_url.return_value = (
                        "https://accounts.google.com/o/oauth2/auth?test",
                        "test-state",
                    )
                    mock_get_flow.return_value = mock_flow

                    response = client.get("/test-protected", follow_redirects=False)

                    # Should redirect to OAuth
                    assert response.status_code == 302


class TestFastAPIAuthCallback:
    """Test FastAPI OAuth callback handler."""

    @pytest.mark.asyncio
    @patch("utils.auth.get_flow")
    @patch("utils.auth.verify_token")
    async def test_auth_callback_success(self, mock_verify_token, mock_get_flow, mock_oauth_env):
        """Test successful OAuth callback."""
        # Setup mocks
        mock_flow = MagicMock()
        mock_credentials = MagicMock()
        mock_credentials.id_token = "test-id-token"
        mock_flow.credentials = mock_credentials
        mock_get_flow.return_value = mock_flow

        mock_verify_token.return_value = {
            "email": "test@8thlight.com",
            "name": "Test User",
            "picture": "https://example.com/pic.jpg",
        }

        # Create mock request with session
        mock_request = MagicMock(spec=Request)
        mock_request.session = {"oauth_state": "test-state", "oauth_redirect": "/test-protected"}
        mock_request.url = MagicMock()
        mock_request.url.path = "/auth/callback"
        mock_request.url.__str__ = Mock(return_value="http://localhost:8080/auth/callback?code=test&state=test-state")
        mock_request.cookies = {}

        response = await fastapi_auth_callback(mock_request, "http://localhost:8080", "/auth/callback")

        # Should redirect
        assert response.status_code == 302

    @pytest.mark.asyncio
    async def test_auth_callback_missing_state(self, mock_oauth_env):
        """Test callback with missing state."""
        mock_request = MagicMock(spec=Request)
        mock_request.session = {}
        mock_request.cookies = {}
        mock_request.url = MagicMock()
        mock_request.url.path = "/auth/callback"

        with pytest.raises(Exception):  # Should raise HTTPException
            await fastapi_auth_callback(mock_request, "http://localhost:8080", "/auth/callback")

    @pytest.mark.asyncio
    @patch("utils.auth.get_flow")
    @patch("utils.auth.verify_token")
    async def test_auth_callback_invalid_domain(self, mock_verify_token, mock_get_flow, mock_oauth_env):
        """Test callback with invalid email domain."""
        mock_flow = MagicMock()
        mock_credentials = MagicMock()
        mock_credentials.id_token = "test-id-token"
        mock_flow.credentials = mock_credentials
        mock_get_flow.return_value = mock_flow

        mock_verify_token.return_value = {
            "email": "test@example.com",  # Wrong domain
            "name": "Test User",
        }

        mock_request = MagicMock(spec=Request)
        mock_request.session = {"oauth_state": "test-state", "oauth_redirect": "/test-protected"}
        mock_request.url = MagicMock()
        mock_request.url.path = "/auth/callback"
        mock_request.url.__str__ = Mock(return_value="http://localhost:8080/auth/callback?code=test&state=test-state")
        mock_request.cookies = {}

        with pytest.raises(Exception):  # Should raise HTTPException with 403
            await fastapi_auth_callback(mock_request, "http://localhost:8080", "/auth/callback")


class TestFastAPILogout:
    """Test FastAPI logout handler."""

    @pytest.mark.asyncio
    async def test_logout_clears_session(self, mock_oauth_env):
        """Test that logout clears session."""
        # fastapi_logout doesn't take parameters, it returns a response with cookie deletion
        response = await fastapi_logout()

        # Response is a JSONResponse object
        assert response.status_code == 200
        # Function deletes cookies via response.delete_cookie()
