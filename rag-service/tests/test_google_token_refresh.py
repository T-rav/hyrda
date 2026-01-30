"""Tests for Google OAuth token refresh functionality."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from utils.google_token_refresh import (
    GoogleTokenRefresher,
    TokenRefreshResult,
    get_token_refresher,
)


class TestGoogleTokenRefresher:
    """Test suite for GoogleTokenRefresher."""

    @pytest.fixture
    def refresher(self):
        """Create a token refresher with test credentials."""
        return GoogleTokenRefresher(
            client_id="test-client-id",
            client_secret="test-client-secret",
        )

    @pytest.mark.asyncio
    async def test_refresh_token_success(self, refresher):
        """Test successful token refresh."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(
            return_value={
                "access_token": "ya29.new-access-token",
                "expires_in": 3600,
                "token_type": "Bearer",
            }
        )

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result: TokenRefreshResult = await refresher.refresh_token("test-refresh-token")

            assert result["success"] is True
            assert result["access_token"] == "ya29.new-access-token"
            assert result["refresh_token"] == "test-refresh-token"  # Same refresh token returned
            assert result["error"] is None
            assert result["expires_at"] is not None

            # Verify the call to Google
            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args
            assert call_args[0][0] == "https://oauth2.googleapis.com/token"

    @pytest.mark.asyncio
    async def test_refresh_token_with_new_refresh_token(self, refresher):
        """Test token refresh when Google provides a new refresh token."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(
            return_value={
                "access_token": "ya29.new-access-token",
                "refresh_token": "1//04new-refresh-token",  # New refresh token
                "expires_in": 3600,
                "token_type": "Bearer",
            }
        )

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result: TokenRefreshResult = await refresher.refresh_token("old-refresh-token")

            assert result["success"] is True
            assert result["access_token"] == "ya29.new-access-token"
            assert result["refresh_token"] == "1//04new-refresh-token"  # New token

    @pytest.mark.asyncio
    async def test_refresh_token_invalid_credentials(self, refresher):
        """Test token refresh with invalid client credentials."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.json = MagicMock(
            return_value={
                "error": "invalid_client",
                "error_description": "The OAuth client was not found.",
            }
        )

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result: TokenRefreshResult = await refresher.refresh_token("test-refresh-token")

            assert result["success"] is False
            assert result["access_token"] is None
            assert "OAuth client was not found" in result["error"]

    @pytest.mark.asyncio
    async def test_refresh_token_invalid_grant(self, refresher):
        """Test token refresh with invalid/expired refresh token."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json = MagicMock(
            return_value={
                "error": "invalid_grant",
                "error_description": "Token has been expired or revoked.",
            }
        )

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result: TokenRefreshResult = await refresher.refresh_token("expired-refresh-token")

            assert result["success"] is False
            assert "expired or revoked" in result["error"]

    @pytest.mark.asyncio
    async def test_refresh_token_timeout(self, refresher):
        """Test token refresh timeout handling."""
        import httpx

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("Connection timed out"))
            mock_client_class.return_value = mock_client

            result: TokenRefreshResult = await refresher.refresh_token("test-refresh-token")

            assert result["success"] is False
            assert "timed out" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_refresh_token_no_credentials(self):
        """Test token refresh when credentials are not configured."""
        refresher_no_creds = GoogleTokenRefresher(client_id=None, client_secret=None)

        result: TokenRefreshResult = await refresher_no_creds.refresh_token("test-refresh-token")

        assert result["success"] is False
        assert "not configured" in result["error"]

    @pytest.mark.asyncio
    async def test_refresh_token_empty_refresh_token(self, refresher):
        """Test token refresh with empty refresh token."""
        result: TokenRefreshResult = await refresher.refresh_token("")

        assert result["success"] is False
        assert "No refresh token provided" in result["error"]

    def test_is_token_expired_with_datetime(self):
        """Test token expiry check with datetime object."""
        refresher = GoogleTokenRefresher()

        # Token expired 10 minutes ago
        expired_time = datetime.now(UTC) - timedelta(minutes=10)
        assert refresher.is_token_expired(expired_time) is True

        # Token expires in 3 minutes (within 5-minute buffer) → should be expired
        almost_expired = datetime.now(UTC) + timedelta(minutes=3)
        assert refresher.is_token_expired(almost_expired) is True

        # Token expires in 10 minutes (beyond 5-minute buffer) → should NOT be expired
        fresh = datetime.now(UTC) + timedelta(minutes=10)
        assert refresher.is_token_expired(fresh) is False

        # Token expires in 30 minutes (well beyond buffer) → should NOT be expired
        very_fresh = datetime.now(UTC) + timedelta(minutes=30)
        assert refresher.is_token_expired(very_fresh) is False

    def test_is_token_expired_with_string(self):
        """Test token expiry check with ISO string."""
        refresher = GoogleTokenRefresher()

        # Token expired 10 minutes ago
        expired_str = (datetime.now(UTC) - timedelta(minutes=10)).isoformat()
        assert refresher.is_token_expired(expired_str) is True

        # Token expires in 30 minutes
        fresh_str = (datetime.now(UTC) + timedelta(minutes=30)).isoformat()
        assert refresher.is_token_expired(fresh_str) is False

    def test_is_token_expired_with_none(self):
        """Test token expiry check with None."""
        refresher = GoogleTokenRefresher()

        # None should be considered expired (to trigger refresh)
        assert refresher.is_token_expired(None) is True

    def test_is_token_expired_with_invalid_string(self):
        """Test token expiry check with invalid string."""
        refresher = GoogleTokenRefresher()

        # Invalid string should be considered expired
        assert refresher.is_token_expired("not-a-date") is True


class TestGetTokenRefresher:
    """Test suite for get_token_refresher factory function."""

    def test_singleton_pattern(self):
        """Test that get_token_refresher returns the same instance."""
        # Reset global instance first
        import utils.google_token_refresh as refresh_module

        refresh_module._token_refresher = None

        # Get two instances
        refresher1 = get_token_refresher()
        refresher2 = get_token_refresher()

        # Should be the same object
        assert refresher1 is refresher2

    def test_uses_env_vars(self):
        """Test that refresher reads credentials from environment."""
        with patch.dict(
            "os.environ",
            {"GOOGLE_CLIENT_ID": "env-client-id", "GOOGLE_CLIENT_SECRET": "env-client-secret"},
        ):
            refresher = GoogleTokenRefresher()
            assert refresher.client_id == "env-client-id"
            assert refresher.client_secret == "env-client-secret"


class TestTokenRefreshResult:
    """Test TokenRefreshResult typed dict structure."""

    def test_result_structure(self):
        """Test that TokenRefreshResult has expected fields."""
        result: TokenRefreshResult = {
            "success": True,
            "access_token": "test-token",
            "refresh_token": "test-refresh",
            "expires_at": datetime.now(UTC),
            "error": None,
        }

        assert result["success"] is True
        assert result["access_token"] == "test-token"
        assert result["refresh_token"] == "test-refresh"
        assert result["expires_at"] is not None
        assert result["error"] is None
