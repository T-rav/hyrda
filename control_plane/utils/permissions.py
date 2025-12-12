"""Permission system for Control Plane.

Centralized permission checks to support multiple permission tiers.
Future tiers: admin, power_user, read_only, etc.
"""

from typing import Any

from fastapi import HTTPException, Request


async def get_current_user(request: Request) -> Any:
    """Get current user from database.

    FastAPI dependency that retrieves the authenticated user from JWT or session.

    Args:
        request: FastAPI Request object

    Returns:
        User object

    Raises:
        HTTPException: If user is not authenticated or not found
    """
    from models import User, get_db_session
    from dependencies.auth import get_current_user as get_current_user_auth

    # Get user info from JWT or session using auth dependency
    user_info = await get_current_user_auth(request)
    user_email = user_info.get("email")

    if not user_email:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        with get_db_session() as db_session:
            user = db_session.query(User).filter(User.email == user_email).first()
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            return user
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get user: {str(e)}")


async def require_admin(request: Request) -> None:
    """FastAPI dependency to require admin privileges.

    Usage:
        @router.get("/admin-only")
        async def admin_route(admin_check: None = Depends(require_admin)):
            return {"message": "Admin only"}

    Args:
        request: FastAPI Request object

    Raises:
        HTTPException: If user is not authenticated or not an admin
    """
    from dependencies.auth import get_current_user as get_current_user_auth

    # Get user info from JWT or session
    user_info = await get_current_user_auth(request)

    # Check is_admin flag from JWT/session
    if not user_info.get("is_admin", False):
        raise HTTPException(status_code=403, detail="Admin privileges required")

    return None


async def require_permission(permission_type: str, request: Request) -> None:
    """FastAPI dependency to require a specific permission.

    Future implementation for granular permissions.

    Args:
        permission_type: Type of permission required
        request: FastAPI Request object

    Raises:
        HTTPException: If user doesn't have the required permission
    """
    # For now, all permissions require admin
    # Future: Check user.permissions or user_groups for specific permission
    await require_admin(request)
    return None


# Permission tier constants for future use
class PermissionTier:
    """Permission tier definitions."""

    ADMIN = "admin"
    POWER_USER = "power_user"
    READ_ONLY = "read_only"
    USER = "user"


# Future: Permission to tier mapping
PERMISSION_TIERS = {
    "manage_groups": [PermissionTier.ADMIN],
    "manage_agents": [PermissionTier.ADMIN],
    "manage_users": [PermissionTier.ADMIN],
    "view_groups": [
        PermissionTier.ADMIN,
        PermissionTier.POWER_USER,
        PermissionTier.READ_ONLY,
    ],
    "view_agents": [
        PermissionTier.ADMIN,
        PermissionTier.POWER_USER,
        PermissionTier.READ_ONLY,
    ],
    # Add more as needed
}
