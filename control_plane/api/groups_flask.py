"""Group management endpoints."""

import logging
from collections import defaultdict

from flask import Blueprint, Response, jsonify, request
from flask.views import MethodView
from models import (
    AgentGroupPermission,
    AgentMetadata,
    PermissionGroup,
    User,
    UserGroup,
    get_db_session,
)
from utils.audit import AuditAction, log_permission_action
from utils.errors import error_response
from utils.pagination import build_pagination_response, get_pagination_params, paginate_query
from utils.permissions import check_admin, require_admin
from utils.validation import validate_display_name, validate_group_name

logger = logging.getLogger(__name__)

# Create blueprint
groups_bp = Blueprint("groups", __name__, url_prefix="/api/groups")


@groups_bp.route("", methods=["GET", "POST"])
def manage_groups() -> Response:
    """List all groups or create a new group."""
    try:
        if request.method == "GET":
            # Get pagination parameters
            page, per_page = get_pagination_params(default_per_page=50, max_per_page=100)

            with get_db_session() as session:
                # Build query
                query = session.query(PermissionGroup).order_by(PermissionGroup.group_name)

                # Paginate query
                groups, total_count = paginate_query(query, page, per_page)

                # Batch load all user memberships for these groups in ONE query
                # This prevents N+1 query problem
                group_names = [g.group_name for g in groups]
                all_memberships = session.query(UserGroup, User).join(
                    User, UserGroup.slack_user_id == User.slack_user_id
                ).filter(
                    UserGroup.group_name.in_(group_names)
                ).all()

                # Build lookup dictionary: group_name -> [users]
                users_by_group = defaultdict(list)
                for membership, user in all_memberships:
                    users_by_group[membership.group_name].append({
                        "slack_user_id": user.slack_user_id,
                        "full_name": user.full_name,
                        "email": user.email,
                    })

                # Build group data using cached user lists
                groups_data = []
                for group in groups:
                    users_list = users_by_group[group.group_name]

                    groups_data.append({
                        "group_name": group.group_name,
                        "display_name": group.display_name,
                        "description": group.description,
                        "user_count": len(users_list),
                        "users": users_list,
                    })

                # Build paginated response
                response = build_pagination_response(groups_data, total_count, page, per_page)
                # Keep "groups" key for backward compatibility
                return jsonify({"groups": response["items"], "pagination": response["pagination"]})

        elif request.method == "POST":
            # Admin check for group creation
            is_admin, error = check_admin()
            if not is_admin:
                return error

            data = request.json
            group_name = data.get("group_name")
            display_name = data.get("display_name")

            # Validate group name
            is_valid, error_msg = validate_group_name(group_name)
            if not is_valid:
                return error_response(error_msg, 400, "VALIDATION_ERROR")

            # Validate display name (optional)
            is_valid, error_msg = validate_display_name(display_name)
            if not is_valid:
                return error_response(error_msg, 400, "VALIDATION_ERROR")

            with get_db_session() as session:
                new_group = PermissionGroup(
                    group_name=group_name,
                    display_name=display_name,
                    description=data.get("description"),
                    created_by=data.get("created_by", "admin"),
                )
                session.add(new_group)
                session.commit()
                return jsonify({"status": "created", "group_name": group_name})

    except Exception as e:
        logger.error(f"Error managing groups: {e}", exc_info=True)
        return error_response(str(e), 500, "INTERNAL_ERROR")


class GroupAPI(MethodView):
    """Single group management using MethodView."""

    @require_admin
    def put(self, group_name: str) -> Response:
        """Update group display name and description."""
        try:
            data = request.json

            with get_db_session() as session:
                group = session.query(PermissionGroup).filter(
                    PermissionGroup.group_name == group_name
                ).first()

                if not group:
                    return jsonify({"error": "Group not found"}), 404

                # Update fields
                if "display_name" in data:
                    group.display_name = data["display_name"]
                if "description" in data:
                    group.description = data["description"]

                session.commit()

                return jsonify({
                    "status": "updated",
                    "group_name": group_name,
                    "display_name": group.display_name,
                    "description": group.description
                })

        except Exception as e:
            logger.error(f"Error managing group: {e}", exc_info=True)
            return jsonify({"error": str(e)}), 500

    @require_admin
    def delete(self, group_name: str) -> Response:
        """Delete a permission group."""
        try:
            # Prevent deletion of system groups
            if group_name == "all_users":
                return jsonify({"error": "Cannot delete system group"}), 403

            with get_db_session() as session:
                # Check if group exists
                group = session.query(PermissionGroup).filter(
                    PermissionGroup.group_name == group_name
                ).first()

                if not group:
                    return jsonify({"error": "Group not found"}), 404

                # Delete all user memberships
                session.query(UserGroup).filter(
                    UserGroup.group_name == group_name
                ).delete()

                # Delete all agent permissions
                session.query(AgentGroupPermission).filter(
                    AgentGroupPermission.group_name == group_name
                ).delete()

                # Delete the group itself
                session.delete(group)
                session.commit()

                return jsonify({"status": "deleted", "group_name": group_name})

        except Exception as e:
            logger.error(f"Error managing group: {e}", exc_info=True)
            return jsonify({"error": str(e)}), 500


class GroupUsersAPI(MethodView):
    """Group user membership management using MethodView."""

    def get(self, group_name: str) -> Response:
        """Get all users in a group."""
        try:
            with get_db_session() as session:
                memberships = session.query(UserGroup).filter(
                    UserGroup.group_name == group_name
                ).all()

                # Batch load all users in one query to prevent N+1
                user_ids = [m.slack_user_id for m in memberships]
                if not user_ids:
                    return jsonify({"users": []})

                all_users = session.query(User).filter(
                    User.slack_user_id.in_(user_ids)
                ).all()

                # Build lookup dictionary for O(1) access
                users_by_id = {u.slack_user_id: u for u in all_users}

                # Build response using lookup dictionary
                users_data = []
                for membership in memberships:
                    user = users_by_id.get(membership.slack_user_id)
                    if user:
                        users_data.append({
                            "user_id": user.slack_user_id,
                            "email": user.email,
                            "full_name": user.full_name,
                            "added_at": membership.added_at.isoformat() if membership.added_at else None,
                        })

                return jsonify({"users": users_data})

        except Exception as e:
            logger.error(f"Error getting group users: {e}", exc_info=True)
            return jsonify({"error": str(e)}), 500

    @require_admin
    def post(self, group_name: str) -> Response:
        """Add user to group."""
        try:
            # Validate request body
            data = request.json
            if not data:
                return error_response("Request body is required", 400, "INVALID_REQUEST")

            user_id = data.get("user_id")
            if not user_id:
                return error_response("user_id is required", 400, "MISSING_FIELD")
            if not isinstance(user_id, str):
                return error_response("user_id must be a string", 400, "INVALID_TYPE")
            if len(user_id) > 255:
                return error_response("user_id too long (max 255 characters)", 400, "INVALID_LENGTH")

            added_by = data.get("added_by", "admin")
            if not isinstance(added_by, str):
                return error_response("added_by must be a string", 400, "INVALID_TYPE")

            with get_db_session() as session:
                # Check if user exists
                user = session.query(User).filter(
                    User.slack_user_id == user_id
                ).first()
                if not user:
                    return jsonify({"error": "User not found"}), 404

                # Check if already in group
                existing = session.query(UserGroup).filter(
                    UserGroup.slack_user_id == user_id,
                    UserGroup.group_name == group_name
                ).first()
                if existing:
                    return jsonify({"error": "User already in group"}), 400

                # Add user to group
                new_membership = UserGroup(
                    slack_user_id=user_id,
                    group_name=group_name,
                    added_by=added_by
                )
                session.add(new_membership)
                session.commit()
                return jsonify({"status": "added"})

        except Exception as e:
            logger.error(f"Error adding user to group: {e}", exc_info=True)
            return jsonify({"error": str(e)}), 500

    @require_admin
    def delete(self, group_name: str) -> Response:
        """Remove user from group."""
        try:
            user_id = request.args.get("user_id")
            if not user_id:
                return jsonify({"error": "user_id is required"}), 400

            # Prevent manual removal from system groups
            if group_name == "all_users":
                return jsonify({"error": "Cannot manually remove users from system group"}), 403

            with get_db_session() as session:
                membership = session.query(UserGroup).filter(
                    UserGroup.slack_user_id == user_id,
                    UserGroup.group_name == group_name
                ).first()

                if not membership:
                    return jsonify({"error": "User not in group"}), 404

                session.delete(membership)
                session.commit()
                return jsonify({"status": "removed"})

        except Exception as e:
            logger.error(f"Error removing user from group: {e}", exc_info=True)
            return jsonify({"error": str(e)}), 500


class GroupAgentsAPI(MethodView):
    """Group agent permissions management using MethodView."""

    def get(self, group_name: str) -> Response:
        """Get all agents this group has access to."""
        try:
            with get_db_session() as session:
                permissions = session.query(AgentGroupPermission).filter(
                    AgentGroupPermission.group_name == group_name
                ).all()

                agent_names = [p.agent_name for p in permissions]
                return jsonify({"agent_names": agent_names})

        except Exception as e:
            logger.error(f"Error getting group agents: {e}", exc_info=True)
            return jsonify({"error": str(e)}), 500

    @require_admin
    def post(self, group_name: str) -> Response:
        """Grant agent access to group."""
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
                # Check if agent is system agent
                agent_metadata = session.query(AgentMetadata).filter(
                    AgentMetadata.agent_name == agent_name
                ).first()

                if agent_metadata and agent_metadata.is_system and group_name != "all_users":
                    return jsonify({
                        "error": "System agents can only be granted to 'all_users' group"
                    }), 403

                # Check if group exists
                group = session.query(PermissionGroup).filter(
                    PermissionGroup.group_name == group_name
                ).first()
                if not group:
                    return jsonify({"error": "Group not found"}), 404

                # Check if permission already exists
                existing = session.query(AgentGroupPermission).filter(
                    AgentGroupPermission.agent_name == agent_name,
                    AgentGroupPermission.group_name == group_name
                ).first()
                if existing:
                    return jsonify({"error": "Permission already granted"}), 400

                # Grant permission
                new_permission = AgentGroupPermission(
                    agent_name=agent_name,
                    group_name=group_name,
                    granted_by=granted_by,
                    permission_type="allow"
                )
                session.add(new_permission)
                session.commit()

                # Audit log
                log_permission_action(
                    AuditAction.GRANT_PERMISSION,
                    "agent_group_permission",
                    f"{group_name}/{agent_name}",
                    {"granted_by": granted_by}
                )

                return jsonify({"status": "granted"})

        except Exception as e:
            logger.error(f"Error granting agent to group: {e}", exc_info=True)
            return jsonify({"error": str(e)}), 500

    @require_admin
    def delete(self, group_name: str) -> Response:
        """Revoke agent access from group."""
        try:
            agent_name = request.args.get("agent_name")
            if not agent_name:
                return jsonify({"error": "agent_name is required"}), 400

            with get_db_session() as session:
                # Check if agent is system agent
                agent_metadata = session.query(AgentMetadata).filter(
                    AgentMetadata.agent_name == agent_name
                ).first()

                if agent_metadata and agent_metadata.is_system and group_name == "all_users":
                    return jsonify({
                        "error": "Cannot revoke system agents from 'all_users' group"
                    }), 403

                permission = session.query(AgentGroupPermission).filter(
                    AgentGroupPermission.agent_name == agent_name,
                    AgentGroupPermission.group_name == group_name
                ).first()

                if not permission:
                    return jsonify({"error": "Permission not found"}), 404

                session.delete(permission)
                session.commit()

                # Audit log
                log_permission_action(
                    AuditAction.REVOKE_PERMISSION,
                    "agent_group_permission",
                    f"{group_name}/{agent_name}",
                    {}
                )

                return jsonify({"status": "revoked"})

        except Exception as e:
            logger.error(f"Error revoking agent from group: {e}", exc_info=True)
            return jsonify({"error": str(e)}), 500


# Register MethodView routes
groups_bp.add_url_rule(
    "/<string:group_name>",
    view_func=GroupAPI.as_view("group"),
    methods=["PUT", "DELETE"]
)

groups_bp.add_url_rule(
    "/<string:group_name>/users",
    view_func=GroupUsersAPI.as_view("group_users"),
    methods=["GET", "POST", "DELETE"]
)

groups_bp.add_url_rule(
    "/<string:group_name>/agents",
    view_func=GroupAgentsAPI.as_view("group_agents"),
    methods=["GET", "POST", "DELETE"]
)
