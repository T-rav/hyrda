"""Authentication dependencies for Control Plane API endpoints."""

import os
import sys

from fastapi import HTTPException, Request

# Import JWT utilities from shared directory
sys.path.insert(0, "/app")
from shared.utils.jwt_auth import JWTAuthError, extract_token_from_request, verify_token


async def get_current_user_or_service(request: Request) -> dict:
    """
    Flexible auth dependency that accepts either user JWT or service token.

    Returns user_info dict with:
    - For user auth: email, name, is_admin, user_id
    - For service auth: {"service": True}
    """
    # Try service token first
    service_token = request.headers.get("X-Service-Token")
    expected_service_token = os.getenv("SERVICE_TOKEN", "dev-service-token-insecure")

    if service_token and service_token == expected_service_token:
        return {"service": True, "is_admin": True}  # Services have admin privileges

    # Fall back to user auth
    return await get_current_user(request)


async def get_current_user(request: Request) -> dict:
    """
    Dependency to get the current authenticated user.

    Supports both JWT tokens (preferred) and session-based auth (fallback).
    Use with: Depends(get_current_user)

    Returns:
        dict: User info with email and name

    Raises:
        HTTPException: 401 if not authenticated
    """
    import logging
    logger = logging.getLogger(__name__)

    # Try JWT token first (from Authorization header or cookie)
    auth_header = request.headers.get("Authorization")
    logger.info(f"🔍 AUTH DEBUG: Method={request.method}, Path={request.url.path}, Auth header present: {bool(auth_header)}")

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
                "is_admin": payload.get("is_admin", False),
                "user_id": payload.get("user_id"),
            }
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
            # Redirect browser to login
            login_url = "/auth/login"
            redirect_after_login = str(request.url)
            raise HTTPException(
                status_code=307,  # Temporary redirect
                detail="Redirecting to login",
                headers={"Location": f"{login_url}?redirect={redirect_after_login}"}
            )
        else:
            # API clients get 401 with instructions
            raise HTTPException(
                status_code=401,
                detail="Not authenticated. Login at /auth/login or get token from /auth/token",
            )

    return user_info
