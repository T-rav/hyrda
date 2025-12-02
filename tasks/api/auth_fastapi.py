"""Authentication endpoints for OAuth flow."""

import logging
import os

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth")


@router.get("/callback")
async def auth_callback(request: Request):
    """Handle OAuth callback.

    Returns:
        Redirect to original URL or error response
    """
    from utils.auth import AuditLogger, get_flow, get_redirect_uri, verify_token

    service_base_url = os.getenv("SERVER_BASE_URL", "http://localhost:5001")
    redirect_uri = get_redirect_uri(service_base_url, "/auth/callback")

    state = request.session.get("oauth_state")
    csrf_token = request.session.get("oauth_csrf")
    redirect_url = request.session.get("oauth_redirect", "/")

    # Verify CSRF token
    if not csrf_token:
        AuditLogger.log_auth_event(
            "callback_failed",
            success=False,
            error="CSRF token missing - potential session fixation attack",
        )
        request.session.clear()
        return JSONResponse(
            {"error": "Invalid session - please try again"}, status_code=403
        )

    if not state:
        AuditLogger.log_auth_event(
            "callback_failed",
            success=False,
            error="Missing OAuth state",
        )
        return JSONResponse({"error": "Invalid session state"}, status_code=400)

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
            )
            return JSONResponse({"error": "No email in token"}, status_code=400)

        # Verify domain
        from utils.auth import verify_domain

        if not verify_domain(email):
            AuditLogger.log_auth_event(
                "login_denied_domain",
                email=email,
                success=False,
                error=f"Email domain not allowed: {email}",
            )
            return JSONResponse(
                {"error": "Access restricted to allowed domain"}, status_code=403
            )

        # Store user info in session
        request.session["user_email"] = email
        request.session["user_info"] = {
            "email": email,
            "name": idinfo.get("name"),
            "picture": idinfo.get("picture"),
        }
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
        return JSONResponse({"error": "Authentication failed"}, status_code=500)


@router.post("/logout")
async def logout(request: Request):
    """Handle logout.

    Returns:
        Success message
    """
    from utils.auth import AuditLogger

    email = request.session.get("user_email")
    request.session.clear()

    AuditLogger.log_auth_event(
        "logout",
        email=email,
    )

    return {"message": "Logged out successfully"}
