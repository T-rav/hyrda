"""Authentication dependencies for FastAPI dependency injection."""

import os
import sys
from pathlib import Path

from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse

# Import JWT utilities from shared directory
sys.path.insert(0, "/app")  # Add app root to path for shared imports
from shared.utils.jwt_auth import JWTAuthError, extract_token_from_request, verify_token
from utils.auth import verify_domain

# Control plane base URL for redirects
CONTROL_PLANE_URL = os.getenv("CONTROL_PLANE_BASE_URL", "http://localhost:6001")


async def get_current_user(request: Request) -> dict:
    """
    Dependency to get the current authenticated user.

    Supports both JWT tokens (preferred) and session-based auth (fallback).
    Use with: Depends(get_current_user)

    Returns:
        dict: User info with email and name

    Raises:
        HTTPException: 401 if not authenticated or invalid domain
    """
    # Try JWT token first (from Authorization header or cookie)
    auth_header = request.headers.get("Authorization")
    token = extract_token_from_request(auth_header)

    # Fallback to cookie if no Authorization header
    if not token:
        token = request.cookies.get("access_token")

    if token:
        try:
            payload = verify_token(token)
            user_email = payload.get("email")
            user_info = {
                "email": user_email,
                "name": payload.get("name"),
                "picture": payload.get("picture"),
            }

            # Verify domain
            if not verify_domain(user_email):
                raise HTTPException(
                    status_code=403, detail=f"Email domain not allowed: {user_email}"
                )

            return user_info

        except JWTAuthError as e:
            raise HTTPException(status_code=401, detail=f"Invalid token: {e}")

    # Fallback to session-based auth (for backward compatibility)
    user_email = request.session.get("user_email")
    user_info = request.session.get("user_info")

    if not user_email or not user_info:
        # Check if request is from a browser (wants HTML)
        accept_header = request.headers.get("accept", "")
        is_browser = "text/html" in accept_header

        if is_browser:
            # Redirect browser to control-plane OAuth login
            # Save the original URL to redirect back after login
            redirect_after_login = str(request.url)
            login_url = f"{CONTROL_PLANE_URL}/auth/login?redirect={redirect_after_login}"
            raise HTTPException(
                status_code=307,  # Temporary redirect (preserves method)
                detail="Redirecting to login",
                headers={"Location": login_url}
            )
        else:
            # API clients get 401 with instructions
            raise HTTPException(
                status_code=401,
                detail=f"Not authenticated. Get token from {CONTROL_PLANE_URL}/auth/token",
            )

    # Verify domain
    if not verify_domain(user_email):
        request.session.clear()
        raise HTTPException(
            status_code=403, detail=f"Email domain not allowed: {user_email}"
        )

    return user_info


async def get_optional_user(request: Request) -> dict | None:
    """
    Optional auth dependency - doesn't raise if not authenticated.

    Returns:
        dict | None: User info if authenticated, None otherwise
    """
    user_email = request.session.get("user_email")
    user_info = request.session.get("user_info")

    if not user_email or not user_info:
        return None

    if not verify_domain(user_email):
        return None

    return user_info
