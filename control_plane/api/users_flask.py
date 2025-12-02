"""User management endpoints."""

import logging
import os
from collections import defaultdict

from flask import Blueprint, Response, jsonify, request, session
from flask.views import MethodView
from models import AgentPermission, PermissionGroup, User, UserGroup, get_db_session
from utils.errors import error_response
from utils.pagination import build_pagination_response, get_pagination_params, paginate_query
from utils.permissions import require_admin
from utils.rate_limit import rate_limit

logger = logging.getLogger(__name__)

# Create blueprint
users_bp = Blueprint("users", __name__, url_prefix="/api/users")


@users_bp.route("/me", methods=["GET"])
@rate_limit(max_requests=100, window_seconds=60)  # 100 requests per minute per IP
def get_current_user() -> Response:
    """Get current authenticated user info.

    Rate limited to 100 requests per minute per IP address.
    """
    try:
        user_email = session.get("user_email")
        user_info = session.get("user_info", {})

        if not user_email:
            return error_response("Not authenticated", 401, "NOT_AUTHENTICATED")

        return jsonify({
            "email": user_email,
            "name": user_info.get("name", ""),
            "picture": user_info.get("picture", ""),
        })

    except Exception as e:
        logger.error(f"Error getting current user: {e}", exc_info=True)
        return error_response(str(e), 500, "INTERNAL_ERROR")


@users_bp.route("", methods=["GET"])
def list_users() -> Response:
    """List all users from security database with their group memberships.

    Query Parameters:
        page: Page number (1-indexed, default: 1)
        per_page: Items per page (default: 50, max: 100)

    Returns:
        JSON response with paginated users and pagination metadata
    """
    try:
        # Get pagination parameters
        page, per_page = get_pagination_params(default_per_page=50, max_per_page=100)

        with get_db_session() as session:
            # Build query
            query = session.query(User).order_by(User.email)

            # Paginate query
            users, total_count = paginate_query(query, page, per_page)

            # Batch load all group memberships for these users in ONE query
            # This prevents N+1 query problem
            user_ids = [user.slack_user_id for user in users]
            all_memberships = session.query(UserGroup, PermissionGroup).join(
                PermissionGroup, UserGroup.group_name == PermissionGroup.group_name
            ).filter(
                UserGroup.slack_user_id.in_(user_ids)
            ).all()

            # Build lookup dictionary: user_id -> [groups]
            memberships_by_user = defaultdict(list)
            for membership, group in all_memberships:
                memberships_by_user[membership.slack_user_id].append({
                    "group_name": group.group_name,
                    "display_name": group.display_name,
                })

            # Build user data using cached memberships
            users_data = []
            for user in users:
                groups = memberships_by_user[user.slack_user_id]

                users_data.append({
                    "id": user.id,
                    "slack_user_id": user.slack_user_id,
                    "email": user.email,
                    "full_name": user.full_name,
                    "is_active": user.is_active,
                    "is_admin": user.is_admin,
                    "last_synced_at": user.last_synced_at.isoformat() if user.last_synced_at else None,
                    "groups": groups,
                })

            # Build paginated response
            response = build_pagination_response(users_data, total_count, page, per_page)
            # Keep "users" key for backward compatibility
            return jsonify({"users": response["items"], "pagination": response["pagination"]})

    except Exception as e:
        logger.error(f"Error listing users: {e}", exc_info=True)
        return error_response(str(e), 500, "INTERNAL_ERROR")


@users_bp.route("/sync", methods=["POST"])
@require_admin
def sync_users() -> Response:
    """Sync users from configured identity provider to security database.

    Provider is configured via USER_MANAGEMENT_PROVIDER environment variable
    (defaults to 'slack'). Supports: slack, google.
    """
    try:
        from services.user_sync import sync_users_from_provider

        # Get provider type from request body or use configured default
        provider_type = request.json.get("provider") if request.json else None

        stats = sync_users_from_provider(provider_type=provider_type)

        provider_name = provider_type or os.getenv("USER_MANAGEMENT_PROVIDER", "slack")
        return jsonify({
            "status": "success",
            "message": f"User sync from {provider_name} completed",
            "stats": stats,
        })

    except ValueError as e:
        # Configuration error
        logger.error(f"Configuration error during user sync: {e}")
        return jsonify({
            "status": "error",
            "message": str(e),
        }), 400

    except Exception as e:
        logger.error(f"Error syncing users: {e}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": f"Sync failed: {str(e)}",
        }), 500


class UserAdminAPI(MethodView):
    """User admin status management using MethodView."""

    def put(self, user_id: int) -> Response:
        """Update user admin status.

        Special case: If no admins exist, anyone can promote the first admin.
        Otherwise, only admins can change admin status.
        """
        try:
            if not request.json or "is_admin" not in request.json:
                return jsonify({"error": "Missing is_admin field"}), 400

            new_admin_status = request.json["is_admin"]

            with get_db_session() as db_session:
                # Use explicit transaction with row-level locking to prevent race conditions
                # This ensures only ONE request can bootstrap the first admin
                with db_session.begin():
                    # Lock ALL admin records to prevent concurrent bootstrap
                    # This prevents TOCTOU (Time-of-Check to Time-of-Use) vulnerability
                    existing_admins = db_session.query(User).filter(
                        User.is_admin
                    ).with_for_update().all()

                    admin_count = len(existing_admins)

                    # If no admins exist, allow bootstrap (first admin creation)
                    if admin_count == 0:
                        logger.info("No admins exist - allowing bootstrap admin creation")
                    else:
                        # Otherwise, require current user to be admin
                        current_user_email = session.get("user_email")
                        if not current_user_email:
                            return error_response("Not authenticated", 401, "NOT_AUTHENTICATED")

                        current_user = db_session.query(User).filter(User.email == current_user_email).first()
                        if not current_user or not current_user.is_admin:
                            return error_response("Only admins can manage admin status", 403, "ADMIN_REQUIRED")

                    # Update the target user (also with lock)
                    user = db_session.query(User).filter(User.id == user_id).with_for_update().first()
                    if not user:
                        return error_response("User not found", 404, "USER_NOT_FOUND")

                    user.is_admin = new_admin_status
                    db_session.commit()

                logger.info(f"User {user.email} admin status changed to {new_admin_status}")

                return jsonify({
                    "status": "success",
                    "message": "User admin status updated",
                    "user": {
                        "id": user.id,
                        "email": user.email,
                        "is_admin": user.is_admin,
                    }
                })

        except Exception as e:
            logger.error(f"Error updating user admin status: {e}", exc_info=True)
            return jsonify({"error": str(e)}), 500


class UserPermissionsAPI(MethodView):
    """User permission management using MethodView."""

    def get(self, user_id: str) -> Response:
        """Get user's direct agent permissions."""
        try:
            with get_db_session() as session:
                # Get user's direct permissions
                permissions = session.query(AgentPermission).filter(
                    AgentPermission.slack_user_id == user_id
                ).all()

                agent_names = [p.agent_name for p in permissions]
                return jsonify({"agent_names": agent_names})

        except Exception as e:
            logger.error(f"Error getting user permissions: {e}", exc_info=True)
            return jsonify({"error": str(e)}), 500

    @require_admin
    def post(self, user_id: str) -> Response:
        """Grant direct agent permission to user."""
        try:
            # Validate request body
            data = request.json
            if not data:
                return error_response("Request body is required", 400, "INVALID_REQUEST")

            agent_name = data.get("agent_name")
            if not agent_name:
                return error_response("agent_name is required", 400, "MISSING_FIELD")
            if not isinstance(agent_name, str):
                return error_response("agent_name must be a string", 400, "INVALID_TYPE")
            if len(agent_name) > 100:
                return error_response("agent_name too long (max 100 characters)", 400, "INVALID_LENGTH")

            granted_by = data.get("granted_by", "admin")
            if not isinstance(granted_by, str):
                return error_response("granted_by must be a string", 400, "INVALID_TYPE")

            with get_db_session() as session:
                # Check if user exists
                user = session.query(User).filter(
                    User.slack_user_id == user_id
                ).first()
                if not user:
                    return jsonify({"error": "User not found"}), 404

                # Check if permission already exists
                existing = session.query(AgentPermission).filter(
                    AgentPermission.slack_user_id == user_id,
                    AgentPermission.agent_name == agent_name
                ).first()
                if existing:
                    return jsonify({"error": "Permission already granted"}), 400

                # Grant permission
                new_permission = AgentPermission(
                    agent_name=agent_name,
                    slack_user_id=user_id,
                    granted_by=granted_by,
                    permission_type="allow"
                )
                session.add(new_permission)
                session.commit()
                return jsonify({"status": "granted"})

        except Exception as e:
            logger.error(f"Error granting user permission: {e}", exc_info=True)
            return jsonify({"error": str(e)}), 500

    @require_admin
    def delete(self, user_id: str) -> Response:
        """Revoke direct agent permission from user."""
        try:
            agent_name = request.args.get("agent_name")
            if not agent_name:
                return jsonify({"error": "agent_name is required"}), 400

            with get_db_session() as session:
                permission = session.query(AgentPermission).filter(
                    AgentPermission.slack_user_id == user_id,
                    AgentPermission.agent_name == agent_name
                ).first()

                if not permission:
                    return jsonify({"error": "Permission not found"}), 404

                session.delete(permission)
                session.commit()
                return jsonify({"status": "revoked"})

        except Exception as e:
            logger.error(f"Error revoking user permission: {e}", exc_info=True)
            return jsonify({"error": str(e)}), 500


# Register MethodView routes
users_bp.add_url_rule(
    "/<int:user_id>/admin",
    view_func=UserAdminAPI.as_view("user_admin"),
    methods=["PUT"]
)

users_bp.add_url_rule(
    "/<string:user_id>/permissions",
    view_func=UserPermissionsAPI.as_view("user_permissions"),
    methods=["GET", "POST", "DELETE"]
)
