"""Control Plane Flask application for agent and permission management."""

import logging
import sys
from pathlib import Path

from flask import Flask, Response, jsonify
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
app = Flask(__name__)


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
    """List all users with their permissions."""
    # TODO: Implement user listing from database
    return jsonify({"users": []})


@app.route("/api/health")
def health_check() -> Response:
    """Health check endpoint."""
    return jsonify({"status": "healthy", "service": "control_plane"})


# Initialize app
create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=6001, debug=True)
