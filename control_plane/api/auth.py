"""Authentication endpoints for OAuth flow."""

import logging
import os

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from utils.auth import (
    AuditLogger,
    get_flow,
    get_redirect_uri,
    verify_domain,
    verify_token,
)
from utils.rate_limit import rate_limit

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/auth")


@router.get("/callback")
@rate_limit(max_requests=10, window_seconds=60)
async def auth_callback(request: Request):
    """Handle OAuth callback.

    Rate limited to prevent brute force attacks on OAuth flow.
    """
    service_base_url = os.getenv("CONTROL_PLANE_BASE_URL", "http://localhost:6001")
    redirect_uri = get_redirect_uri(service_base_url, "/auth/callback")

    # Get state from session
    state = request.session.get("oauth_state")
    csrf_token = request.session.get("oauth_csrf")
    redirect_url = request.session.get("oauth_redirect", "/")

    if not state:
        AuditLogger.log_auth_event(
            "callback_failed",
            success=False,
            error="Missing OAuth state - possible session timeout",
        )
        raise HTTPException(status_code=400, detail="Invalid session state")

    if not csrf_token:
        AuditLogger.log_auth_event(
            "callback_failed",
            success=False,
            error="CSRF token missing - potential session fixation attack",
        )
        request.session.clear()
        raise HTTPException(
            status_code=403, detail="Invalid session - please try again"
        )

    try:
        # Create OAuth flow
        flow = get_flow(redirect_uri)
        flow.fetch_token(authorization_response=str(request.url))

        # Get credentials and verify
        credentials = flow.credentials
        idinfo = verify_token(credentials.id_token)
        email = idinfo.get("email")

        # Verify domain
        if not verify_domain(email):
            AuditLogger.log_auth_event(
                "callback_failed",
                email=email,
                success=False,
                error=f"Email domain not allowed: {email}",
            )
            raise HTTPException(status_code=403, detail="Access restricted")

        # Store user info in session
        request.session["user_email"] = email
        request.session["user_info"] = {
            "email": email,
            "name": idinfo.get("name"),
            "picture": idinfo.get("picture"),
        }

        # Clear OAuth state
        request.session.pop("oauth_state", None)
        request.session.pop("oauth_csrf", None)
        request.session.pop("oauth_redirect", None)

        AuditLogger.log_auth_event(
            "login_success",
            email=email,
        )

        return RedirectResponse(url=redirect_url, status_code=302)

    except Exception as e:
        logger.error(f"OAuth callback error: {e}", exc_info=True)
        AuditLogger.log_auth_event(
            "callback_failed",
            success=False,
            error=str(e),
        )
        raise HTTPException(status_code=500, detail="Authentication failed")


@router.post("/logout")
async def logout(request: Request):
    """Handle logout."""
    email = request.session.get("user_email")

    # Clear session
    request.session.clear()

    AuditLogger.log_auth_event(
        "logout",
        email=email,
    )

    return {"message": "Logged out successfully"}
