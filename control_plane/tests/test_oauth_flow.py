"""Tests for OAuth authentication flow."""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Add control_plane to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestOAuthScopeHandling:
    """Test OAuth scope handling to prevent scope mismatch errors."""

    @patch("api.auth.Flow.from_client_config")
    def test_oauth_flow_creation_without_granted_scopes(self, mock_flow_class):
        """Test that OAuth flow is created without include_granted_scopes."""
        from api.auth import router

        mock_flow = MagicMock()
        mock_flow.authorization_url.return_value = (
            "https://accounts.google.com/o/oauth2/auth",
            "state123",
        )
        mock_flow_class.return_value = mock_flow

        # Create test client
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        # Make login request
        with patch.dict(
            os.environ,
            {
                "GOOGLE_OAUTH_CLIENT_ID": "test-client-id",
                "GOOGLE_OAUTH_CLIENT_SECRET": "test-secret",
            },
        ):
            response = client.get("/auth/login?redirect=https://localhost:5001/")

        # Verify authorization_url was called without include_granted_scopes
        mock_flow.authorization_url.assert_called_once()
        call_kwargs = mock_flow.authorization_url.call_args[1]

        # Should have access_type and prompt, but NOT include_granted_scopes
        assert "access_type" in call_kwargs
        assert "prompt" in call_kwargs
        assert "include_granted_scopes" not in call_kwargs


class TestDomainVerification:
    """Test domain verification logic."""

    def test_wildcard_domain_allows_all_emails(self):
        """Test that wildcard domain allows any email."""
        from utils.auth import verify_domain

        # Set wildcard domain
        with patch.dict(os.environ, {"ALLOWED_EMAIL_DOMAIN": "*"}):
            assert verify_domain("user@example.com") is True
            assert verify_domain("admin@test.org") is True
            assert verify_domain("anyone@anywhere.co") is True

    def test_specific_domain_only_allows_matching_emails(self):
        """Test that specific domain only allows matching emails."""
        from utils.auth import verify_domain

        with patch.dict(os.environ, {"ALLOWED_EMAIL_DOMAIN": "8thlight.com"}):
            assert verify_domain("user@8thlight.com") is True
            assert verify_domain("admin@8thlight.com") is True
            assert verify_domain("user@example.com") is False
            assert verify_domain("admin@test.org") is False

    def test_empty_email_returns_false(self):
        """Test that empty email returns False."""
        from utils.auth import verify_domain

        with patch.dict(os.environ, {"ALLOWED_EMAIL_DOMAIN": "*"}):
            assert verify_domain("") is False
            assert verify_domain(None) is False

    def test_malformed_email_returns_false(self):
        """Test that malformed email returns False."""
        from utils.auth import verify_domain

        with patch.dict(os.environ, {"ALLOWED_EMAIL_DOMAIN": "8thlight.com"}):
            assert verify_domain("notanemail") is False
            assert verify_domain("missing-at-sign.com") is False


class TestOAuthCallback:
    """Test OAuth callback handling."""

    @pytest.mark.asyncio
    @patch("api.auth.Flow.from_client_config")
    async def test_callback_handles_scope_mismatch_gracefully(self, mock_flow_class):
        """Test that callback handles scope mismatch errors gracefully."""
        from api.auth import router

        # Mock flow that simulates Google returning extra scopes
        mock_flow = MagicMock()
        mock_flow.fetch_token.side_effect = Exception(
            "Scope has changed from 'openid email profile' to 'openid email profile drive.readonly'"
        )
        mock_flow_class.return_value = mock_flow

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        # Make callback request
        with patch.dict(
            os.environ,
            {
                "GOOGLE_OAUTH_CLIENT_ID": "test-client-id",
                "GOOGLE_OAUTH_CLIENT_SECRET": "test-secret",
            },
        ):
            response = client.get(
                "/auth/callback?code=test-code&state=test-state&scope=openid+email+profile"
            )

        # Should return authentication error, not crash
        assert response.status_code == 200
        assert "Authentication failed" in response.json()["detail"]

    @pytest.mark.asyncio
    @patch("api.auth.Flow.from_client_config")
    async def test_successful_oauth_callback_sets_session(self, mock_flow_class):
        """Test that successful OAuth callback sets session data."""
        from api.auth import router

        # Mock successful OAuth flow
        mock_flow = MagicMock()
        mock_credentials = MagicMock()
        mock_credentials.id_token = {
            "email": "user@8thlight.com",
            "name": "Test User",
            "picture": "https://example.com/pic.jpg",
        }
        mock_flow.fetch_token.return_value = None
        mock_flow.credentials = mock_credentials
        mock_flow_class.return_value = mock_flow

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        # Make callback request
        with patch.dict(
            os.environ,
            {
                "GOOGLE_OAUTH_CLIENT_ID": "test-client-id",
                "GOOGLE_OAUTH_CLIENT_SECRET": "test-secret",
                "ALLOWED_EMAIL_DOMAIN": "*",
            },
        ):
            with patch("api.auth.verify_domain", return_value=True):
                response = client.get(
                    "/auth/callback?code=test-code&state=test-state&redirect=https://localhost:5001/"
                )

        # Should redirect to the redirect URL
        assert response.status_code == 302
        assert "localhost:5001" in response.headers["location"]
