"""Control Plane Flask application for agent and permission management."""

import logging
import sys
from pathlib import Path

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
    # Import here to avoid circular dependencies
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent / "bot"))

    try:
        from agents.registry import agent_registry

        agents = agent_registry.list_agents()
        agents_data = []

        for agent in agents:
            agent_class = agent.get("agent_class")

            # Try to instantiate agent to get description, but handle failures gracefully
            description = "No description"
            try:
                instance = agent_class() if agent_class else None
                if instance and hasattr(instance, 'description'):
                    description = instance.description
            except Exception as inst_error:
                logger.warning(f"Could not instantiate agent {agent['name']}: {inst_error}")
                # Try to get description from class attribute
                if agent_class and hasattr(agent_class, 'description'):
                    description = agent_class.description

            agents_data.append({
                "name": agent["name"],
                "aliases": agent.get("aliases", []),
                "description": description,
                "is_public": True,  # TODO: Get from database
                "requires_admin": False,  # TODO: Get from database
                "authorized_users": 0,  # TODO: Count from database
            })

        return jsonify({"agents": agents_data})
    except ImportError as import_error:
        logger.error(f"Cannot import bot agents: {import_error}")
        # Return mock data for development
        return jsonify({"agents": [
            {
                "name": "profile",
                "aliases": ["-profile"],
                "description": "Generate comprehensive company profiles through deep research",
                "is_public": True,
                "requires_admin": False,
                "authorized_users": 0
            },
            {
                "name": "meddic",
                "aliases": ["-meddic", "-medic"],
                "description": "MEDDIC sales methodology coach",
                "is_public": True,
                "requires_admin": False,
                "authorized_users": 0
            },
            {
                "name": "help",
                "aliases": ["-help", "?"],
                "description": "Show available commands and help",
                "is_public": True,
                "requires_admin": False,
                "authorized_users": 0
            }
        ]})
    except Exception as e:
        logger.error(f"Error listing agents: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/agents/<string:agent_name>")
def get_agent_details(agent_name: str) -> Response:
    """Get detailed information about a specific agent."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent / "bot"))

    try:
        from agents.registry import agent_registry

        agent_info = agent_registry.get(agent_name)
        if not agent_info:
            return jsonify({"error": "Agent not found"}), 404

        agent_class = agent_info.get("agent_class")
        instance = agent_class() if agent_class else None

        details = {
            "name": agent_name,
            "aliases": agent_info.get("aliases", []),
            "description": instance.description if instance else "No description",
            "is_public": True,  # TODO: Get from database
            "requires_admin": False,  # TODO: Get from database
            "authorized_users": [],  # TODO: Get from database
        }

        return jsonify(details)
    except Exception as e:
        logger.error(f"Error getting agent details: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/users")
def list_users() -> Response:
    """List all users from security database (synced from Google Workspace)."""
    try:
        from models import User, get_db_session

        with get_db_session() as session:
            users = session.query(User).order_by(User.email).all()
            users_data = [
                {
                    "id": user.id,
                    "slack_user_id": user.slack_user_id,
                    "email": user.email,
                    "full_name": user.full_name,
                    "is_active": user.is_active,
                    "is_admin": user.is_admin,
                    "last_synced_at": user.last_synced_at.isoformat() if user.last_synced_at else None,
                }
                for user in users
            ]
            return jsonify({"users": users_data})

    except Exception as e:
        logger.error(f"Error listing users: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/users/sync", methods=["POST"])
def sync_users() -> Response:
    """Sync users from Google Workspace to security database.

    Links users to slack_users table in data database via slack_user_id.
    """
    try:
        from services import sync_users_from_google

        stats = sync_users_from_google()
        return jsonify({
            "status": "success",
            "message": "User sync completed",
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
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent / "bot"))

    try:
        from services.permission_service import get_permission_service

        permission_service = get_permission_service()

        if request.method == "GET":
            # TODO: Implement list_groups method in PermissionService
            return jsonify({"groups": []})

        elif request.method == "POST":
            data = request.json
            success = permission_service.create_group(
                group_name=data.get("group_name"),
                display_name=data.get("display_name"),
                description=data.get("description"),
                created_by=data.get("created_by"),
            )

            if success:
                return jsonify({"status": "created", "group_name": data.get("group_name")})
            return jsonify({"error": "Failed to create group"}), 400

    except Exception as e:
        logger.error(f"Error managing groups: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/groups/<string:group_name>/users", methods=["GET", "POST", "DELETE"])
def manage_group_users(group_name: str) -> Response:
    """Manage users in a group."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent / "bot"))

    try:
        from services.permission_service import get_permission_service

        permission_service = get_permission_service()

        if request.method == "GET":
            # TODO: Implement get_group_users method
            return jsonify({"users": []})

        elif request.method == "POST":
            data = request.json
            success = permission_service.add_user_to_group(
                user_id=data.get("user_id"),
                group_name=group_name,
                added_by=data.get("added_by"),
            )

            if success:
                return jsonify({"status": "added"})
            return jsonify({"error": "Failed to add user to group"}), 400

        elif request.method == "DELETE":
            user_id = request.args.get("user_id")
            success = permission_service.remove_user_from_group(user_id, group_name)

            if success:
                return jsonify({"status": "removed"})
            return jsonify({"error": "Failed to remove user from group"}), 400

    except Exception as e:
        logger.error(f"Error managing group users: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/groups/<string:group_name>/agents", methods=["POST", "DELETE"])
def manage_group_agents(group_name: str) -> Response:
    """Grant or revoke agent access for a group."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent / "bot"))

    try:
        from services.permission_service import get_permission_service

        permission_service = get_permission_service()

        if request.method == "POST":
            data = request.json
            success = permission_service.grant_group_permission(
                group_name=group_name,
                agent_name=data.get("agent_name"),
                granted_by=data.get("granted_by"),
            )

            if success:
                return jsonify({"status": "granted"})
            return jsonify({"error": "Failed to grant permission"}), 400

        elif request.method == "DELETE":
            agent_name = request.args.get("agent_name")
            success = permission_service.revoke_group_permission(group_name, agent_name)

            if success:
                return jsonify({"status": "revoked"})
            return jsonify({"error": "Failed to revoke permission"}), 400

    except Exception as e:
        logger.error(f"Error managing group agents: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/users/<string:user_id>/permissions", methods=["POST", "DELETE"])
def manage_user_permissions(user_id: str) -> Response:
    """Grant or revoke direct user permissions."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent / "bot"))

    try:
        from services.permission_service import get_permission_service

        permission_service = get_permission_service()

        if request.method == "POST":
            data = request.json
            success = permission_service.grant_permission(
                user_id=user_id,
                agent_name=data.get("agent_name"),
                granted_by=data.get("granted_by"),
            )

            if success:
                return jsonify({"status": "granted"})
            return jsonify({"error": "Failed to grant permission"}), 400

        elif request.method == "DELETE":
            agent_name = request.args.get("agent_name")
            success = permission_service.revoke_permission(user_id, agent_name)

            if success:
                return jsonify({"status": "revoked"})
            return jsonify({"error": "Failed to revoke permission"}), 400

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
