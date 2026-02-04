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
        "CONTROL_PLANE_INTERNAL_URL", "https://control-plane:6001"
    )

    try:
        # Forward both Authorization header (JWT) and cookies (session)
        headers = {}
        auth_header = request.headers.get("Authorization")
        if auth_header:
            headers["Authorization"] = auth_header

        # Note: verify=False is intentional for local development (control-plane may use self-signed certs)
        async with httpx.AsyncClient(verify=False) as client:  # nosec B501
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
        ) from e


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


async def verify_admin_from_database(user_email: str) -> bool:
    """
    SECURITY: Re-verify admin status from control-plane database.

    This function provides defense-in-depth by checking the database
    for critical operations, even if JWT token says user is admin.

    Args:
        user_email: Email of user to verify

    Returns:
        bool: True if user is admin in database, False otherwise

    Raises:
        HTTPException: 503 if control-plane is unavailable
    """
    import httpx

    control_plane_url = os.getenv(
        "CONTROL_PLANE_INTERNAL_URL", "https://control-plane:6001"
    )

    try:
        # Call control-plane to verify admin status from database
        # This endpoint should query the database, not just read JWT
        async with httpx.AsyncClient(verify=False) as client:  # nosec B501
            response = await client.get(
                f"{control_plane_url}/api/users/verify-admin",
                params={"email": user_email},
                timeout=5.0,
            )

            if response.status_code == 200:
                data = response.json()
                return data.get("is_admin", False)
            else:
                # If verification fails, deny access (fail closed)
                return False
    except httpx.RequestError:
        # If control-plane is down, deny access (fail closed)
        return False


async def require_admin_from_database(request: Request) -> dict:
    """
    SECURITY: Dependency that requires admin status verified from database.

    Use this for critical write operations (delete, pause, resume) instead of
    just trusting the JWT token's is_admin claim.

    Returns:
        dict: User info

    Raises:
        HTTPException: 401 if not authenticated, 403 if not admin
    """
    # First get user from JWT/session
    user = await get_current_user(request)

    # Then re-verify admin status from database
    is_admin_in_db = await verify_admin_from_database(user["email"])

    if not is_admin_in_db:
        raise HTTPException(
            status_code=403,
            detail="Admin access required. Your admin privileges may have been revoked.",
        )

    return user
