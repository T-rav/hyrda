"""Test suite for OAuth authentication."""

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add control_plane to path BEFORE importing app
control_plane_dir = Path(__file__).parent.parent
if str(control_plane_dir) not in sys.path:
    sys.path.insert(0, str(control_plane_dir))

from utils.auth import (
    AuditLogger,
    get_flow,
    get_redirect_uri,
    verify_domain,
    verify_token,
)


@pytest.fixture
def app():
    """Get FastAPI app for testing."""
    from app import create_app

    fastapi_app = create_app()
    yield fastapi_app


@pytest.fixture
def client(app):
    """Create test client."""
    from starlette.testclient import TestClient

    return TestClient(app)


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
        with patch.dict(
            os.environ, {"ALLOWED_EMAIL_DOMAIN": "@example.com"}, clear=False
        ):
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
        with patch(
            "utils.auth.GOOGLE_CLIENT_ID", "test-client-id.apps.googleusercontent.com"
        ):
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
            with pytest.raises(
                utils.auth.AuthError, match="Google OAuth not configured"
            ):
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

        with patch(
            "utils.auth.GOOGLE_CLIENT_ID", "test-client-id.apps.googleusercontent.com"
        ):
            with pytest.raises(utils.auth.AuthError, match=r"Invalid token:.*"):
                verify_token("invalid-token")
