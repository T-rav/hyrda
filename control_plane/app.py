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

    logger.info("Control Plane application initialized on port 6001")
    return app


# API Routes
@app.route("/api/agents")
def list_agents() -> Response:
    """List all registered agents with permission info."""
    try:
        from models import AgentGroupPermission, AgentMetadata, get_db_session

        # Try to get agents from bot registry, but fall back to known agents if not available
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent / "bot"))

        try:
            from agents.registry import agent_registry
            agents = agent_registry.list_agents()
            agents_data = []

            for agent in agents:
                agent_class = agent.get("agent_class")

                # Try to instantiate agent to get description
                description = "No description"
                try:
                    instance = agent_class() if agent_class else None
                    if instance and hasattr(instance, 'description'):
                        description = instance.description
                except Exception as inst_error:
                    logger.warning(f"Could not instantiate agent {agent['name']}: {inst_error}")
                    if agent_class and hasattr(agent_class, 'description'):
                        description = agent_class.description

                # Get metadata and group count from database
                with get_db_session() as session:
                    group_count = session.query(AgentGroupPermission).filter(
                        AgentGroupPermission.agent_name == agent["name"]
                    ).count()

                    # Get agent metadata for enabled state
                    metadata = session.query(AgentMetadata).filter(
                        AgentMetadata.agent_name == agent["name"]
                    ).first()
                    is_enabled = metadata.is_public if metadata else False  # Default to disabled

                agents_data.append({
                    "name": agent["name"],
                    "aliases": agent.get("aliases", []),
                    "description": description,
                    "is_public": is_enabled,
                    "requires_admin": False,
                    "authorized_groups": group_count,
                })

            return jsonify({"agents": agents_data})

        except ImportError:
            # Return mock data with real permission counts
            logger.warning("Cannot import bot agents, using mock data")
            mock_agents = [
                {"name": "profile", "aliases": ["-profile"], "description": "Generate comprehensive company profiles"},
                {"name": "meddic", "aliases": ["-meddic"], "description": "MEDDIC sales methodology coach"},
                {"name": "help", "aliases": ["-help", "?"], "description": "Show available commands and help"},
            ]

            agents_data = []
            with get_db_session() as session:
                for agent in mock_agents:
                    group_count = session.query(AgentGroupPermission).filter(
                        AgentGroupPermission.agent_name == agent["name"]
                    ).count()

                    # Get agent metadata for enabled state
                    metadata = session.query(AgentMetadata).filter(
                        AgentMetadata.agent_name == agent["name"]
                    ).first()
                    is_enabled = metadata.is_public if metadata else False  # Default to disabled

                    agents_data.append({
                        **agent,
                        "is_public": is_enabled,
                        "requires_admin": False,
                        "authorized_groups": group_count,
                    })

            return jsonify({"agents": agents_data})

    except Exception as e:
        logger.error(f"Error listing agents: {e}", exc_info=True)
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

            # Get agent metadata for enabled state
            metadata = session.query(AgentMetadata).filter(
                AgentMetadata.agent_name == agent_name
            ).first()
            is_enabled = metadata.is_public if metadata else False  # Default to disabled

        details = {
            "name": agent_name,
            "authorized_user_ids": authorized_user_ids,
            "authorized_group_names": authorized_group_names,
            "is_public": is_enabled,
        }

        return jsonify(details)
    except Exception as e:
        logger.error(f"Error getting agent details: {e}", exc_info=True)
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


@app.route("/api/groups/<string:group_name>/agents", methods=["POST", "DELETE"])
def manage_group_agents(group_name: str) -> Response:
    """Grant or revoke agent access for a group."""
    try:
        from models import AgentGroupPermission, PermissionGroup, get_db_session

        if request.method == "POST":
            data = request.json
            agent_name = data.get("agent_name")
            granted_by = data.get("granted_by", "admin")

            if not agent_name:
                return jsonify({"error": "agent_name is required"}), 400

            with get_db_session() as session:
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
    app.run(host="0.0.0.0", port=6001, debug=True)
