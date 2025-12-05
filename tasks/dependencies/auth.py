"""Authentication dependencies for FastAPI dependency injection."""

import sys
from pathlib import Path

from fastapi import HTTPException, Request

# Import JWT utilities from shared directory
sys.path.insert(0, "/app")  # Add app root to path for shared imports
from shared.utils.jwt_auth import JWTAuthError, extract_token_from_request, verify_token
from utils.auth import verify_domain


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
        raise HTTPException(
            status_code=401,
            detail="Not authenticated - please login at control-plane (port 6001)",
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
