"""Authentication dependencies for FastAPI dependency injection."""

import os
import sys

from fastapi import HTTPException, Request

# Import JWT utilities from shared directory
sys.path.insert(0, "/app")  # Add app root to path for shared imports
from utils.auth import verify_domain

# Control plane base URL for redirects
CONTROL_PLANE_URL = os.getenv("CONTROL_PLANE_BASE_URL", "http://localhost:6001")


async def get_current_user(request: Request) -> dict:
    """
    Dependency to get the current authenticated user.

    Proxies auth check to control-plane for centralized session management.
    Supports both JWT (Authorization header) and session (cookies) auth.
    Use with: Depends(get_current_user)

    Returns:
        dict: User info with email and name

    Raises:
        HTTPException: 401 if not authenticated or invalid domain
    """
    import httpx

    # Proxy auth check to control-plane
    control_plane_url = os.getenv(
        "CONTROL_PLANE_INTERNAL_URL", "https://control_plane:6001"
    )

    try:
        # Forward both Authorization header (JWT) and cookies (session)
        headers = {}
        auth_header = request.headers.get("Authorization")
        if auth_header:
            headers["Authorization"] = auth_header

        async with httpx.AsyncClient(verify=False) as client:
            response = await client.get(
                f"{control_plane_url}/api/users/me",
                headers=headers,
                cookies=request.cookies,
                timeout=5.0,
            )

            if response.status_code == 200:
                user_data = response.json()
                return user_data
            else:
                raise HTTPException(
                    status_code=401,
                    detail="Not authenticated",
                )
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Auth service unavailable: {e}",
        )


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
