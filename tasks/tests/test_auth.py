"""Test suite for Tasks service OAuth authentication."""

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
from flask import Flask, session

# Add tasks to path
tasks_dir = Path(__file__).parent.parent
if str(tasks_dir) not in sys.path:
    sys.path.insert(0, str(tasks_dir))

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
    # Set test database URL to avoid MySQL connection
    with patch.dict(os.environ, {
        "TASK_DATABASE_URL": "sqlite:///:memory:",
        "DATA_DATABASE_URL": "sqlite:///:memory:",
    }):
        from app import create_app

        flask_app = create_app()
        flask_app.config["TESTING"] = True
        flask_app.config["WTF_CSRF_ENABLED"] = False

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
            "SERVER_BASE_URL": "http://localhost:5001",
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

    def test_protected_endpoint_redirects_when_not_authenticated(self, client, mock_oauth_env):
        """Test that protected endpoints redirect to OAuth when not authenticated."""
        with patch("utils.auth.get_flow") as mock_get_flow:
            mock_flow = MagicMock()
            mock_flow.authorization_url.return_value = (
                "https://accounts.google.com/o/oauth2/auth?test",
                "test-state",
            )
            mock_get_flow.return_value = mock_flow

            response = client.get("/api/jobs")

            # Should redirect to Google OAuth
            assert response.status_code == 302
            assert "accounts.google.com" in response.location

    def test_protected_endpoint_allows_authenticated_user(self, client, mock_oauth_env):
        """Test that authenticated users can access protected endpoints."""
        with client.session_transaction() as sess:
            sess["user_email"] = "test@8thlight.com"
            sess["user_info"] = {"email": "test@8thlight.com"}

        response = client.get("/api/jobs")
        # Should succeed (may return 200 or other non-redirect status)
        assert response.status_code != 302
