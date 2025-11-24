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

from flask import Flask, Response, jsonify, request, send_from_directory
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
    # Configure Flask
    app.config["SECRET_KEY"] = "dev-secret-key-change-in-prod"
    app.config["ENV"] = "development"

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
            active_users = session.query(User).filter(User.is_active == True).all()
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


# API Routes
@app.route("/api/agents")
def list_agents() -> Response:
    """List all registered agents from database.

    Agents are now stored in the database (agent_metadata table) and can be
    configured dynamically without code changes. Bot and agent-service query
    this endpoint to discover available agents.
    """
    try:
        from models import AgentGroupPermission, AgentMetadata, get_db_session

        agents_data = []
        with get_db_session() as session:
            # Get all agents from database
            agents = session.query(AgentMetadata).all()

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
                    "authorized_groups": group_count,
                })

        return jsonify({"agents": agents_data})

    except Exception as e:
        logger.error(f"Error listing agents: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/agents/register", methods=["POST"])
def register_agent() -> Response:
    """Register or update an agent in the database.

    Called by agent-service on startup to sync available agents.
    Upserts agent metadata - creates if doesn't exist, updates if it does.
    """
    try:
        from models import AgentMetadata, get_db_session

        data = request.get_json()
        agent_name = data.get("name")
        display_name = data.get("display_name", agent_name)
        description = data.get("description", "")
        aliases = data.get("aliases", [])
        is_system = data.get("is_system", False)

        if not agent_name:
            return jsonify({"error": "name is required"}), 400

        with get_db_session() as session:
            # Check if agent exists
            agent = session.query(AgentMetadata).filter(
                AgentMetadata.agent_name == agent_name
            ).first()

            if agent:
                # Update existing agent
                agent.display_name = display_name
                agent.description = description
                agent.set_aliases(aliases)
                agent.is_system = is_system
                logger.info(f"Updated agent '{agent_name}' in database")
            else:
                # Create new agent (default enabled)
                agent = AgentMetadata(
                    agent_name=agent_name,
                    display_name=display_name,
                    description=description,
                    is_public=True,  # Default enabled
                    requires_admin=False,
                    is_system=is_system,
                )
                agent.set_aliases(aliases)
                session.add(agent)
                logger.info(f"Registered new agent '{agent_name}' in database")

            session.commit()

        return jsonify({
            "success": True,
            "agent": agent_name,
            "action": "updated" if agent else "created"
        })

    except Exception as e:
        logger.error(f"Error registering agent: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


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
                return jsonify({"error": "Cannot disable system agents"}), 403

            # Toggle the state
            agent_metadata.is_public = not agent_metadata.is_public
            session.commit()

            return jsonify({
                "agent_name": agent_name,
                "is_enabled": agent_metadata.is_public,
            })

    except Exception as e:
        logger.error(f"Error toggling agent: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/users")
def list_users() -> Response:
    """List all users from security database with their group memberships."""
    try:
        from models import User, UserGroup, PermissionGroup, get_db_session

        with get_db_session() as session:
            users = session.query(User).order_by(User.email).all()
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

            return jsonify({"users": users_data})

    except Exception as e:
        logger.error(f"Error listing users: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/users/sync", methods=["POST"])
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
    return jsonify({"status": "healthy", "service": "control_plane"})


# Group Management API Routes
@app.route("/api/groups", methods=["GET", "POST"])
def manage_groups() -> Response:
    """List all groups or create a new group."""
    try:
        from models import PermissionGroup, UserGroup, get_db_session

        if request.method == "GET":
            with get_db_session() as session:
                from models import User

                # Get all groups with their user counts and user details
                groups = session.query(PermissionGroup).all()

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

                return jsonify({"groups": groups_data})

        elif request.method == "POST":
            data = request.json
            with get_db_session() as session:
                new_group = PermissionGroup(
                    group_name=data.get("group_name"),
                    display_name=data.get("display_name"),
                    description=data.get("description"),
                    created_by=data.get("created_by", "admin"),
                )
                session.add(new_group)
                session.commit()
                return jsonify({"status": "created", "group_name": data.get("group_name")})

    except Exception as e:
        logger.error(f"Error managing groups: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/groups/<string:group_name>", methods=["PUT", "DELETE"])
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
                return jsonify({"status": "granted"})

        elif request.method == "DELETE":
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
                return jsonify({"status": "revoked"})

    except Exception as e:
        logger.error(f"Error managing group agents: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/users/<string:user_id>/permissions", methods=["GET", "POST", "DELETE"])
def manage_user_permissions(user_id: str) -> Response:
    """Get, grant, or revoke direct user permissions."""
    try:
        from models import AgentPermission, User, get_db_session

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
