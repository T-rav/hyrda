"""Authentication endpoints for OAuth flow with JWT token generation."""

import logging
import os
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, JSONResponse
from utils.auth import (
    AuditLogger,
    get_flow,
    get_redirect_uri,
    verify_domain,
    verify_token,
)
from utils.rate_limit import rate_limit

# Import JWT utilities from shared directory
sys.path.insert(0, "/app")  # Add app root to path for shared imports
from shared.utils.jwt_auth import create_access_token

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

        # Generate JWT token
        user_name = idinfo.get("name")
        user_picture = idinfo.get("picture")
        jwt_token = create_access_token(
            user_email=email,
            user_name=user_name,
            user_picture=user_picture,
        )

        # Store user info in session (for backward compatibility)
        request.session["user_email"] = email
        request.session["user_info"] = {
            "email": email,
            "name": user_name,
            "picture": user_picture,
        }

        # Clear OAuth state
        request.session.pop("oauth_state", None)
        request.session.pop("oauth_csrf", None)
        request.session.pop("oauth_redirect", None)

        AuditLogger.log_auth_event(
            "login_success",
            email=email,
        )

        # Create response with JWT token as HTTP-only cookie
        response = RedirectResponse(url=redirect_url, status_code=302)
        response.set_cookie(
            key="access_token",
            value=jwt_token,
            httponly=True,  # Prevent XSS attacks
            secure=os.getenv("ENVIRONMENT") == "production",  # HTTPS only in prod
            samesite="lax",  # CSRF protection
            max_age=86400,  # 24 hours (matches JWT expiration)
        )

        return response

    except Exception as e:
        logger.error(f"OAuth callback error: {e}", exc_info=True)
        AuditLogger.log_auth_event(
            "callback_failed",
            success=False,
            error=str(e),
        )
        raise HTTPException(status_code=500, detail="Authentication failed")


@router.get("/token")
async def get_token(request: Request):
    """Get JWT token for current authenticated user.

    This endpoint allows users to get a JWT token for API access.
    Requires existing session (user must be logged in via OAuth).

    Returns:
        JSON with access_token that can be used in Authorization header

    Example:
        # After logging in via OAuth:
        curl http://localhost:6001/auth/token
        # Returns: {"access_token": "eyJ0eXAi...", "token_type": "bearer"}

        # Use token in subsequent requests:
        curl -H "Authorization: Bearer eyJ0eXAi..." http://localhost:5001/api/jobs
    """
    # Check if user is authenticated via session
    user_email = request.session.get("user_email")
    user_info = request.session.get("user_info")

    if not user_email or not user_info:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated - please login first at /auth/callback"
        )

    # Generate JWT token
    jwt_token = create_access_token(
        user_email=user_email,
        user_name=user_info.get("name"),
        user_picture=user_info.get("picture"),
    )

    logger.info(f"Generated JWT token for {user_email}")

    return {
        "access_token": jwt_token,
        "token_type": "bearer",
        "expires_in": 86400,  # 24 hours in seconds
    }


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

    # Create response and clear cookie
    response = JSONResponse({"message": "Logged out successfully"})
    response.delete_cookie("access_token")

    return response
