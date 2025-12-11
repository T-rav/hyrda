"""Google OAuth authentication with domain restriction and audit logging.

This module provides authentication utilities for FastAPI applications
that require Google OAuth authentication restricted to specific email domains.
"""

import logging
import os
from datetime import UTC, datetime
from functools import wraps
from typing import Any, Callable, Optional

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


def validate_oauth_config() -> None:
    """Validate required OAuth environment variables at startup.

    Raises:
        ValueError: If required OAuth configuration is missing in production
    """
    environment = os.getenv("ENVIRONMENT", "development")

    # In production, require all OAuth settings to be explicitly configured
    if environment == "production":
        if not GOOGLE_CLIENT_ID:
            raise ValueError(
                "GOOGLE_OAUTH_CLIENT_ID is required in production but not set"
            )
        if not GOOGLE_CLIENT_SECRET:
            raise ValueError(
                "GOOGLE_OAUTH_CLIENT_SECRET is required in production but not set"
            )
        if not os.getenv("ALLOWED_EMAIL_DOMAIN"):
            logger.warning(
                "ALLOWED_EMAIL_DOMAIN not set in production - using default: @8thlight.com"
            )

        logger.info("OAuth configuration validated for production")
    else:
        # In non-production, just log warnings for missing values
        if not GOOGLE_CLIENT_ID:
            logger.warning("GOOGLE_OAUTH_CLIENT_ID not set (optional in development)")
        if not GOOGLE_CLIENT_SECRET:
            logger.warning("GOOGLE_OAUTH_CLIENT_SECRET not set (optional in development)")


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
    # Allow all domains if wildcard is configured
    if ALLOWED_DOMAIN == "*":
        return True
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


# FastAPI-specific authentication middleware


class FastAPIAuthMiddleware:
    """FastAPI middleware for Google OAuth authentication."""

    def __init__(
        self, app: Any, service_base_url: str, callback_path: str = "/auth/callback"
    ):
        """Initialize FastAPI auth middleware."""
        self.app = app
        self.service_base_url = service_base_url
        self.callback_path = callback_path
        self.login_path = "/auth/login"
        self.logout_path = "/auth/logout"
        self._setup_routes()

    def _setup_routes(self) -> None:
        """Setup auth routes."""
        import secrets

        from fastapi import Request as FastAPIRequest
        from fastapi.responses import JSONResponse, RedirectResponse

        @self.app.get(self.login_path)
        async def auth_login(request: FastAPIRequest) -> RedirectResponse:
            """Initiate OAuth login."""
            redirect_uri = get_redirect_uri(self.service_base_url, self.callback_path)
            flow = get_flow(redirect_uri)
            authorization_url, state = flow.authorization_url(
                access_type="offline",
                prompt="select_account",
            )

            # Generate CSRF token for additional security
            csrf_token = secrets.token_urlsafe(32)
            request.session["oauth_state"] = state
            request.session["oauth_csrf"] = csrf_token
            request.session["oauth_redirect"] = str(
                request.query_params.get("redirect", "/")
            )

            AuditLogger.log_auth_event(
                "login_initiated",
                path=str(request.url.path),
            )

            return RedirectResponse(url=authorization_url)

        @self.app.get(self.callback_path)
        async def auth_callback(
            request: FastAPIRequest,
        ) -> RedirectResponse | JSONResponse:
            """Handle OAuth callback."""
            redirect_uri = get_redirect_uri(self.service_base_url, self.callback_path)
            state = request.session.get("oauth_state")
            csrf_token = request.session.get("oauth_csrf")

            # Verify CSRF token
            if not csrf_token:
                AuditLogger.log_auth_event(
                    "callback_failed",
                    success=False,
                    error="CSRF token missing - potential session fixation attack",
                )
                request.session.clear()
                return JSONResponse(
                    status_code=403,
                    content={"error": "Invalid session - please try again"},
                )

            if not state:
                AuditLogger.log_auth_event(
                    "callback_failed",
                    success=False,
                    error="Missing OAuth state",
                )
                return JSONResponse(
                    status_code=400,
                    content={"error": "Invalid session state"},
                )

            try:
                flow = get_flow(redirect_uri)
                flow.fetch_token(authorization_response=str(request.url))

                credentials = flow.credentials
                idinfo = verify_token(credentials.id_token)

                email = idinfo.get("email")
                if not email:
                    AuditLogger.log_auth_event(
                        "callback_failed",
                        success=False,
                        error="No email in token",
                    )
                    return JSONResponse(
                        status_code=400,
                        content={"error": "No email in token"},
                    )

                # Verify domain
                if not verify_domain(email):
                    AuditLogger.log_auth_event(
                        "login_denied_domain",
                        email=email,
                        success=False,
                        error=f"Email domain not allowed: {email}",
                    )
                    request.session.clear()
                    return JSONResponse(
                        status_code=403,
                        content={
                            "error": f"Access restricted to {ALLOWED_DOMAIN} domain"
                        },
                    )

                # Regenerate session to prevent session fixation attacks
                saved_redirect = request.session.get("oauth_redirect", "/")
                request.session.clear()

                # Store user info in new session
                request.session["user_email"] = email
                request.session["user_info"] = {
                    "email": email,
                    "name": idinfo.get("name"),
                    "picture": idinfo.get("picture"),
                }

                AuditLogger.log_auth_event(
                    "login_success",
                    email=email,
                    path=saved_redirect,
                )

                return RedirectResponse(url=saved_redirect)

            except AuthError as e:
                AuditLogger.log_auth_event(
                    "callback_failed",
                    success=False,
                    error=str(e),
                )
                return JSONResponse(
                    status_code=400,
                    content={"error": str(e)},
                )
            except Exception as e:
                logger.error(f"OAuth callback error: {e}", exc_info=True)
                AuditLogger.log_auth_event(
                    "callback_failed",
                    success=False,
                    error=str(e),
                )
                return JSONResponse(
                    status_code=500,
                    content={"error": "Authentication failed"},
                )

        @self.app.post(self.logout_path)
        async def auth_logout(request: FastAPIRequest) -> JSONResponse:
            """Handle logout."""
            email = request.session.get("user_email")
            request.session.clear()
            AuditLogger.log_auth_event(
                "logout",
                email=email,
            )
            return JSONResponse(content={"message": "Logged out successfully"})

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        """ASGI middleware to check authentication on requests."""
        from starlette.datastructures import URL
        from starlette.requests import Request
        from starlette.responses import RedirectResponse

        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        path = request.url.path

        # Skip auth for public endpoints
        public_paths = [
            self.callback_path,
            self.login_path,
            self.logout_path,
            "/health",
            "/ready",
        ]
        if path in public_paths or path.startswith("/static"):
            await self.app(scope, receive, send)
            return

        # Check if user is authenticated
        if "user_email" not in request.session:
            # Redirect to login with current URL as redirect param
            login_url = URL(self.login_path).include_query_params(
                redirect=str(request.url)
            )
            response = RedirectResponse(url=str(login_url), status_code=302)
            await response(scope, receive, send)
            return

        # Verify domain (in case session was tampered with)
        email = request.session.get("user_email")
        if not verify_domain(email):
            AuditLogger.log_auth_event(
                "access_denied_domain",
                email=email,
                path=path,
                success=False,
                error=f"Email domain not allowed: {email}",
            )
            request.session.clear()
            login_url = URL(self.login_path).include_query_params(
                redirect=str(request.url)
            )
            response = RedirectResponse(url=str(login_url), status_code=302)
            await response(scope, receive, send)
            return

        # User is authenticated, continue
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
            raise HTTPException(
                status_code=403, detail=f"Access restricted to {ALLOWED_DOMAIN} domain"
            )

        AuditLogger.log_auth_event(
            "access_granted",
            email=email,
            path=str(request.url.path),
        )

        return await func(request, *args, **kwargs)

    return wrapper
