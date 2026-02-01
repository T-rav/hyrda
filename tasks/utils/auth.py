"""Google OAuth authentication with domain restriction and audit logging.

FastAPI-only version - all Flask code removed.
"""

import logging
import os
from datetime import UTC, datetime
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow

logger = logging.getLogger(__name__)

# OAuth configuration
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")
ALLOWED_DOMAIN = os.getenv("ALLOWED_EMAIL_DOMAIN", "@8thlight.com").lstrip("@")
OAUTH_SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]


class AuthError(Exception):
    """Authentication error."""

    ...


class AuditLogger:
    """Audit logging for authentication events."""

    @staticmethod
    def log_auth_event(
        event_type: str,
        email: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        success: bool = True,
        error: str | None = None,
        path: str | None = None,
    ) -> None:
        """Log authentication event for auditing."""
        log_data = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event_type": event_type,
            "success": success,
            "email": email,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "path": path,
        }
        if error:
            log_data["error"] = error

        if success:
            logger.info(f"AUTH_AUDIT: {event_type}", extra=log_data)
        else:
            logger.warning(f"AUTH_AUDIT: {event_type} FAILED", extra=log_data)


def get_redirect_uri(
    service_base_url: str, callback_path: str = "/auth/callback"
) -> str:
    """Get OAuth redirect URI for a service."""
    return f"{service_base_url.rstrip('/')}{callback_path}"


def verify_domain(email: str) -> bool:
    """Verify that email belongs to allowed domain."""
    if not email:
        return False
    return email.endswith(f"@{ALLOWED_DOMAIN}")


def get_flow(redirect_uri: str) -> Flow:
    """Create OAuth flow."""
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise AuthError(
            "Google OAuth not configured. Set GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET"
        )

    return Flow.from_client_config(
        {
            "web": {
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=OAUTH_SCOPES,
        redirect_uri=redirect_uri,
    )


def verify_token(token: str) -> dict[str, Any]:
    """Verify Google ID token and return user info."""
    try:
        idinfo = id_token.verify_oauth2_token(token, Request(), GOOGLE_CLIENT_ID)
        return idinfo
    except ValueError as e:
        raise AuthError(f"Invalid token: {e}") from e
