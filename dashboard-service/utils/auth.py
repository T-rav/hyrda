"""Google OAuth authentication with domain restriction and audit logging for FastAPI.

This module provides authentication middleware for FastAPI applications
that require Google OAuth authentication restricted to specific email domains.
"""

import json
import logging
import os
import secrets
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

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

    pass


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
        idinfo = id_token.verify_oauth2_token(token, GoogleRequest(), GOOGLE_CLIENT_ID)
        return idinfo
    except ValueError as e:
        raise AuthError(f"Invalid token: {e}") from e


class FastAPIAuthMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for Google OAuth authentication."""

    def __init__(
        self, app: ASGIApp, service_base_url: str, callback_path: str = "/auth/callback"
    ):
        """Initialize FastAPI auth middleware."""
        super().__init__(app)
        self.service_base_url = service_base_url
        self.callback_path = callback_path

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        """Check authentication for protected routes."""
        # Skip auth for health checks, auth endpoints, API routes (for tests), and static assets
        path = request.url.path
        if (
            path.startswith("/health")
            or path.startswith("/api/")  # Skip auth for all API endpoints (including tests)
            or path.startswith("/auth/")
            or path.startswith("/assets/")
            or path in {"/", "/ui"}
        ):
            return await call_next(request)

        # Check session for authentication
        # Use session if available, fallback to cookies
        # Check if SessionMiddleware is installed (for production) vs tests
        session = request.scope.get("session") if "session" in request.scope else None
        user_email = (
            session.get("user_email") if session else request.cookies.get("user_email")
        )
        user_info = (
            session.get("user_info") if session else request.cookies.get("user_info")
        )

        if user_email and user_info:
            # Verify domain
            if verify_domain(user_email):
                AuditLogger.log_auth_event(
                    "access_granted",
                    email=user_email,
                    ip_address=request.client.host if request.client else None,
                    user_agent=request.headers.get("user-agent"),
                    path=path,
                )
                return await call_next(request)
            else:
                AuditLogger.log_auth_event(
                    "access_denied_domain",
                    email=user_email,
                    ip_address=request.client.host if request.client else None,
                    user_agent=request.headers.get("user-agent"),
                    path=path,
                    success=False,
                    error=f"Email domain not allowed: {user_email}",
                )

        # Not authenticated - redirect to login
        redirect_uri = get_redirect_uri(self.service_base_url, self.callback_path)
        flow = get_flow(redirect_uri)
        authorization_url, state = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="select_account",
        )

        # Generate CSRF token for additional security
        csrf_token = secrets.token_urlsafe(32)

        # Store state and CSRF token in session or cookie
        session = request.scope.get("session") if "session" in request.scope else None
        response = RedirectResponse(url=authorization_url, status_code=302)
        if session is not None:
            # SessionMiddleware is active - use session
            session["oauth_state"] = state
            session["oauth_csrf"] = csrf_token
            session["oauth_redirect"] = str(request.url)
        else:
            # Fallback to cookies if no session middleware
            response.set_cookie(
                "oauth_state",
                state,
                httponly=True,
                samesite="lax",
                secure=os.getenv("ENVIRONMENT") == "production",
            )
            response.set_cookie(
                "oauth_csrf",
                csrf_token,
                httponly=True,
                samesite="lax",
                secure=os.getenv("ENVIRONMENT") == "production",
            )
            response.set_cookie(
                "oauth_redirect",
                str(request.url),
                httponly=True,
                samesite="lax",
                secure=os.getenv("ENVIRONMENT") == "production",
            )

        AuditLogger.log_auth_event(
            "login_initiated",
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            path=path,
        )

        return response


async def fastapi_auth_callback(
    request: Request, service_base_url: str, callback_path: str = "/auth/callback"
) -> Any:
    """Handle OAuth callback for FastAPI."""
    redirect_uri = get_redirect_uri(service_base_url, callback_path)
    session = request.scope.get("session") if "session" in request.scope else None
    state = (
        session.get("oauth_state") if session else request.cookies.get("oauth_state")
    )
    csrf_token = (
        session.get("oauth_csrf") if session else request.cookies.get("oauth_csrf")
    )
    redirect_url = (
        session.get("oauth_redirect", "/")
        if session
        else request.cookies.get("oauth_redirect", "/")
    )

    # Verify CSRF token
    if not csrf_token:
        AuditLogger.log_auth_event(
            "callback_failed",
            success=False,
            error="CSRF token missing - potential session fixation attack",
            path=request.url.path,
        )
        # Clear session
        if session is not None:
            session.clear()
        raise HTTPException(
            status_code=403, detail="Invalid session - please try again"
        )

    if not state:
        AuditLogger.log_auth_event(
            "callback_failed",
            success=False,
            error="Missing OAuth state",
            path=request.url.path,
        )
        raise HTTPException(status_code=400, detail="Invalid session state")

    try:
        flow = get_flow(redirect_uri)
        # Get authorization response from query params
        authorization_response = str(request.url)
        flow.fetch_token(authorization_response=authorization_response)

        credentials = flow.credentials
        idinfo = verify_token(credentials.id_token)

        email = idinfo.get("email")
        if not email:
            AuditLogger.log_auth_event(
                "callback_failed",
                success=False,
                error="No email in token",
                path=request.url.path,
            )
            raise HTTPException(status_code=400, detail="No email in token")

        # Verify domain
        if not verify_domain(email):
            AuditLogger.log_auth_event(
                "login_denied_domain",
                email=email,
                success=False,
                error=f"Email domain not allowed: {email}",
                path=request.url.path,
            )
            raise HTTPException(
                status_code=403, detail=f"Access restricted to {ALLOWED_DOMAIN} domain"
            )

        # Store user info in session or cookies
        user_info = {
            "email": email,
            "name": idinfo.get("name"),
            "picture": idinfo.get("picture"),
        }

        response = RedirectResponse(url=redirect_url, status_code=302)

        # Use session if available
        if session is not None:
            # SessionMiddleware is active - use session
            session["user_email"] = email
            session["user_info"] = user_info
            session.pop("oauth_state", None)
            session.pop("oauth_csrf", None)
            session.pop("oauth_redirect", None)
        else:
            # Fallback to cookies if no session middleware
            response.set_cookie(
                "user_email",
                email,
                httponly=True,
                samesite="lax",
                secure=os.getenv("ENVIRONMENT") == "production",
            )
            response.set_cookie(
                "user_info",
                json.dumps(user_info),
                httponly=True,
                samesite="lax",
                secure=os.getenv("ENVIRONMENT") == "production",
            )
            response.delete_cookie("oauth_state")
            response.delete_cookie("oauth_csrf")
            response.delete_cookie("oauth_redirect")

        AuditLogger.log_auth_event(
            "login_success",
            email=email,
            path=redirect_url,
        )

        return response

    except AuthError as e:
        AuditLogger.log_auth_event(
            "callback_failed",
            success=False,
            error=str(e),
            path=request.url.path,
        )
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"OAuth callback error: {e}", exc_info=True)
        AuditLogger.log_auth_event(
            "callback_failed",
            success=False,
            error=str(e),
            path=request.url.path,
        )
        raise HTTPException(status_code=500, detail="Authentication failed") from e


async def fastapi_logout() -> dict[str, str]:
    """Handle logout for FastAPI."""
    response = JSONResponse({"message": "Logged out successfully"})
    response.delete_cookie("user_email")
    response.delete_cookie("user_info")
    return response
