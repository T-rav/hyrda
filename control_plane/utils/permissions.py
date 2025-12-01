"""Permission system for Control Plane.

Centralized permission checks to support multiple permission tiers.
Future tiers: admin, power_user, read_only, etc.
"""

from functools import wraps
from typing import Callable

from flask import g, jsonify, session


def get_current_user():
    """Get current user from database.

    Uses Flask's g object to cache the user for the request lifecycle.
    This prevents race conditions and improves performance by avoiding
    multiple database queries per request.

    Returns:
        User object if found, None otherwise
    """
    # Check if user is already cached in request context
    if hasattr(g, "current_user"):
        return g.current_user

    from models import User, get_db_session

    user_email = session.get("user_email")
    if not user_email:
        g.current_user = None
        return None

    try:
        with get_db_session() as db_session:
            user = db_session.query(User).filter(User.email == user_email).first()
            # Cache user for this request
            g.current_user = user
            return user
    except Exception:
        g.current_user = None
        return None


def check_authenticated():
    """Check if user is authenticated.

    Returns:
        tuple: (bool, error_response) - (True, None) if authenticated, (False, Response) if not
    """
    user_email = session.get("user_email")
    if not user_email:
        return False, (jsonify({"error": "Not authenticated"}), 401)
    return True, None


def check_admin():
    """Check if current user is an admin.

    Returns:
        tuple: (bool, error_response) - (True, None) if admin, (False, Response) if not
    """
    # First check authentication
    is_authenticated, error = check_authenticated()
    if not is_authenticated:
        return False, error

    # Get user and check admin status
    user = get_current_user()
    if not user:
        return False, (jsonify({"error": "User not found"}), 404)

    if not user.is_admin:
        return False, (jsonify({"error": "Admin privileges required"}), 403)

    return True, None


def check_permission(permission_type: str):
    """Check if current user has a specific permission.

    Future implementation for granular permissions.

    Args:
        permission_type: Type of permission to check (e.g., 'manage_groups', 'manage_agents')

    Returns:
        tuple: (bool, error_response)
    """
    # For now, all permissions require admin
    # Future: Check user.permissions or user_groups for specific permission
    return check_admin()


def require_admin(f: Callable) -> Callable:
    """Decorator to require admin privileges for a route.

    Usage:
        @app.route("/api/admin-only")
        @require_admin
        def admin_route():
            return jsonify({"message": "Admin only"})
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        is_admin, error = check_admin()
        if not is_admin:
            return error
        return f(*args, **kwargs)

    return decorated_function


def require_permission(permission_type: str) -> Callable:
    """Decorator to require a specific permission for a route.

    Future implementation for granular permissions.

    Args:
        permission_type: Type of permission required

    Usage:
        @app.route("/api/groups")
        @require_permission("manage_groups")
        def manage_groups():
            return jsonify({"message": "Managing groups"})
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            has_permission, error = check_permission(permission_type)
            if not has_permission:
                return error
            return f(*args, **kwargs)
        return decorated_function
    return decorator


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
    "view_groups": [PermissionTier.ADMIN, PermissionTier.POWER_USER, PermissionTier.READ_ONLY],
    "view_agents": [PermissionTier.ADMIN, PermissionTier.POWER_USER, PermissionTier.READ_ONLY],
    # Add more as needed
}
