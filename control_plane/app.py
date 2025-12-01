"""Control Plane Flask application for agent and permission management."""

import logging
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment from parent directory .env
parent_env = Path(__file__).parent.parent / ".env"
load_dotenv(parent_env)

# CRITICAL: Ensure control_plane directory is first in sys.path
# This prevents importing bot/models instead of control_plane/models
control_plane_dir = str(Path(__file__).parent.absolute())
if control_plane_dir not in sys.path:
    sys.path.insert(0, control_plane_dir)

from flask import Flask, Response, jsonify, request, send_from_directory, session
from flask_cors import CORS

# Configure logging
log_dir = Path(__file__).parent / "logs"
log_dir.mkdir(exist_ok=True)

formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)

file_handler = logging.FileHandler(log_dir / "control_plane.log")
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(formatter)

root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.addHandler(console_handler)
root_logger.addHandler(file_handler)

logger = logging.getLogger(__name__)

# Global instances
app = Flask(__name__, static_folder="ui/dist", static_url_path="")


def create_app() -> Flask:
    """Create and configure the Flask application."""
    import os

    # Configure Flask
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key-change-in-prod")
    app.config["ENV"] = os.getenv("FLASK_ENV", "development")
    app.config["SESSION_COOKIE_SECURE"] = os.getenv("ENVIRONMENT") == "production"
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

    # Enable CORS
    CORS(app)

    # Ensure "All Users" system group exists
    ensure_all_users_group()

    # Ensure "help" system agent exists and has all_users access
    ensure_help_agent_system()

    logger.info("Control Plane application initialized on port 6001")
    return app


def ensure_all_users_group() -> None:
    """Ensure the 'All Users' system group exists and populate it."""
    try:
        from models import PermissionGroup, User, UserGroup, get_db_session

        with get_db_session() as session:
            # Check if "all_users" group exists
            existing_group = session.query(PermissionGroup).filter(
                PermissionGroup.group_name == "all_users"
            ).first()

            if not existing_group:
                # Create the system group
                all_users_group = PermissionGroup(
                    group_name="all_users",
                    display_name="All Users",
                    description="System group that includes all users automatically",
                    created_by="system",
                )
                session.add(all_users_group)
                session.commit()
                logger.info("Created 'All Users' system group")

            # Add all active users to the group
            active_users = session.query(User).filter(User.is_active).all()
            existing_memberships = session.query(UserGroup).filter(
                UserGroup.group_name == "all_users"
            ).all()
            existing_user_ids = {m.slack_user_id for m in existing_memberships}

            added_count = 0
            for user in active_users:
                if user.slack_user_id not in existing_user_ids:
                    new_membership = UserGroup(
                        slack_user_id=user.slack_user_id,
                        group_name="all_users",
                        added_by="system"
                    )
                    session.add(new_membership)
                    added_count += 1

            if added_count > 0:
                session.commit()
                logger.info(f"Added {added_count} users to 'All Users' group on startup")

    except Exception as e:
        logger.error(f"Error ensuring All Users group: {e}", exc_info=True)


def ensure_help_agent_system() -> None:
    """Ensure the 'help' agent is marked as system and has all_users access."""
    try:
        from models import AgentMetadata, AgentGroupPermission, get_db_session

        with get_db_session() as session:
            # Ensure help agent exists and is marked as system
            help_agent = session.query(AgentMetadata).filter(
                AgentMetadata.agent_name == "help"
            ).first()

            if not help_agent:
                # Create help agent
                help_agent = AgentMetadata(
                    agent_name="help",
                    display_name="Help",
                    description="System agent for help and assistance",
                    is_public=True,
                    is_system=True
                )
                session.add(help_agent)
                session.commit()
                logger.info("Created 'help' system agent")
            elif not help_agent.is_system or not help_agent.is_public:
                # Update existing help agent to be system and enabled
                help_agent.is_system = True
                help_agent.is_public = True
                session.commit()
                logger.info("Updated 'help' agent to system agent")

            # Ensure all_users group has access to help agent
            existing_permission = session.query(AgentGroupPermission).filter(
                AgentGroupPermission.agent_name == "help",
                AgentGroupPermission.group_name == "all_users"
            ).first()

            if not existing_permission:
                permission = AgentGroupPermission(
                    agent_name="help",
                    group_name="all_users",
                    permission_type="allow",
                    granted_by="system"
                )
                session.add(permission)
                session.commit()
                logger.info("Granted 'all_users' access to 'help' agent")

    except Exception as e:
        logger.error(f"Error ensuring help agent system status: {e}", exc_info=True)


# Authentication middleware - protect all routes except health and auth
@app.before_request
def require_authentication():
    """Require authentication for all routes except health checks and auth endpoints."""
    from utils.auth import verify_domain

    # Skip auth for health checks, auth endpoints, and static files
    if (
        request.path.startswith("/health")
        or request.path.startswith("/api/health")
        or request.path.startswith("/auth/")
        or request.path.startswith("/assets/")
        or request.path == "/"
    ):
        return None

    # Check if user is authenticated
    if "user_email" in session and "user_info" in session:
        email = session["user_email"]
        # Verify domain on each request
        if verify_domain(email):
            return None
        else:
            # Domain changed or invalid
            session.clear()
            from utils.auth import AuditLogger

            AuditLogger.log_auth_event(
                "access_denied_domain",
                email=email,
                path=request.path,
                success=False,
                error=f"Email domain not allowed: {email}",
            )

    # Not authenticated - redirect to login
    from utils.auth import get_flow, get_redirect_uri
    from urllib.parse import urlparse

    service_base_url = os.getenv("CONTROL_PLANE_BASE_URL", "http://localhost:6001")
    redirect_uri = get_redirect_uri(service_base_url, "/auth/callback")
    flow = get_flow(redirect_uri)
    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="select_account",
    )
    session["oauth_state"] = state

    # Validate redirect URL to prevent open redirect attacks
    # Only allow same-origin redirects
    redirect_url = request.url
    parsed = urlparse(redirect_url)
    if parsed.netloc and parsed.netloc != request.host:
        # External redirect attempt - redirect to home instead
        redirect_url = "/"
    session["oauth_redirect"] = redirect_url

    from utils.auth import AuditLogger

    AuditLogger.log_auth_event(
        "login_initiated",
        path=request.path,
    )

    from flask import redirect

    return redirect(authorization_url)


# Import centralized permission system and error handling
from utils.permissions import require_admin, check_admin
from utils.errors import error_response, success_response
from utils.validation import validate_agent_name, validate_group_name, validate_display_name
from utils.audit import log_agent_action, log_permission_action, log_user_action, log_group_action, AuditAction
from utils.pagination import get_pagination_params, paginate_query, build_pagination_response
from utils.idempotency import require_idempotency
from utils.rate_limit import rate_limit


# Authentication routes
@app.route("/auth/callback")
@rate_limit(max_requests=10, window_seconds=60)  # 10 requests per minute per IP
def auth_callback() -> Response:
    """Handle OAuth callback.

    Rate limited to prevent brute force attacks on OAuth flow.
    Limit: 10 requests per minute per IP address.
    """
    from utils.auth import flask_auth_callback

    service_base_url = os.getenv("CONTROL_PLANE_BASE_URL", "http://localhost:6001")
    return flask_auth_callback(service_base_url, "/auth/callback")


@app.route("/auth/logout", methods=["POST"])
def logout() -> Response:
    """Handle logout."""
    from utils.auth import flask_logout

    return flask_logout()


# API Routes - Protected with authentication
@app.route("/api/agents")
def list_agents() -> Response:
    """List all registered agents from database.

    Agents are now stored in the database (agent_metadata table) and can be
    configured dynamically without code changes. Bot and agent-service query
    this endpoint to discover available agents.

    Query params:
        include_deleted: If "true", include soft-deleted agents (default: false)
        page: Page number (1-indexed, default: 1)
        per_page: Items per page (default: 50, max: 100)
    """
    try:
        from models import AgentGroupPermission, AgentMetadata, get_db_session

        # Check if we should include deleted agents
        include_deleted = request.args.get("include_deleted", "false").lower() == "true"

        # Get pagination parameters
        page, per_page = get_pagination_params(default_per_page=50, max_per_page=100)

        with get_db_session() as session:
            # Get agents from database, filtering deleted by default
            query = session.query(AgentMetadata).order_by(AgentMetadata.agent_name)
            if not include_deleted:
                query = query.filter(~AgentMetadata.is_deleted)

            # Paginate query
            agents, total_count = paginate_query(query, page, per_page)

            # Build agent data
            agents_data = []
            for agent in agents:
                # Count groups with access to this agent
                group_count = session.query(AgentGroupPermission).filter(
                    AgentGroupPermission.agent_name == agent.agent_name
                ).count()

                agents_data.append({
                    "name": agent.agent_name,
                    "display_name": agent.display_name,
                    "aliases": agent.get_aliases(),
                    "description": agent.description or "No description",
                    "is_public": agent.is_public,
                    "requires_admin": agent.requires_admin,
                    "is_system": agent.is_system,
                    "is_deleted": agent.is_deleted,
                    "authorized_groups": group_count,
                })

            # Build paginated response
            response = build_pagination_response(agents_data, total_count, page, per_page)
            # Keep "agents" key for backward compatibility
            return jsonify({"agents": response["items"], "pagination": response["pagination"]})

    except Exception as e:
        logger.error(f"Error listing agents: {e}", exc_info=True)
        return error_response(str(e), 500, "INTERNAL_ERROR")


@app.route("/api/agents/register", methods=["POST"])
@require_idempotency(ttl_hours=24)
def register_agent() -> Response:
    """Register or update an agent in the database.

    Called by agent-service on startup to sync available agents.
    Upserts agent metadata - creates if doesn't exist, updates if it does.

    Headers:
        Idempotency-Key: Optional unique key to prevent duplicate registrations
    """
    try:
        from models import AgentMetadata, get_db_session

        data = request.get_json()
        agent_name = data.get("name")
        display_name = data.get("display_name", agent_name)
        description = data.get("description", "")
        aliases = data.get("aliases", [])
        is_system = data.get("is_system", False)

        # Validate agent name
        is_valid, error_msg = validate_agent_name(agent_name)
        if not is_valid:
            return error_response(error_msg, 400, "VALIDATION_ERROR")

        # Validate display name (optional)
        is_valid, error_msg = validate_display_name(display_name)
        if not is_valid:
            return error_response(error_msg, 400, "VALIDATION_ERROR")

        with get_db_session() as session:
            # Check if agent exists (deleted or not)
            # Use row-level locking to prevent race conditions
            agent = session.query(AgentMetadata).filter(
                AgentMetadata.agent_name == agent_name
            ).with_for_update().first()

            # Validate uniqueness: ensure no non-deleted agent with same name exists
            if agent and agent.is_deleted:
                # Before reactivating, double-check no active agent with same name exists
                existing_active = session.query(AgentMetadata).filter(
                    AgentMetadata.agent_name == agent_name,
                    AgentMetadata.is_deleted == False
                ).first()
                if existing_active:
                    return error_response(
                        f"Agent '{agent_name}' already exists",
                        409,
                        "AGENT_EXISTS"
                    )

            # Check for conflict: non-deleted agent with same name
            if agent and not agent.is_deleted:
                # Update existing active agent
                agent.display_name = display_name
                agent.description = description
                agent.set_aliases(aliases)
                agent.is_system = is_system
                logger.info(f"Updated agent '{agent_name}' in database")
                action = "updated"
            elif agent and agent.is_deleted:
                # Reactivate deleted agent (undelete and update)
                agent.is_deleted = False
                agent.is_public = True  # Re-enable when reactivating
                agent.display_name = display_name
                agent.description = description
                agent.set_aliases(aliases)
                agent.is_system = is_system
                logger.info(f"Reactivated deleted agent '{agent_name}'")
                action = "reactivated"
            else:
                # Create new agent (default enabled)
                agent = AgentMetadata(
                    agent_name=agent_name,
                    display_name=display_name,
                    description=description,
                    is_public=True,  # Default enabled
                    requires_admin=False,
                    is_system=is_system,
                    is_deleted=False,
                )
                agent.set_aliases(aliases)
                session.add(agent)
                logger.info(f"Registered new agent '{agent_name}' in database")
                action = "created"

            session.commit()

        return jsonify({
            "success": True,
            "agent": agent_name,
            "action": action
        })

    except Exception as e:
        logger.error(f"Error registering agent: {e}", exc_info=True)
        return error_response(str(e), 500, "INTERNAL_ERROR")


@app.route("/api/agents/<string:agent_name>")
def get_agent_details(agent_name: str) -> Response:
    """Get detailed information about a specific agent."""
    try:
        from models import AgentPermission, AgentGroupPermission, AgentMetadata, get_db_session

        # Get authorized users and groups from database
        authorized_user_ids = []
        authorized_group_names = []

        with get_db_session() as session:
            # Get direct user permissions
            user_perms = session.query(AgentPermission).filter(
                AgentPermission.agent_name == agent_name
            ).all()
            authorized_user_ids = [p.slack_user_id for p in user_perms]

            # Get group permissions
            group_perms = session.query(AgentGroupPermission).filter(
                AgentGroupPermission.agent_name == agent_name
            ).all()
            authorized_group_names = [p.group_name for p in group_perms]

            # Get agent metadata for enabled state and system status
            metadata = session.query(AgentMetadata).filter(
                AgentMetadata.agent_name == agent_name
            ).first()
            is_enabled = metadata.is_public if metadata else False  # Default to disabled
            is_system = metadata.is_system if metadata else False

        details = {
            "name": agent_name,
            "authorized_user_ids": authorized_user_ids,
            "authorized_group_names": authorized_group_names,
            "is_public": is_enabled,
            "is_system": is_system,
        }

        return jsonify(details)
    except Exception as e:
        logger.error(f"Error getting agent details: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/agents/<string:agent_name>/usage")
def get_agent_usage(agent_name: str) -> Response:
    """Get usage statistics for a specific agent from agent-service."""
    try:
        import requests

        agent_service_url = os.getenv("AGENT_SERVICE_URL", "http://agent_service:8000")
        response = requests.get(f"{agent_service_url}/api/metrics", timeout=5)

        if response.status_code != 200:
            return jsonify({"error": "Unable to fetch usage stats"}), 503

        data = response.json()
        agent_invocations = data.get("agent_invocations", {})
        by_agent = agent_invocations.get("by_agent", {})

        # Get stats for this specific agent
        total = by_agent.get(agent_name, 0)

        return jsonify({
            "agent_name": agent_name,
            "total_invocations": total,
            "all_time_stats": agent_invocations,  # Include overall stats for context
        })
    except Exception as e:
        logger.error(f"Error getting agent usage: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/agents/<string:agent_name>/toggle", methods=["POST"])
@require_admin
def toggle_agent(agent_name: str) -> Response:
    """Toggle agent enabled/disabled state."""
    try:
        from models import AgentMetadata, get_db_session

        with get_db_session() as session:
            # Get or create agent metadata
            agent_metadata = session.query(AgentMetadata).filter(
                AgentMetadata.agent_name == agent_name
            ).first()

            if not agent_metadata:
                # Create new metadata entry, default to enabled (is_public=True)
                agent_metadata = AgentMetadata(
                    agent_name=agent_name,
                    is_public=False,  # Toggle will make it True
                )
                session.add(agent_metadata)

            # Prevent disabling system agents
            if agent_metadata.is_system and agent_metadata.is_public:
                return error_response(
                    "Cannot disable system agents",
                    403,
                    "SYSTEM_AGENT_PROTECTED"
                )

            # Toggle the state
            agent_metadata.is_public = not agent_metadata.is_public
            session.commit()

            return jsonify({
                "agent_name": agent_name,
                "is_enabled": agent_metadata.is_public,
            })

    except Exception as e:
        logger.error(f"Error toggling agent: {e}", exc_info=True)
        return error_response(str(e), 500, "INTERNAL_ERROR")


@app.route("/api/agents/<string:agent_name>", methods=["DELETE"])
@require_admin
def delete_agent(agent_name: str) -> Response:
    """Soft delete an agent (mark as deleted, don't remove from database).

    System agents cannot be deleted.
    Deleted agents are hidden from list_agents() by default.

    Permission Handling:
    - Related permissions in agent_permissions and agent_group_permissions are PRESERVED
    - Permissions remain in the database but are effectively inactive (agent won't appear in lists)
    - If the agent is reactivated via register_agent(), existing permissions are automatically restored
    - This allows temporary removal without losing access control configuration
    - To permanently remove an agent and its permissions, manual database cleanup is required

    Args:
        agent_name: The name of the agent to soft delete

    Returns:
        JSON response with success status or error message

    Raises:
        403: If attempting to delete a system agent
        404: If agent not found
        500: If database error occurs
    """
    try:
        from models import AgentMetadata, get_db_session

        with get_db_session() as session:
            agent_metadata = session.query(AgentMetadata).filter(
                AgentMetadata.agent_name == agent_name
            ).first()

            if not agent_metadata:
                return error_response(
                    f"Agent '{agent_name}' not found",
                    404,
                    "AGENT_NOT_FOUND"
                )

            # Prevent deleting system agents
            if agent_metadata.is_system:
                return error_response(
                    "Cannot delete system agents",
                    403,
                    "SYSTEM_AGENT_PROTECTED"
                )

            # Soft delete: mark as deleted
            agent_metadata.is_deleted = True
            agent_metadata.is_public = False  # Also disable when deleting
            session.commit()

            logger.info(f"Soft deleted agent '{agent_name}'")

            # Audit log
            log_agent_action(
                AuditAction.AGENT_DELETE,
                agent_name,
                {"display_name": agent_metadata.display_name}
            )

            return success_response(
                data={"agent_name": agent_name},
                message=f"Agent '{agent_name}' marked as deleted"
            )

    except Exception as e:
        logger.error(f"Error deleting agent: {e}", exc_info=True)
        return error_response(str(e), 500, "INTERNAL_ERROR")


@app.route("/api/me")
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


@app.route("/api/users")
def list_users() -> Response:
    """List all users from security database with their group memberships.

    Query Parameters:
        page: Page number (1-indexed, default: 1)
        per_page: Items per page (default: 50, max: 100)

    Returns:
        JSON response with paginated users and pagination metadata
    """
    try:
        from models import User, UserGroup, PermissionGroup, get_db_session

        # Get pagination parameters
        page, per_page = get_pagination_params(default_per_page=50, max_per_page=100)

        with get_db_session() as session:
            # Build query
            query = session.query(User).order_by(User.email)

            # Paginate query
            users, total_count = paginate_query(query, page, per_page)

            # Build user data with group memberships
            users_data = []
            for user in users:
                # Get groups this user belongs to
                memberships = session.query(UserGroup, PermissionGroup).join(
                    PermissionGroup, UserGroup.group_name == PermissionGroup.group_name
                ).filter(
                    UserGroup.slack_user_id == user.slack_user_id
                ).all()

                groups = [
                    {
                        "group_name": membership.PermissionGroup.group_name,
                        "display_name": membership.PermissionGroup.display_name,
                    }
                    for membership in memberships
                ]

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


@app.route("/api/users/sync", methods=["POST"])
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




@app.route("/health")
@app.route("/api/health")
def health_check() -> Response:
    """Health check endpoint."""
    return jsonify({"service": "control_plane"})


# Group Management API Routes
@app.route("/api/groups", methods=["GET", "POST"])
def manage_groups() -> Response:
    """List all groups or create a new group."""
    try:
        from models import PermissionGroup, UserGroup, get_db_session

        if request.method == "GET":
            # Get pagination parameters
            page, per_page = get_pagination_params(default_per_page=50, max_per_page=100)

            with get_db_session() as session:
                from models import User

                # Build query
                query = session.query(PermissionGroup).order_by(PermissionGroup.group_name)

                # Paginate query
                groups, total_count = paginate_query(query, page, per_page)

                # Build group data with user details
                groups_data = []
                for group in groups:
                    # Get users for this group with their details
                    user_memberships = session.query(UserGroup, User).join(
                        User, UserGroup.slack_user_id == User.slack_user_id
                    ).filter(
                        UserGroup.group_name == group.group_name
                    ).all()

                    users_list = [
                        {
                            "slack_user_id": membership.User.slack_user_id,
                            "full_name": membership.User.full_name,
                            "email": membership.User.email,
                        }
                        for membership in user_memberships
                    ]

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


@app.route("/api/groups/<string:group_name>", methods=["PUT", "DELETE"])
@require_admin
def manage_group(group_name: str) -> Response:
    """Update or delete a permission group."""
    try:
        from models import PermissionGroup, UserGroup, AgentGroupPermission, get_db_session

        if request.method == "PUT":
            # Update group display name and description
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

        elif request.method == "DELETE":
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


@app.route("/api/users/<int:user_id>/admin", methods=["PUT"])
def update_user_admin_status(user_id: int) -> Response:
    """Update user admin status.

    Special case: If no admins exist, anyone can promote the first admin.
    Otherwise, only admins can change admin status.
    """
    try:
        from models import User, get_db_session

        if not request.json or "is_admin" not in request.json:
            return jsonify({"error": "Missing is_admin field"}), 400

        new_admin_status = request.json["is_admin"]

        with get_db_session() as db_session:
            # Check if any admins exist
            admin_count = db_session.query(User).filter(User.is_admin).count()

            # If no admins exist, allow bootstrap (first admin creation)
            if admin_count == 0:
                logger.info("No admins exist - allowing bootstrap admin creation")
            else:
                # Otherwise, require current user to be admin
                current_user_email = session.get("user_email")
                if not current_user_email:
                    return jsonify({"error": "Not authenticated"}), 401

                current_user = db_session.query(User).filter(User.email == current_user_email).first()
                if not current_user or not current_user.is_admin:
                    return jsonify({"error": "Only admins can manage admin status"}), 403

            # Update the target user
            user = db_session.query(User).filter(User.id == user_id).first()
            if not user:
                return jsonify({"error": "User not found"}), 404

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


@app.route("/api/groups/<string:group_name>/users", methods=["GET", "POST", "DELETE"])
def manage_group_users(group_name: str) -> Response:
    """Manage users in a group."""
    try:
        from models import User, UserGroup, get_db_session

        if request.method == "GET":
            with get_db_session() as session:
                memberships = session.query(UserGroup).filter(
                    UserGroup.group_name == group_name
                ).all()

                users_data = []
                for membership in memberships:
                    user = session.query(User).filter(
                        User.slack_user_id == membership.slack_user_id
                    ).first()
                    if user:
                        users_data.append({
                            "user_id": user.slack_user_id,
                            "email": user.email,
                            "full_name": user.full_name,
                            "added_at": membership.added_at.isoformat() if membership.added_at else None,
                        })

                return jsonify({"users": users_data})

        elif request.method == "POST":
            # Admin check for adding users to groups
            is_admin, error = check_admin()
            if not is_admin:
                return error

            data = request.json
            user_id = data.get("user_id")
            added_by = data.get("added_by", "admin")

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

        elif request.method == "DELETE":
            # Admin check for removing users from groups
            is_admin, error = check_admin()
            if not is_admin:
                return error

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
        logger.error(f"Error managing group users: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/groups/<string:group_name>/agents", methods=["GET", "POST", "DELETE"])
def manage_group_agents(group_name: str) -> Response:
    """Get, grant, or revoke agent access for a group."""
    try:
        from models import AgentGroupPermission, PermissionGroup, get_db_session

        if request.method == "GET":
            with get_db_session() as session:
                # Get all agents this group has access to
                permissions = session.query(AgentGroupPermission).filter(
                    AgentGroupPermission.group_name == group_name
                ).all()

                agent_names = [p.agent_name for p in permissions]
                return jsonify({"agent_names": agent_names})

        elif request.method == "POST":
            # Admin check for granting agent access
            is_admin, error = check_admin()
            if not is_admin:
                return error

            data = request.json
            agent_name = data.get("agent_name")
            granted_by = data.get("granted_by", "admin")

            if not agent_name:
                return jsonify({"error": "agent_name is required"}), 400

            with get_db_session() as session:
                from models import AgentMetadata

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

        elif request.method == "DELETE":
            # Admin check for revoking agent access
            is_admin, error = check_admin()
            if not is_admin:
                return error

            agent_name = request.args.get("agent_name")
            if not agent_name:
                return jsonify({"error": "agent_name is required"}), 400

            with get_db_session() as session:
                from models import AgentMetadata

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
                    f"{group_name}/{agent_name}"
                )

                return jsonify({"status": "revoked"})

    except Exception as e:
        logger.error(f"Error managing group agents: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/users/<string:user_id>/permissions", methods=["GET", "POST", "DELETE"])
def manage_user_permissions(user_id: str) -> Response:
    """Get, grant, or revoke direct user permissions."""
    try:
        from models import AgentPermission, User, get_db_session

        # GET is public for users to see their own permissions
        # POST and DELETE require admin privileges
        if request.method in ["POST", "DELETE"]:
            is_admin, error = check_admin()
            if not is_admin:
                return error

        if request.method == "GET":
            with get_db_session() as session:
                # Get user's direct permissions
                permissions = session.query(AgentPermission).filter(
                    AgentPermission.slack_user_id == user_id
                ).all()

                agent_names = [p.agent_name for p in permissions]
                return jsonify({"agent_names": agent_names})

        elif request.method == "POST":
            data = request.json
            agent_name = data.get("agent_name")
            granted_by = data.get("granted_by", "admin")

            if not agent_name:
                return jsonify({"error": "agent_name is required"}), 400

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

        elif request.method == "DELETE":
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
        logger.error(f"Error managing user permissions: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


# Initialize app
create_app()


# Serve React UI (must be last to act as catch-all)
@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_ui(path: str) -> Response:
    """Serve React UI for all non-API routes."""
    if path and Path(app.static_folder, path).exists():
        return send_from_directory(app.static_folder, path)
    else:
        return send_from_directory(app.static_folder, "index.html")

if __name__ == "__main__":
    # For local development only - use gunicorn in production
    import os
    if os.getenv("ENVIRONMENT") == "production":
        logger.warning("Running Flask dev server in production! Use gunicorn instead.")
    app.run(host="0.0.0.0", port=6001, debug=True)
