"""Google OAuth token refresh utilities.

This module provides functionality to refresh expired Google OAuth tokens
using the refresh token. This allows the RAG service to maintain access
to Google APIs (Drive, Gmail) on behalf of users without requiring
re-authentication.
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import TypedDict

import httpx

logger = logging.getLogger(__name__)

# Google OAuth token endpoint
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"


class TokenRefreshResult(TypedDict):
    """Result of token refresh operation."""

    success: bool
    access_token: str | None
    refresh_token: str | None  # May be null if Google doesn't return new one
    expires_at: datetime | None
    error: str | None


class GoogleTokenRefresher:
    """Handles Google OAuth token refresh operations.

    When a user's Google OAuth access token expires (typically after 1 hour),
    this class uses the refresh token to obtain a new access token without
    requiring the user to re-authenticate.
    """

    def __init__(self, client_id: str | None = None, client_secret: str | None = None):
        """Initialize the token refresher.

        Args:
            client_id: Google OAuth client ID. If not provided, reads from env.
            client_secret: Google OAuth client secret. If not provided, reads from env.
        """
        import os

        self.client_id = client_id or os.getenv("GOOGLE_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("GOOGLE_CLIENT_SECRET")

    async def refresh_token(self, refresh_token: str) -> TokenRefreshResult:
        """Refresh an expired Google OAuth access token.

        Args:
            refresh_token: The refresh token obtained during initial OAuth flow.

        Returns:
            TokenRefreshResult with new access token or error details.

        Example:
            refresher = GoogleTokenRefresher()
            result = await refresher.refresh_token("1//04xxx...")
            if result["success"]:
                new_access_token = result["access_token"]
                expires_at = result["expires_at"]
        """
        if not self.client_id or not self.client_secret:
            return {
                "success": False,
                "access_token": None,
                "refresh_token": None,
                "expires_at": None,
                "error": "Google OAuth credentials not configured (GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET)",
            }

        if not refresh_token:
            return {
                "success": False,
                "access_token": None,
                "refresh_token": None,
                "expires_at": None,
                "error": "No refresh token provided",
            }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    GOOGLE_TOKEN_ENDPOINT,
                    data={
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "refresh_token": refresh_token,
                        "grant_type": "refresh_token",
                    },
                    timeout=10.0,
                )

                if response.status_code != 200:
                    error_data = response.json() if response.text else {}
                    error_desc = error_data.get("error_description", "Unknown error")
                    logger.warning(f"Token refresh failed: {error_desc}")
                    return {
                        "success": False,
                        "access_token": None,
                        "refresh_token": None,
                        "expires_at": None,
                        "error": f"Token refresh failed: {error_desc}",
                    }

                data = response.json()
                access_token = data.get("access_token")
                new_refresh_token = data.get("refresh_token")  # May be null
                expires_in = data.get("expires_in", 3600)  # Default 1 hour

                if not access_token:
                    return {
                        "success": False,
                        "access_token": None,
                        "refresh_token": None,
                        "expires_at": None,
                        "error": "No access token in refresh response",
                    }

                # Calculate expiry time
                expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)

                logger.info(f"Successfully refreshed Google OAuth token (expires in {expires_in}s)")

                return {
                    "success": True,
                    "access_token": access_token,
                    "refresh_token": new_refresh_token or refresh_token,  # Keep old if no new one
                    "expires_at": expires_at,
                    "error": None,
                }

        except httpx.TimeoutException:
            logger.error("Token refresh request timed out")
            return {
                "success": False,
                "access_token": None,
                "refresh_token": None,
                "expires_at": None,
                "error": "Token refresh request timed out",
            }
        except Exception as e:
            logger.error(f"Unexpected error during token refresh: {e}")
            return {
                "success": False,
                "access_token": None,
                "refresh_token": None,
                "expires_at": None,
                "error": f"Token refresh error: {str(e)}",
            }

    def is_token_expired(self, expires_at: datetime | str | None) -> bool:
        """Check if a token is expired or about to expire (within 5 minutes).

        Args:
            expires_at: Token expiry timestamp (datetime object or ISO string)

        Returns:
            True if token is expired or expires within 5 minutes
        """
        if not expires_at:
            # If we don't know expiry, assume it's expired to trigger refresh
            return True

        try:
            if isinstance(expires_at, str):
                expires_at = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))

            # Consider token expired if it expires within 5 minutes
            buffer = timedelta(minutes=5)
            return datetime.now(UTC) >= (expires_at - buffer)
        except Exception as e:
            logger.warning(f"Could not parse expiry date: {e}")
            return True  # Assume expired on parse error


# Global instance for convenience
_token_refresher: GoogleTokenRefresher | None = None


def get_token_refresher() -> GoogleTokenRefresher:
    """Get or create global GoogleTokenRefresher instance."""
    global _token_refresher
    if _token_refresher is None:
        _token_refresher = GoogleTokenRefresher()
    return _token_refresher
