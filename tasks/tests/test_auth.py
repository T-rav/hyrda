"""Test suite for Tasks service OAuth authentication."""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add tasks to path
tasks_dir = Path(__file__).parent.parent
if str(tasks_dir) not in sys.path:
    sys.path.insert(0, str(tasks_dir))

import utils.auth  # noqa: E402, I001

from tests.factories import FlaskAppFactory, MockJobRegistryFactory, MockSchedulerFactory  # noqa: E402


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
    old_flask_env = os.environ.get("FLASK_ENV")

    # Set development environment for tests
    os.environ["ENVIRONMENT"] = "development"
    os.environ["FLASK_ENV"] = "development"

    try:
        test_app = FlaskAppFactory.create_test_app(
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
        if old_flask_env:
            os.environ["FLASK_ENV"] = old_flask_env
        else:
            os.environ.pop("FLASK_ENV", None)


@pytest.fixture
def auth_client(auth_app):
    """Authenticated client for auth tests."""
    return FlaskAppFactory.create_test_client(auth_app, authenticated=True)


@pytest.fixture
def unauth_client(auth_app):
    """Unauthenticated client for auth tests."""
    return FlaskAppFactory.create_test_client(auth_app, authenticated=False)


@pytest.fixture
def mock_oauth_env():
    """Mock OAuth environment variables."""
    env_vars = {
        "GOOGLE_OAUTH_CLIENT_ID": "test-client-id.apps.googleusercontent.com",
        "GOOGLE_OAUTH_CLIENT_SECRET": "test-client-secret",
        "ALLOWED_EMAIL_DOMAIN": "8thlight.com",  # Without @ - verify_domain() adds it
        "SERVER_BASE_URL": "http://localhost:5001",
        "ENVIRONMENT": "development",  # Prevent SECRET_KEY production validation in tests
        "FLASK_ENV": "development",
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

    def test_protected_endpoint_returns_401_when_not_authenticated(
        self, unauth_client, mock_oauth_env
    ):
        """Test that protected endpoints return 401 when not authenticated."""
        # With dependency injection, unauthenticated requests get 401
        response = unauth_client.get("/api/jobs")
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data

    def test_protected_endpoint_allows_authenticated_user(self, client, mock_oauth_env):
        """Test that authenticated users can access protected endpoints."""
        # The client fixture uses dependency override for auth
        response = client.get("/api/jobs")
        # Should succeed
        assert response.status_code == 200
