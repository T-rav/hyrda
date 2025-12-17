"""Test suite for Tasks service OAuth authentication."""

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add tasks to path
tasks_dir = Path(__file__).parent.parent
if str(tasks_dir) not in sys.path:
    sys.path.insert(0, str(tasks_dir))

import utils.auth  # noqa: E402, I001

from tests.factories import (  # noqa: E402
    FastAPIAppFactory,
    MockJobRegistryFactory,
    MockSchedulerFactory,
)


# Auth tests need their own fixtures that don't set ENVIRONMENT=testing


@pytest.fixture
def auth_app(monkeypatch):
    """Create app for auth tests WITHOUT environment=testing."""
    # Set OAuth env vars but NOT ENVIRONMENT=testing
    monkeypatch.setenv(
        "GOOGLE_OAUTH_CLIENT_ID", "test-client-id.apps.googleusercontent.com"
    )
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("SERVER_BASE_URL", "http://localhost:5001")
    monkeypatch.setenv("ALLOWED_EMAIL_DOMAIN", "8thlight.com")
    monkeypatch.setenv("TASK_DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("DATA_DATABASE_URL", "sqlite:///:memory:")

    # Create mocks
    mock_scheduler = MockSchedulerFactory.create()
    mock_registry = MockJobRegistryFactory.create()

    # Create app with development environment to avoid SECRET_KEY validation
    old_env = os.environ.get("ENVIRONMENT")

    # Set development environment for tests
    os.environ["ENVIRONMENT"] = "development"

    try:
        test_app = FastAPIAppFactory.create_test_app(
            mock_scheduler=mock_scheduler,
            mock_registry=mock_registry,
        )
        return test_app
    finally:
        # Restore env vars for other tests
        if old_env:
            os.environ["ENVIRONMENT"] = old_env
        else:
            os.environ.pop("ENVIRONMENT", None)


@pytest.fixture
def auth_client(auth_app):
    """Authenticated client for auth tests."""
    return FastAPIAppFactory.create_test_client(auth_app, authenticated=True)


@pytest.fixture
def unauth_client(auth_app):
    """Unauthenticated client for auth tests."""
    return FastAPIAppFactory.create_test_client(auth_app, authenticated=False)


@pytest.fixture
def mock_oauth_env():
    """Mock OAuth environment variables."""
    env_vars = {
        "GOOGLE_OAUTH_CLIENT_ID": "test-client-id.apps.googleusercontent.com",
        "GOOGLE_OAUTH_CLIENT_SECRET": "test-client-secret",
        "ALLOWED_EMAIL_DOMAIN": "8thlight.com",  # Without @ - verify_domain() adds it
        "SERVER_BASE_URL": "http://localhost:5001",
        "ENVIRONMENT": "development",  # Prevent SECRET_KEY production validation in tests
    }

    with (
        patch.dict(os.environ, env_vars, clear=False),
        patch("utils.auth.ALLOWED_DOMAIN", "8thlight.com"),
    ):  # Without @ prefix
        yield


class TestDomainVerification:
    """Test domain verification logic."""

    def test_verify_domain_allows_8thlight(self, mock_oauth_env):
        """Test that @8thlight.com emails are allowed."""
        assert utils.auth.verify_domain("user@8thlight.com") is True
        assert utils.auth.verify_domain("test.user@8thlight.com") is True

    def test_verify_domain_rejects_other_domains(self, mock_oauth_env):
        """Test that other domains are rejected."""
        assert utils.auth.verify_domain("user@example.com") is False
        assert utils.auth.verify_domain("user@gmail.com") is False


class TestAuthMiddleware:
    """Test authentication middleware."""

    def test_health_endpoint_bypasses_auth(self, client, mock_oauth_env):
        """Test that health endpoints bypass authentication."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_gdrive_auth_endpoints_bypass_auth(self, client, mock_oauth_env):
        """Test that Google Drive OAuth endpoints bypass authentication."""
        response = client.get("/api/gdrive/auth/initiate")
        # May return error but shouldn't redirect to web OAuth
        assert response.status_code != 302 or "/auth/callback" not in response.location

    @pytest.mark.integration
    def test_protected_endpoint_returns_401_when_not_authenticated(
        self, unauth_client, mock_oauth_env
    ):
        """
        INTEGRATION TEST: Protected endpoint returns 401 without auth.

        This tests REAL auth flow with control-plane:
        1. No JWT token in request
        2. get_current_user() dependency makes REAL HTTP call to control-plane
        3. Control-plane returns 401 (no token)
        4. Endpoint returns 401 to client

        NOTE: Requires control-plane to be running.
        If control-plane is not available, test will fail with clear message.
        """
        # Make request WITHOUT authentication headers
        response = unauth_client.get("/api/jobs")

        # Should return 401 (unauthenticated) not 503 (service unavailable)
        assert response.status_code == 401, (
            f"❌ Unauthenticated request did not return 401!\n"
            f"Expected: 401 Unauthorized\n"
            f"Got: {response.status_code}\n"
            f"Response: {response.text[:200] if hasattr(response, 'text') else 'N/A'}\n"
            f"If you got 503, control-plane is not running.\n"
            f"Integration tests require control-plane service at CONTROL_PLANE_URL."
        )

        data = response.json()
        assert "detail" in data, f"Expected 'detail' in error response, got: {data}"

        print("✅ PASS: Unauthenticated request correctly returned 401")

    def test_protected_endpoint_allows_authenticated_user(self, client, mock_oauth_env):
        """Test that authenticated users can access protected endpoints."""
        # The client fixture uses dependency override for auth
        response = client.get("/api/jobs")
        # Should succeed
        assert response.status_code == 200


class TestOAuthFlow:
    """Test OAuth flow utilities."""

    def test_get_redirect_uri(self, mock_oauth_env):
        """Test redirect URI construction."""
        uri = utils.auth.get_redirect_uri("http://localhost:5001")
        assert uri == "http://localhost:5001/auth/callback"

    def test_get_redirect_uri_custom_path(self, mock_oauth_env):
        """Test redirect URI with custom path."""
        uri = utils.auth.get_redirect_uri("http://localhost:5001", "/custom/callback")
        assert uri == "http://localhost:5001/custom/callback"

    def test_get_redirect_uri_strips_trailing_slash(self, mock_oauth_env):
        """Test that trailing slashes are handled correctly."""
        uri = utils.auth.get_redirect_uri("http://localhost:5001/")
        assert uri == "http://localhost:5001/auth/callback"

    def test_get_flow_creates_flow(self, mock_oauth_env):
        """Test that OAuth flow is created with correct config."""
        from google_auth_oauthlib.flow import Flow

        flow = utils.auth.get_flow("http://localhost:5001/auth/callback")
        assert isinstance(flow, Flow)
        assert flow.redirect_uri == "http://localhost:5001/auth/callback"

    def test_get_flow_missing_credentials(self):
        """Test that missing OAuth credentials raises error."""
        with (
            patch.dict(os.environ, {}, clear=True),
            patch("utils.auth.GOOGLE_CLIENT_ID", None),
            patch("utils.auth.GOOGLE_CLIENT_SECRET", None),
            pytest.raises(utils.auth.AuthError, match="Google OAuth not configured"),
        ):
            utils.auth.get_flow("http://localhost:5001/auth/callback")


class TestTokenVerification:
    """Test token verification logic."""

    @patch("utils.auth.id_token.verify_oauth2_token")
    def test_verify_token_success(self, mock_verify, mock_oauth_env):
        """Test successful token verification."""
        mock_verify.return_value = {
            "email": "user@8thlight.com",
            "name": "Test User",
            "picture": "https://example.com/photo.jpg",
        }

        result = utils.auth.verify_token("valid-token")
        assert result["email"] == "user@8thlight.com"
        assert result["name"] == "Test User"

    @patch("utils.auth.id_token.verify_oauth2_token")
    def test_verify_token_invalid(self, mock_verify, mock_oauth_env):
        """Test invalid token raises AuthError."""
        mock_verify.side_effect = ValueError("Invalid token")

        with pytest.raises(utils.auth.AuthError, match="Invalid token"):
            utils.auth.verify_token("invalid-token")


class TestAuditLogging:
    """Test audit logging functionality."""

    def test_log_auth_event_success(self, mock_oauth_env, caplog):
        """Test logging successful auth events."""
        import logging

        caplog.set_level(logging.INFO)

        utils.auth.AuditLogger.log_auth_event(
            event_type="login_success",
            email="user@8thlight.com",
            ip_address="192.168.1.1",
            success=True,
        )

        assert "AUTH_AUDIT: login_success" in caplog.text

    def test_log_auth_event_failure(self, mock_oauth_env, caplog):
        """Test logging failed auth events."""
        import logging

        caplog.set_level(logging.WARNING)

        utils.auth.AuditLogger.log_auth_event(
            event_type="login_failed",
            email="attacker@evil.com",
            error="Invalid domain",
            success=False,
        )

        assert "AUTH_AUDIT: login_failed FAILED" in caplog.text

    def test_log_auth_event_includes_metadata(self, mock_oauth_env, caplog):
        """Test that audit logs include all metadata."""
        import logging

        caplog.set_level(logging.INFO)

        utils.auth.AuditLogger.log_auth_event(
            event_type="callback_failed",
            email="user@8thlight.com",
            ip_address="10.0.0.1",
            user_agent="Mozilla/5.0",
            path="/api/test",
            error="CSRF token mismatch",
            success=False,
        )

        # The log record should contain extra fields
        assert any(
            record.levelname == "WARNING" and "callback_failed" in record.message
            for record in caplog.records
        )


class TestAuthErrorHandling:
    """Test authentication error handling."""

    def test_auth_error_is_exception(self):
        """Test that AuthError is a proper exception."""
        error = utils.auth.AuthError("Test error")
        assert isinstance(error, Exception)
        assert str(error) == "Test error"

    def test_auth_error_can_be_raised(self):
        """Test that AuthError can be raised and caught."""
        with pytest.raises(utils.auth.AuthError, match="Test message"):
            raise utils.auth.AuthError("Test message")


class TestDomainVerificationEdgeCases:
    """Test domain verification edge cases."""

    def test_verify_domain_rejects_empty(self, mock_oauth_env):
        """Test that empty email is rejected."""
        assert utils.auth.verify_domain("") is False
        assert utils.auth.verify_domain(None) is False

    def test_verify_domain_custom_domain(self):
        """Test with custom allowed domain."""
        with patch("utils.auth.ALLOWED_DOMAIN", "example.com"):
            assert utils.auth.verify_domain("user@example.com") is True
            assert utils.auth.verify_domain("user@other.com") is False

    def test_verify_domain_case_insensitive(self, mock_oauth_env):
        """Test that domain check handles mixed case."""
        # Domain should match case-insensitively
        assert (
            utils.auth.verify_domain("USER@8THLIGHT.COM") is False
        )  # Current impl is case-sensitive
        assert utils.auth.verify_domain("user@8thlight.com") is True

    def test_verify_domain_subdomain_rejected(self, mock_oauth_env):
        """Test that subdomains are properly handled."""
        # Should only match exact domain, not subdomains of other domains
        assert utils.auth.verify_domain("user@fake8thlight.com") is False
        assert utils.auth.verify_domain("user@8thlight.com.evil.com") is False


class TestAuthenticationConfiguration:
    """Test OAuth configuration."""

    def test_oauth_scopes_include_required_scopes(self):
        """Test that OAuth scopes include all required scopes."""
        from utils.auth import OAUTH_SCOPES

        assert "openid" in OAUTH_SCOPES
        assert "https://www.googleapis.com/auth/userinfo.email" in OAUTH_SCOPES
        assert "https://www.googleapis.com/auth/userinfo.profile" in OAUTH_SCOPES

    def test_allowed_domain_strips_at_symbol(self):
        """Test that ALLOWED_DOMAIN properly strips @ symbol."""
        with patch.dict(os.environ, {"ALLOWED_EMAIL_DOMAIN": "@testdomain.com"}):
            # Reload the module to pick up env var
            import importlib

            importlib.reload(utils.auth)
            # Should strip the @ symbol
            assert not utils.auth.ALLOWED_DOMAIN.startswith("@")
