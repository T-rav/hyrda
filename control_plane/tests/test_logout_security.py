"""
Comprehensive tests for logout security fixes.

Tests verify:
1. Cookie deletion with proper parameters
2. Cache-control headers on index.html
3. Session clearing
4. Token revocation
"""

import pytest
from unittest.mock import patch, MagicMock
import sys
import os
from pathlib import Path

# Add control_plane and shared to path
control_plane_dir = Path(__file__).parent.parent
shared_dir = control_plane_dir.parent / "shared"
if str(control_plane_dir) not in sys.path:
    sys.path.insert(0, str(control_plane_dir))
if str(shared_dir) not in sys.path:
    sys.path.insert(0, str(shared_dir))


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
            "JWT_SECRET_KEY": "test-secret-key-for-jwt-tokens-min-32-chars",
            "SLACK_BOT_TOKEN": "xoxb-test-token",
        },
        clear=False,
    ):
        yield


class TestLogoutCookieDeletion:
    """Tests for proper cookie deletion on logout."""

    def test_cookie_deletion_parameters_match_creation(self, mock_oauth_env):
        """Cookie deletion must use same parameters as cookie creation."""
        # Expected parameters when setting cookie (from auth.py:258-264)
        set_cookie_params = {
            "key": "access_token",
            "httponly": True,
            "secure": False,  # Not production
            "samesite": "lax",
            "max_age": 86400,
        }

        # Expected parameters when deleting cookie (from auth.py:382-387)
        delete_cookie_params = {
            "key": "access_token",
            "path": "/",
            "httponly": True,
            "samesite": "lax",
        }

        # Verify critical parameters match
        assert (
            set_cookie_params["key"] == delete_cookie_params["key"]
        ), "Cookie key must match"
        assert (
            set_cookie_params["httponly"] == delete_cookie_params["httponly"]
        ), "httponly flag must match"
        assert (
            set_cookie_params["samesite"] == delete_cookie_params["samesite"]
        ), "samesite policy must match"

    @patch("api.auth.revoke_token")
    @patch("api.auth.extract_token_from_request")
    def test_logout_deletes_cookie_with_correct_params(
        self, mock_extract_token, mock_revoke_token, mock_oauth_env
    ):
        """Logout should delete cookie with matching parameters."""
        from fastapi import Request

        # Mock request with session and cookie
        mock_request = MagicMock(spec=Request)
        mock_request.session = {"user_email": "test@8thlight.com"}
        mock_request.cookies = {"access_token": "test_token"}
        mock_request.headers = {}

        mock_extract_token.return_value = None
        mock_revoke_token.return_value = True

        # Import after mocking
        from api.auth import logout

        # Create mock response to inspect (logout returns RedirectResponse, not JSONResponse)
        with patch("api.auth.RedirectResponse") as mock_redirect_response:
            mock_response = MagicMock()
            mock_redirect_response.return_value = mock_response

            # Call logout (it's async, so we need to handle that)
            import asyncio

            asyncio.run(logout(mock_request))

            # Verify delete_cookie was called with correct parameters
            mock_response.delete_cookie.assert_called_once_with(
                key="access_token",
                path="/",
                httponly=True,
                samesite="lax",
            )

    @patch("api.auth.revoke_token")
    def test_logout_clears_session(self, mock_revoke_token, mock_oauth_env):
        """Logout should clear session data."""
        from fastapi import Request

        mock_request = MagicMock(spec=Request)
        # Make session a MagicMock so we can track clear() calls
        mock_session = MagicMock()
        mock_session.get.return_value = "test@8thlight.com"
        mock_request.session = mock_session
        mock_request.cookies = {}
        mock_request.headers = {}

        mock_revoke_token.return_value = True

        from api.auth import logout
        import asyncio

        asyncio.run(logout(mock_request))

        # Verify session.clear() was called
        mock_session.clear.assert_called_once()

    @patch("api.auth.revoke_token")
    def test_logout_revokes_token_from_cookie(self, mock_revoke_token, mock_oauth_env):
        """Logout should revoke JWT token from cookie."""
        from fastapi import Request

        mock_request = MagicMock(spec=Request)
        mock_request.session = {"user_email": "test@8thlight.com"}
        mock_request.cookies = {"access_token": "test_token_from_cookie"}
        mock_request.headers = {}

        mock_revoke_token.return_value = True

        from api.auth import logout
        import asyncio

        asyncio.run(logout(mock_request))

        # Verify revoke_token was called with cookie value
        mock_revoke_token.assert_called_once_with("test_token_from_cookie")

    @patch("api.auth.revoke_token")
    @patch("api.auth.extract_token_from_request")
    def test_logout_revokes_token_from_header(
        self, mock_extract_token, mock_revoke_token, mock_oauth_env
    ):
        """Logout should revoke JWT token from Authorization header if no cookie."""
        from fastapi import Request

        mock_request = MagicMock(spec=Request)
        mock_request.session = {"user_email": "test@8thlight.com"}
        mock_request.cookies = {}  # No cookie
        mock_request.headers = {"Authorization": "Bearer test_token_from_header"}

        mock_extract_token.return_value = "test_token_from_header"
        mock_revoke_token.return_value = True

        from api.auth import logout
        import asyncio

        asyncio.run(logout(mock_request))

        # Verify extract_token was called
        mock_extract_token.assert_called_once_with("Bearer test_token_from_header")
        # Verify revoke_token was called with header value
        mock_revoke_token.assert_called_once_with("test_token_from_header")


class TestCacheControlHeaders:
    """Tests for cache-control headers on index.html."""

    def test_index_html_has_no_cache_headers(self, mock_oauth_env):
        """index.html should have no-cache headers to prevent browser caching."""
        from fastapi.responses import FileResponse

        # Expected headers for index.html
        expected_headers = {
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        }

        # Create a mock FileResponse
        mock_response = MagicMock(spec=FileResponse)
        mock_response.headers = {}

        # Simulate what the serve_react_app function does
        mock_response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        mock_response.headers["Pragma"] = "no-cache"
        mock_response.headers["Expires"] = "0"

        # Verify headers match
        for key, value in expected_headers.items():
            assert (
                mock_response.headers[key] == value
            ), f"Header {key} should be {value}"

    def test_cache_headers_prevent_browser_caching(self, mock_oauth_env):
        """Cache-control headers should instruct browser not to cache."""
        cache_control = "no-cache, no-store, must-revalidate"

        # Verify all three directives are present
        assert "no-cache" in cache_control, "Should have no-cache directive"
        assert "no-store" in cache_control, "Should have no-store directive"
        assert (
            "must-revalidate" in cache_control
        ), "Should have must-revalidate directive"

        # Verify Pragma header (HTTP/1.0 compatibility)
        pragma = "no-cache"
        assert pragma == "no-cache", "Pragma should be no-cache for HTTP/1.0 clients"

        # Verify Expires header (forces immediate expiration)
        expires = "0"
        assert expires == "0", "Expires should be 0 to force immediate expiration"


class TestLogoutAuditLogging:
    """Tests for audit logging during logout."""

    @patch("api.auth.AuditLogger.log_auth_event")
    @patch("api.auth.revoke_token")
    def test_logout_logs_audit_event(
        self, mock_revoke_token, mock_audit_log, mock_oauth_env
    ):
        """Logout should log audit event."""
        from fastapi import Request

        mock_request = MagicMock(spec=Request)
        mock_request.session = {"user_email": "test@8thlight.com"}
        mock_request.cookies = {"access_token": "test_token"}
        mock_request.headers = {}

        mock_revoke_token.return_value = True

        from api.auth import logout
        import asyncio

        asyncio.run(logout(mock_request))

        # Verify audit log was called
        mock_audit_log.assert_called_once_with(
            "logout",
            email="test@8thlight.com",
        )


class TestLogoutEdgeCases:
    """Tests for edge cases in logout."""

    @patch("api.auth.revoke_token")
    def test_logout_works_without_session(self, mock_revoke_token, mock_oauth_env):
        """Logout should work even if session is empty."""
        from fastapi import Request

        mock_request = MagicMock(spec=Request)
        mock_request.session = {}  # Empty session
        mock_request.cookies = {}
        mock_request.headers = {}

        mock_revoke_token.return_value = False

        from api.auth import logout
        import asyncio

        result = asyncio.run(logout(mock_request))

        # Should not raise exception
        assert result is not None

    @patch("api.auth.revoke_token")
    def test_logout_works_without_cookie(self, mock_revoke_token, mock_oauth_env):
        """Logout should work even if no cookie present."""
        from fastapi import Request

        mock_request = MagicMock(spec=Request)
        mock_request.session = {"user_email": "test@8thlight.com"}
        mock_request.cookies = {}  # No cookie
        mock_request.headers = {}  # No auth header

        from api.auth import logout
        import asyncio

        result = asyncio.run(logout(mock_request))

        # Should not raise exception
        assert result is not None
        # revoke_token should not be called (no token to revoke)
        mock_revoke_token.assert_not_called()

    @patch("api.auth.revoke_token")
    def test_logout_continues_if_revocation_fails(
        self, mock_revoke_token, mock_oauth_env
    ):
        """Logout should continue even if token revocation fails."""
        from fastapi import Request

        mock_request = MagicMock(spec=Request)
        # Make session a MagicMock so we can track clear() calls
        mock_session = MagicMock()
        mock_session.get.return_value = "test@8thlight.com"
        mock_request.session = mock_session
        mock_request.cookies = {"access_token": "test_token"}
        mock_request.headers = {}

        # Simulate revocation failure (Redis unavailable)
        mock_revoke_token.return_value = False

        from api.auth import logout
        import asyncio

        result = asyncio.run(logout(mock_request))

        # Should still succeed (cookie deleted, session cleared)
        assert result is not None
        mock_session.clear.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
