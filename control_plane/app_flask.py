"""Control Plane Flask application for agent and permission management.

Refactored architecture using Blueprints and MethodView for clean code organization.
"""

import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, Response, redirect, request, send_from_directory, session
from flask_cors import CORS
from urllib.parse import urlparse

# Load environment from parent directory .env
parent_env = Path(__file__).parent.parent / ".env"
load_dotenv(parent_env)

# CRITICAL: Ensure control_plane directory is first in sys.path
# This prevents importing bot/models instead of control_plane/models
control_plane_dir = str(Path(__file__).parent.absolute())
if control_plane_dir not in sys.path:
    sys.path.insert(0, control_plane_dir)

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
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key-change-in-prod")
    app.config["ENV"] = os.getenv("FLASK_ENV", "development")
    app.config["SESSION_COOKIE_SECURE"] = os.getenv("ENVIRONMENT") == "production"
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

    # Enable CORS
    CORS(app)

    # Register blueprints
    register_blueprints()

    # Ensure system data exists
    ensure_all_users_group()
    ensure_help_agent_system()

    logger.info("Control Plane application initialized on port 6001")
    return app


def register_blueprints() -> None:
    """Register all API blueprints."""
    from api.agents import agents_bp
    from api.auth import auth_bp
    from api.groups import groups_bp
    from api.health import health_bp
    from api.users import users_bp

    # Register blueprints
    app.register_blueprint(health_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(agents_bp)
    app.register_blueprint(groups_bp)
    app.register_blueprint(users_bp)

    logger.info("Registered all API blueprints")


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

            new_members_added = 0
            for user in active_users:
                if user.slack_user_id not in existing_user_ids:
                    membership = UserGroup(
                        slack_user_id=user.slack_user_id,
                        group_name="all_users",
                        added_by="system",
                    )
                    session.add(membership)
                    new_members_added += 1

            if new_members_added > 0:
                session.commit()
                logger.info(f"Added {new_members_added} users to 'all_users' group")

    except Exception as e:
        logger.error(f"Error ensuring 'all_users' group: {e}", exc_info=True)


def ensure_help_agent_system() -> None:
    """Ensure 'help' agent exists, is marked as system agent, and has all_users access."""
    try:
        from models import AgentGroupPermission, AgentMetadata, get_db_session

        with get_db_session() as session:
            help_agent = session.query(AgentMetadata).filter(
                AgentMetadata.agent_name == "help"
            ).first()

            # Create help agent if it doesn't exist
            if not help_agent:
                help_agent = AgentMetadata(
                    agent_name="help",
                    display_name="Help Agent",
                    description="System agent that provides help and guidance",
                    is_public=True,
                    is_system=True,
                    requires_admin=False,
                    is_deleted=False,
                )
                session.add(help_agent)
                session.commit()
                logger.info("Created 'help' system agent")
            elif not help_agent.is_system:
                # Mark existing agent as system
                help_agent.is_system = True
                help_agent.is_public = True
                session.commit()
                logger.info("Marked 'help' agent as system agent")

            # Ensure help agent has all_users access
            existing_permission = session.query(AgentGroupPermission).filter(
                AgentGroupPermission.agent_name == "help",
                AgentGroupPermission.group_name == "all_users"
            ).first()

            if not existing_permission:
                permission = AgentGroupPermission(
                    agent_name="help",
                    group_name="all_users",
                    granted_by="system",
                    permission_type="allow"
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
    from utils.auth import AuditLogger, get_flow, get_redirect_uri, verify_domain

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
            AuditLogger.log_auth_event(
                "access_denied_domain",
                email=email,
                path=request.path,
                success=False,
                error=f"Email domain not allowed: {email}",
            )

    # Not authenticated - redirect to login
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
    # Allowlist of safe redirect path prefixes
    ALLOWED_REDIRECT_PREFIXES = ["/", "/api/agents", "/api/groups", "/api/users"]

    # Check for redirect_to query parameter (user-controlled)
    redirect_to = request.args.get("redirect_to")
    if redirect_to:
        parsed_redirect = urlparse(redirect_to)

        # Reject external redirects (different domain)
        if parsed_redirect.netloc and parsed_redirect.netloc != request.host:
            logger.warning(f"Blocked external redirect attempt: {redirect_to}")
            redirect_url = "/"
        # Check path against allowlist (prefix match)
        elif parsed_redirect.path:
            # Check if path starts with any allowed prefix
            is_allowed = any(
                parsed_redirect.path.startswith(prefix)
                for prefix in ALLOWED_REDIRECT_PREFIXES
            )
            if is_allowed:
                redirect_url = redirect_to
            else:
                logger.warning(f"Blocked redirect to non-allowlisted path: {parsed_redirect.path}")
                redirect_url = "/"
        else:
            redirect_url = "/"
    else:
        # No explicit redirect_to, use referrer or default
        redirect_url = request.referrer if request.referrer else "/"

    session["oauth_redirect"] = redirect_url

    AuditLogger.log_auth_event(
        "login_initiated",
        path=request.path,
    )

    return redirect(authorization_url)


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
    if os.getenv("ENVIRONMENT") == "production":
        logger.warning("Running Flask dev server in production! Use gunicorn instead.")
    app.run(host="0.0.0.0", port=6001, debug=True)
