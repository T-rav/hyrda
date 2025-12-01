"""Test suite for OAuth authentication."""

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
from flask import Flask, session

# Add control_plane to path BEFORE importing app
control_plane_dir = Path(__file__).parent.parent
if str(control_plane_dir) not in sys.path:
    sys.path.insert(0, str(control_plane_dir))

from utils.auth import (
    AuditLogger,
    AuthError,
    flask_auth_callback,
    flask_logout,
    get_flow,
    get_redirect_uri,
    verify_domain,
    verify_token,
)


@pytest.fixture
def app():
    """Get Flask app for testing."""
    from app import app as flask_app

    flask_app.config["TESTING"] = True
    flask_app.config["WTF_CSRF_ENABLED"] = False
    flask_app.config["SECRET_KEY"] = "test-secret-key"

    yield flask_app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def mock_oauth_env():
    """Mock OAuth environment variables."""
    with patch.dict(
        os.environ,
        {
            "GOOGLE_OAUTH_CLIENT_ID": "test-client-id.apps.googleusercontent.com",
            "GOOGLE_OAUTH_CLIENT_SECRET": "test-client-secret",
            "ALLOWED_EMAIL_DOMAIN": "@8thlight.com",
            "CONTROL_PLANE_BASE_URL": "http://localhost:6001",
        },
        clear=False,
    ):
        yield


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

    def test_verify_domain_rejects_empty(self, mock_oauth_env):
        """Test that empty email is rejected."""
        assert verify_domain("") is False
        assert verify_domain(None) is False

    def test_verify_domain_custom_domain(self):
        """Test custom domain configuration."""
        with patch.dict(os.environ, {"ALLOWED_EMAIL_DOMAIN": "@example.com"}, clear=False):
            # Reload module to pick up new env var
            import importlib
            import utils.auth

            importlib.reload(utils.auth)
            assert utils.auth.verify_domain("user@example.com") is True
            assert utils.auth.verify_domain("user@8thlight.com") is False
            # Restore
            importlib.reload(utils.auth)


class TestAuditLogging:
    """Test audit logging functionality."""

    @patch("utils.auth.logger")
    def test_log_auth_event_success(self, mock_logger, mock_oauth_env):
        """Test successful auth event logging."""
        AuditLogger.log_auth_event(
            "login_success",
            email="test@8thlight.com",
            ip_address="127.0.0.1",
            success=True,
        )

        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert "AUTH_AUDIT: login_success" in call_args[0][0]
        assert call_args[1]["extra"]["email"] == "test@8thlight.com"
        assert call_args[1]["extra"]["success"] is True

    @patch("utils.auth.logger")
    def test_log_auth_event_failure(self, mock_logger, mock_oauth_env):
        """Test failed auth event logging."""
        AuditLogger.log_auth_event(
            "login_failed",
            email="test@example.com",
            success=False,
            error="Invalid domain",
        )

        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args
        assert "AUTH_AUDIT: login_failed FAILED" in call_args[0][0]
        assert call_args[1]["extra"]["error"] == "Invalid domain"


class TestOAuthFlow:
    """Test OAuth flow creation."""

    def test_get_redirect_uri(self, mock_oauth_env):
        """Test redirect URI construction."""
        uri = get_redirect_uri("http://localhost:6001", "/auth/callback")
        assert uri == "http://localhost:6001/auth/callback"

        uri = get_redirect_uri("http://localhost:6001/", "/auth/callback")
        assert uri == "http://localhost:6001/auth/callback"

    def test_get_flow_creates_flow(self, mock_oauth_env):
        """Test that get_flow creates a Flow object."""
        with patch("utils.auth.GOOGLE_CLIENT_ID", "test-client-id.apps.googleusercontent.com"):
            with patch("utils.auth.GOOGLE_CLIENT_SECRET", "test-client-secret"):
                redirect_uri = "http://localhost:6001/auth/callback"
                flow = get_flow(redirect_uri)

                assert flow is not None
                assert flow.redirect_uri == redirect_uri

    def test_get_flow_missing_credentials(self):
        """Test that missing credentials raise AuthError."""
        with patch.dict(os.environ, {}, clear=True):
            import importlib
            import utils.auth

            importlib.reload(utils.auth)
            # After reload, use the AuthError from the reloaded module
            with pytest.raises(utils.auth.AuthError, match="Google OAuth not configured"):
                utils.auth.get_flow("http://localhost:6001/auth/callback")
            # Restore
            importlib.reload(utils.auth)


class TestTokenVerification:
    """Test token verification."""

    @patch("utils.auth.id_token.verify_oauth2_token")
    @patch("utils.auth.Request")
    def test_verify_token_success(self, mock_request, mock_verify, mock_oauth_env):
        """Test successful token verification."""
        mock_verify.return_value = {
            "email": "test@8thlight.com",
            "name": "Test User",
            "picture": "https://example.com/pic.jpg",
        }

        token = "test-token"
        result = verify_token(token)

        assert result["email"] == "test@8thlight.com"
        mock_verify.assert_called_once()

    @patch("utils.auth.id_token.verify_oauth2_token")
    @patch("utils.auth.Request")
    def test_verify_token_invalid(self, mock_request, mock_verify, mock_oauth_env):
        """Test invalid token raises AuthError."""
        import utils.auth  # Import here to get fresh reference

        mock_verify.side_effect = ValueError("Invalid token")

        with patch("utils.auth.GOOGLE_CLIENT_ID", "test-client-id.apps.googleusercontent.com"):
            with pytest.raises(utils.auth.AuthError, match=r"Invalid token:.*"):
                verify_token("invalid-token")


class TestFlaskAuthCallback:
    """Test Flask OAuth callback handler."""

    @patch("utils.auth.get_flow")
    @patch("utils.auth.verify_token")
    def test_auth_callback_success(self, mock_verify_token, mock_get_flow, app, mock_oauth_env):
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

        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["oauth_state"] = "test-state"
                sess["oauth_redirect"] = "/api/agents"

            # Call within request context
            with app.test_request_context("http://localhost:6001/auth/callback?code=test-code&state=test-state"):
                # Set up session for the request context
                session["oauth_state"] = "test-state"
                session["oauth_redirect"] = "/api/agents"

                response = flask_auth_callback("http://localhost:6001", "/auth/callback")

                # Should redirect to original URL
                assert response.status_code == 302
                assert "/api/agents" in response.location

    @patch("utils.auth.get_flow")
    def test_auth_callback_missing_state(self, mock_get_flow, app, mock_oauth_env):
        """Test callback with missing state."""
        with app.test_request_context("http://localhost:6001/auth/callback?code=test-code&state=test-state"):
            # No oauth_state in session
            result = flask_auth_callback("http://localhost:6001", "/auth/callback")
            # Result is a tuple (response, status_code) when called directly
            if isinstance(result, tuple):
                response, status_code = result
                assert status_code == 400
            else:
                assert result.status_code == 400

    @patch("utils.auth.get_flow")
    @patch("utils.auth.verify_token")
    def test_auth_callback_invalid_domain(self, mock_verify_token, mock_get_flow, app, mock_oauth_env):
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

        with app.test_request_context("http://localhost:6001/auth/callback?code=test-code&state=test-state"):
            # Set up session
            session["oauth_state"] = "test-state"
            session["oauth_redirect"] = "/api/agents"

            result = flask_auth_callback("http://localhost:6001", "/auth/callback")

            # Result is a tuple (response, status_code) when called directly
            if isinstance(result, tuple):
                response, status_code = result
                assert status_code == 403
                data = json.loads(response.data)
            else:
                assert result.status_code == 403
                data = json.loads(result.data)
            assert "restricted" in data["error"].lower()


class TestFlaskLogout:
    """Test Flask logout handler."""

    def test_logout_clears_session(self, app, mock_oauth_env):
        """Test that logout clears session."""
        with app.test_request_context("/auth/logout"):
            # Set up session
            session["user_email"] = "test@8thlight.com"
            session["user_info"] = {"email": "test@8thlight.com"}

            response = flask_logout()

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["message"] == "Logged out successfully"
            # Session should be cleared
            assert "user_email" not in session
            assert "user_info" not in session


class TestAuthMiddleware:
    """Test authentication middleware."""

    def test_health_endpoint_bypasses_auth(self, client, mock_oauth_env):
        """Test that health endpoints bypass authentication."""
        response = client.get("/health")
        assert response.status_code == 200

        response = client.get("/api/health")
        assert response.status_code == 200

    def test_auth_endpoints_bypass_auth(self, client, mock_oauth_env):
        """Test that auth endpoints bypass authentication."""
        response = client.get("/auth/callback")
        # May return error but shouldn't redirect to OAuth
        assert response.status_code != 302 or "/accounts.google.com" not in response.location

    def test_protected_endpoint_redirects_when_not_authenticated(self, client, mock_oauth_env):
        """Test that protected endpoints redirect to OAuth when not authenticated."""
        with patch("utils.auth.get_flow") as mock_get_flow:
            mock_flow = MagicMock()
            mock_flow.authorization_url.return_value = (
                "https://accounts.google.com/o/oauth2/auth?test",
                "test-state",
            )
            mock_get_flow.return_value = mock_flow

            response = client.get("/api/agents")

            # Should redirect to Google OAuth
            assert response.status_code == 302
            assert "accounts.google.com" in response.location

    def test_protected_endpoint_allows_authenticated_user(self, client, mock_oauth_env):
        """Test that authenticated users can access protected endpoints."""
        with client.session_transaction() as sess:
            sess["user_email"] = "test@8thlight.com"
            sess["user_info"] = {"email": "test@8thlight.com"}

        response = client.get("/api/agents")
        # Should succeed (may return 200 or other non-redirect status)
        assert response.status_code != 302

    def test_protected_endpoint_rejects_wrong_domain(self, client, mock_oauth_env):
        """Test that wrong domain users are rejected."""
        with client.session_transaction() as sess:
            sess["user_email"] = "test@example.com"
            sess["user_info"] = {"email": "test@example.com"}

        with patch("utils.auth.get_flow") as mock_get_flow:
            mock_flow = MagicMock()
            mock_flow.authorization_url.return_value = (
                "https://accounts.google.com/o/oauth2/auth?test",
                "test-state",
            )
            mock_get_flow.return_value = mock_flow

            response = client.get("/api/agents")

            # Should redirect to OAuth (session cleared)
            assert response.status_code == 302
