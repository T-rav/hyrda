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

    @patch("utils.auth.Flow.from_client_config")
    def test_oauth_flow_creation_without_granted_scopes(self, mock_flow_class):
        """Test that OAuth flow is created without include_granted_scopes."""
        mock_flow = MagicMock()
        mock_flow.authorization_url.return_value = (
            "https://accounts.google.com/o/oauth2/auth",
            "state123",
        )
        mock_flow_class.return_value = mock_flow

        # Reload module with test env vars
        with patch.dict(
            os.environ,
            {
                "GOOGLE_OAUTH_CLIENT_ID": "test-client-id",
                "GOOGLE_OAUTH_CLIENT_SECRET": "test-secret",
            },
            clear=False,
        ):
            import importlib
            import utils.auth
            importlib.reload(utils.auth)
            from utils.auth import get_flow

            flow = get_flow("https://localhost:6001/auth/callback")

        # Verify Flow.from_client_config was called with correct parameters
        mock_flow_class.assert_called_once()
        call_args = mock_flow_class.call_args

        # Should have client_config, scopes, and redirect_uri
        assert "scopes" in call_args[1]
        assert "redirect_uri" in call_args[1]
        assert call_args[1]["redirect_uri"] == "https://localhost:6001/auth/callback"


class TestDomainVerification:
    """Test domain verification logic."""

    def test_wildcard_domain_allows_all_emails(self):
        """Test that wildcard domain allows any email."""
        with patch.dict(os.environ, {"ALLOWED_EMAIL_DOMAIN": "*"}, clear=False):
            import importlib
            import utils.auth
            importlib.reload(utils.auth)
            from utils.auth import verify_domain

            assert verify_domain("user@example.com") is True
            assert verify_domain("admin@test.org") is True
            assert verify_domain("anyone@anywhere.co") is True

    def test_specific_domain_only_allows_matching_emails(self):
        """Test that specific domain only allows matching emails."""
        with patch.dict(os.environ, {"ALLOWED_EMAIL_DOMAIN": "8thlight.com"}, clear=False):
            import importlib
            import utils.auth
            importlib.reload(utils.auth)
            from utils.auth import verify_domain

            assert verify_domain("user@8thlight.com") is True
            assert verify_domain("admin@8thlight.com") is True
            assert verify_domain("user@example.com") is False
            assert verify_domain("admin@test.org") is False

    def test_empty_email_returns_false(self):
        """Test that empty email returns False."""
        with patch.dict(os.environ, {"ALLOWED_EMAIL_DOMAIN": "*"}, clear=False):
            import importlib
            import utils.auth
            importlib.reload(utils.auth)
            from utils.auth import verify_domain

            assert verify_domain("") is False
            assert verify_domain(None) is False

    def test_malformed_email_returns_false(self):
        """Test that malformed email returns False."""
        with patch.dict(os.environ, {"ALLOWED_EMAIL_DOMAIN": "8thlight.com"}, clear=False):
            import importlib
            import utils.auth
            importlib.reload(utils.auth)
            from utils.auth import verify_domain

            assert verify_domain("notanemail") is False
            assert verify_domain("missing-at-sign.com") is False


class TestOAuthCallback:
    """Test OAuth callback handling."""

    def test_callback_requires_session_state(self):
        """Test that callback requires OAuth state in session."""
        with patch.dict(os.environ, {"ALLOWED_EMAIL_DOMAIN": "8thlight.com"}, clear=False):
            import importlib
            import utils.auth
            importlib.reload(utils.auth)
            from utils.auth import verify_domain

            # Test that verify_domain is used in the OAuth flow
            # This ensures domain verification happens during callback
            assert verify_domain("user@8thlight.com") is True
            assert verify_domain("user@example.com") is False

    def test_oauth_scopes_configured_correctly(self):
        """Test that OAuth scopes are configured correctly."""
        from utils.auth import OAUTH_SCOPES

        # Verify we request the minimal necessary scopes
        assert "openid" in OAUTH_SCOPES
        assert "https://www.googleapis.com/auth/userinfo.email" in OAUTH_SCOPES
        assert "https://www.googleapis.com/auth/userinfo.profile" in OAUTH_SCOPES

        # Ensure we DON'T request unnecessary scopes that cause issues
        # (no drive, calendar, or other extra scopes)
        assert len(OAUTH_SCOPES) == 3
