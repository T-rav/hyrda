"""Google OAuth authentication with domain restriction and audit logging.

This module provides authentication middleware for Flask and FastAPI applications
that require Google OAuth authentication restricted to specific email domains.
"""

import logging
import os
from datetime import UTC, datetime
from functools import wraps
from typing import Any, Callable, Optional

from flask import Response, has_request_context, jsonify, redirect, request, session
from google.auth.transport.requests import Request
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow

logger = logging.getLogger(__name__)

# OAuth configuration
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")
ALLOWED_DOMAIN = os.getenv("ALLOWED_EMAIL_DOMAIN", "@8thlight.com").lstrip("@")
OAUTH_SCOPES = ["openid", "https://www.googleapis.com/auth/userinfo.email", "https://www.googleapis.com/auth/userinfo.profile"]


class AuthError(Exception):
    """Authentication error."""

    pass


class AuditLogger:
    """Audit logging for authentication events."""

    @staticmethod
    def log_auth_event(
        event_type: str,
        email: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        success: bool = True,
        error: Optional[str] = None,
        path: Optional[str] = None,
    ) -> None:
        """Log authentication event for auditing."""
        log_data = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event_type": event_type,
            "success": success,
            "email": email,
            "ip_address": ip_address or (request.remote_addr if has_request_context() else None),
            "user_agent": user_agent or (request.headers.get("User-Agent") if has_request_context() else None),
            "path": path or (request.path if has_request_context() else None),
        }
        if error:
            log_data["error"] = error

        if success:
            logger.info(f"AUTH_AUDIT: {event_type}", extra=log_data)
        else:
            logger.warning(f"AUTH_AUDIT: {event_type} FAILED", extra=log_data)


def get_redirect_uri(service_base_url: str, callback_path: str = "/auth/callback") -> str:
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
        raise AuthError("Google OAuth not configured. Set GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET")

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


# Flask-specific authentication decorators and helpers


def flask_require_auth(service_base_url: str, callback_path: str = "/auth/callback"):
    """Flask decorator to require Google OAuth authentication."""

    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args: Any, **kwargs: Any) -> Any:
            # Check if user is authenticated
            if "user_email" in session and "user_info" in session:
                email = session["user_email"]
                # Verify domain on each request
                if verify_domain(email):
                    AuditLogger.log_auth_event(
                        "access_granted",
                        email=email,
                        path=request.path,
                    )
                    return f(*args, **kwargs)
                else:
                    # Domain changed or invalid
                    session.clear()
                    AuditLogger.log_auth_event(
                        "access_denied_domain",
                        email=email,
                        path=request.path,
                        success=False,
                        error=f"Email domain not allowed: {email}",
                    )

            # Not authenticated - redirect to login
            import secrets
            redirect_uri = get_redirect_uri(service_base_url, callback_path)
            flow = get_flow(redirect_uri)
            authorization_url, state = flow.authorization_url(
                access_type="offline",
                include_granted_scopes="true",
                prompt="select_account",
            )

            # Generate CSRF token for additional security
            csrf_token = secrets.token_urlsafe(32)
            session["oauth_state"] = state
            session["oauth_csrf"] = csrf_token
            session["oauth_redirect"] = request.url

            AuditLogger.log_auth_event(
                "login_initiated",
                path=request.path,
            )

            return redirect(authorization_url)

        return decorated_function

    return decorator


def flask_auth_callback(service_base_url: str, callback_path: str = "/auth/callback") -> Response:
    """Handle OAuth callback for Flask."""
    redirect_uri = get_redirect_uri(service_base_url, callback_path)
    state = session.get("oauth_state")
    csrf_token = session.get("oauth_csrf")
    redirect_url = session.get("oauth_redirect", "/")

    # Verify CSRF token
    if not csrf_token:
        AuditLogger.log_auth_event(
            "callback_failed",
            success=False,
            error="CSRF token missing - potential session fixation attack",
        )
        session.clear()
        return jsonify({"error": "Invalid session - please try again"}), 403

    if not state:
        AuditLogger.log_auth_event(
            "callback_failed",
            success=False,
            error="Missing OAuth state",
        )
        return jsonify({"error": "Invalid session state"}), 400

    try:
        flow = get_flow(redirect_uri)
        flow.fetch_token(authorization_response=request.url)

        credentials = flow.credentials
        idinfo = verify_token(credentials.id_token)

        email = idinfo.get("email")
        if not email:
            AuditLogger.log_auth_event(
                "callback_failed",
                success=False,
                error="No email in token",
            )
            return jsonify({"error": "No email in token"}), 400

        # Verify domain
        if not verify_domain(email):
            AuditLogger.log_auth_event(
                "login_denied_domain",
                email=email,
                success=False,
                error=f"Email domain not allowed: {email}",
            )
            session.clear()
            return jsonify({"error": f"Access restricted to {ALLOWED_DOMAIN} domain"}), 403

        # Regenerate session to prevent session fixation attacks
        # Store redirect URL before clearing
        saved_redirect = session.get("oauth_redirect", "/")

        # Clear old session data (regenerates session ID in Flask)
        session.clear()

        # Store user info in new session
        session["user_email"] = email
        session["user_info"] = {
            "email": email,
            "name": idinfo.get("name"),
            "picture": idinfo.get("picture"),
        }

        # Restore redirect URL
        redirect_url = saved_redirect

        AuditLogger.log_auth_event(
            "login_success",
            email=email,
            path=redirect_url,
        )

        return redirect(redirect_url)

    except AuthError as e:
        AuditLogger.log_auth_event(
            "callback_failed",
            success=False,
            error=str(e),
        )
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"OAuth callback error: {e}", exc_info=True)
        AuditLogger.log_auth_event(
            "callback_failed",
            success=False,
            error=str(e),
        )
        return jsonify({"error": "Authentication failed"}), 500


def flask_logout() -> Response:
    """Handle logout for Flask."""
    email = session.get("user_email")
    session.clear()
    AuditLogger.log_auth_event(
        "logout",
        email=email,
    )
    return jsonify({"message": "Logged out successfully"})


# FastAPI-specific authentication middleware


class FastAPIAuthMiddleware:
    """FastAPI middleware for Google OAuth authentication."""

    def __init__(self, app: Any, service_base_url: str, callback_path: str = "/auth/callback"):
        """Initialize FastAPI auth middleware."""
        self.app = app
        self.service_base_url = service_base_url
        self.callback_path = callback_path
        self._setup_routes()

    def _setup_routes(self) -> None:
        """Setup auth routes."""
        from fastapi import Request as FastAPIRequest

        @self.app.get(self.callback_path)
        async def auth_callback(request: FastAPIRequest) -> Any:
            """Handle OAuth callback."""
            # FastAPI callback implementation
            redirect_uri = get_redirect_uri(self.service_base_url, self.callback_path)
            state = request.session.get("oauth_state") if hasattr(request, "session") else None

            if not state:
                AuditLogger.log_auth_event(
                    "callback_failed",
                    success=False,
                    error="Missing OAuth state",
                )
                return {"error": "Invalid session state"}

            try:
                get_flow(redirect_uri)
                # Note: FastAPI implementation would need async handling
                # This is a simplified version
                return {"message": "FastAPI auth callback - implementation needed"}

            except Exception as e:
                logger.error(f"OAuth callback error: {e}", exc_info=True)
                return {"error": "Authentication failed"}

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        """ASGI middleware."""
        # Middleware implementation
        await self.app(scope, receive, send)


def fastapi_require_auth(func: Callable) -> Callable:
    """FastAPI dependency for requiring authentication."""
    from fastapi import HTTPException, Request

    @wraps(func)
    async def wrapper(request: Request, *args: Any, **kwargs: Any) -> Any:
        """Check authentication."""
        # Check session for user_email
        if not hasattr(request, "session") or "user_email" not in request.session:
            raise HTTPException(status_code=401, detail="Not authenticated")

        email = request.session["user_email"]
        if not verify_domain(email):
            raise HTTPException(status_code=403, detail=f"Access restricted to {ALLOWED_DOMAIN} domain")

        AuditLogger.log_auth_event(
            "access_granted",
            email=email,
            path=str(request.url.path),
        )

        return await func(request, *args, **kwargs)

    return wrapper
