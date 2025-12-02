"""Authentication dependencies for FastAPI dependency injection."""

from fastapi import HTTPException, Request
from utils.auth import verify_domain


async def get_current_user(request: Request) -> dict:
    """
    Dependency to get the current authenticated user.

    This is the FastAPI-standard way to handle authentication.
    Use with: Depends(get_current_user)

    Returns:
        dict: User info with email and name

    Raises:
        HTTPException: 401 if not authenticated or invalid domain
    """
    # Check if user is authenticated via session
    user_email = request.session.get("user_email")
    user_info = request.session.get("user_info")

    if not user_email or not user_info:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated - please login"
        )

    # Verify domain
    if not verify_domain(user_email):
        request.session.clear()
        raise HTTPException(
            status_code=403,
            detail=f"Email domain not allowed: {user_email}"
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
