"""Control Plane FastAPI application for agent and permission management.

Migrated from Flask to FastAPI for consistency with other services.
"""

import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# Import security middleware from shared directory
sys.path.insert(0, str(Path(__file__).parent.parent))  # Add parent to path for shared
from shared.middleware.prometheus_metrics import (
    PrometheusMetricsMiddleware,
    create_metrics_endpoint,
)
from shared.middleware.redis_session import RedisSessionMiddleware
from shared.middleware.security import (
    HTTPSRedirectMiddleware,
    SecurityHeadersMiddleware,
)
from shared.middleware.tracing import TracingMiddleware
from shared.utils.otel_tracing import instrument_fastapi

# Load environment from parent directory .env
parent_env = Path(__file__).parent.parent / ".env"
load_dotenv(parent_env)

# CRITICAL: Ensure control_plane directory is first in sys.path
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan - startup and shutdown."""
    # Startup
    # Validate OAuth configuration at startup
    from utils.auth import validate_oauth_config

    validate_oauth_config()

    ensure_all_users_group()
    ensure_help_agent_system()
    logger.info("Control Plane application initialized")

    yield

    # Shutdown
    logger.info("Control Plane application shutting down")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    # Create FastAPI app with lifespan management
    app = FastAPI(
        title="Control Plane",
        description="Agent and permission management service",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Add session middleware with Redis backend (required for OAuth)
    secret_key = os.getenv("SECRET_KEY", "dev-secret-key-change-in-prod")

    # Validate SECRET_KEY in production
    environment = os.getenv("ENVIRONMENT", "development")
    is_production = environment == "production"
    is_default_key = secret_key in [
        "dev-secret-key-change-in-production",
        "dev-secret-key-change-in-prod",
        "dev-secret-change-in-prod",
    ]
    if is_production and is_default_key:
        raise ValueError(
            "SECRET_KEY must be set to a secure value in production. "
            "Current value is the default development key."
        )

    # Use Redis session middleware for persistent sessions
    app.add_middleware(
        RedisSessionMiddleware,
        secret_key=secret_key,
        session_cookie="session_id",
        max_age=3600 * 24 * 7,  # 7 days
        same_site="lax",
        https_only=is_production,
        domain="localhost",  # Share session cookie across all localhost ports
    )

    # Add tracing middleware (must be first for complete request tracking)
    app.add_middleware(TracingMiddleware, service_name="control-plane")

    # Add OpenTelemetry instrumentation
    instrument_fastapi(app, "control-plane")

    # Add Prometheus metrics middleware
    app.add_middleware(PrometheusMetricsMiddleware, service_name="control-plane")

    # Add security middleware
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(HTTPSRedirectMiddleware)

    # Enable CORS - restrict to specific origins
    allowed_origins = os.getenv(
        "ALLOWED_ORIGINS",
        "https://localhost:6001,https://localhost:5001,https://localhost:3000",
    )
    origins_list = [origin.strip() for origin in allowed_origins.split(",")]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers
    register_routers(app)

    # Serve static files (React UI) - MUST be mounted before catch-all route
    static_folder = Path(__file__).parent / "ui" / "dist"
    if static_folder.exists():
        # Mount assets folder for JS/CSS files
        assets_folder = static_folder / "assets"
        if assets_folder.exists():
            app.mount("/assets", StaticFiles(directory=str(assets_folder)), name="assets")

    # Prometheus metrics endpoint
    app.get("/metrics")(create_metrics_endpoint())

    # Catch-all route for SPA - this must be LAST
    if static_folder.exists():
        @app.get("/")
        @app.get("/{path:path}")
        async def serve_react_app(path: str = ""):
            """Serve React app for all routes (SPA).

            Note: This catch-all must be registered AFTER all other routes/mounts
            to avoid intercepting API calls and static assets.
            """
            # Don't serve index.html for API, auth, or assets paths (safety check)
            if path.startswith("api/") or path.startswith("auth/") or path.startswith("assets/"):
                from fastapi import HTTPException
                raise HTTPException(404)

            index_file = static_folder / "index.html"
            if index_file.exists():
                # Prevent browser caching to ensure auth checks run on every page load
                response = FileResponse(index_file)
                response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
                response.headers["Pragma"] = "no-cache"
                response.headers["Expires"] = "0"
                return response
            return {"status": "UI not built"}

    logger.info("Control Plane FastAPI application initialized on port 6001")
    return app


def register_routers(app: FastAPI) -> None:
    """Register all API routers."""
    from api.agents import router as agents_router
    from api.auth import router as auth_router
    from api.groups import router as groups_router
    from api.health import router as health_router
    from api.users import router as users_router

    # Register routers
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(agents_router)
    app.include_router(groups_router)
    app.include_router(users_router)

    logger.info("Registered all API routers")


def cleanup_duplicate_user_groups() -> None:
    """Remove duplicate user group memberships (one-time cleanup)."""
    try:
        from models import UserGroup, get_db_session
        from sqlalchemy import func

        with get_db_session() as session:
            # Find duplicate entries (same user + group combination)
            duplicates = (
                session.query(
                    UserGroup.slack_user_id,
                    UserGroup.group_name,
                    func.count(UserGroup.id).label('count')
                )
                .group_by(UserGroup.slack_user_id, UserGroup.group_name)
                .having(func.count(UserGroup.id) > 1)
                .all()
            )

            if not duplicates:
                return

            logger.info(f"Found {len(duplicates)} duplicate user-group combinations")

            total_removed = 0
            for slack_user_id, group_name, count in duplicates:
                # Get all entries for this user-group combination
                entries = (
                    session.query(UserGroup)
                    .filter(
                        UserGroup.slack_user_id == slack_user_id,
                        UserGroup.group_name == group_name
                    )
                    .order_by(UserGroup.created_at.asc())  # Keep the oldest
                    .all()
                )

                # Delete all but the first (oldest) entry
                for entry in entries[1:]:
                    session.delete(entry)
                    total_removed += 1

            session.commit()
            logger.info(f"Cleaned up {total_removed} duplicate user group entries")

    except Exception as e:
        logger.error(f"Error cleaning up duplicate user groups: {e}")


def ensure_all_users_group() -> None:
    """Ensure the 'All Users' system group exists and populate it."""
    try:
        from models import PermissionGroup, User, UserGroup, get_db_session

        # First, clean up any duplicates
        cleanup_duplicate_user_groups()

        with get_db_session() as session:
            # Check if "all_users" group exists
            existing_group = (
                session.query(PermissionGroup)
                .filter(PermissionGroup.group_name == "all_users")
                .first()
            )

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
            existing_memberships = (
                session.query(UserGroup)
                .filter(UserGroup.group_name == "all_users")
                .all()
            )
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
                logger.info(f"Added {new_members_added} users to 'All Users' group")

    except Exception as e:
        logger.error(f"Error ensuring 'All Users' group: {e}")


def ensure_help_agent_system() -> None:
    """Ensure the help agent system metadata exists and has all_users group access."""
    try:
        from models import AgentGroupPermission, AgentMetadata, get_db_session

        with get_db_session() as session:
            # Ensure help agent exists
            existing_agent = (
                session.query(AgentMetadata)
                .filter(AgentMetadata.agent_name == "help")
                .first()
            )

            if not existing_agent:
                help_agent = AgentMetadata(
                    agent_name="help",
                    display_name="Help",
                    description="Built-in help command",
                    is_system=True,
                    is_public=True,
                )
                session.add(help_agent)
                session.commit()
                logger.info("Created 'help' system agent")

            # Ensure help agent has all_users group permission
            existing_permission = (
                session.query(AgentGroupPermission)
                .filter(
                    AgentGroupPermission.agent_name == "help",
                    AgentGroupPermission.group_name == "all_users",
                )
                .first()
            )

            if not existing_permission:
                permission = AgentGroupPermission(
                    agent_name="help", group_name="all_users", granted_by="system"
                )
                session.add(permission)
                session.commit()
                logger.info("Granted 'help' agent to 'all_users' group")

    except Exception as e:
        logger.error(f"Error ensuring help agent: {e}")


# Create the app instance at module level for uvicorn
app = create_app()


def main():
    """Run the application directly (not used in Docker, kept for local dev)."""
    port = int(os.getenv("CONTROL_PLANE_PORT", "6001"))

    logger.info(f"Starting Control Plane on port {port}")
    logger.info(f"Dashboard available at: http://localhost:{port}/")

    # Run with uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        reload=(os.getenv("FLASK_ENV") == "development"),
        log_level="info",
    )


if __name__ == "__main__":
    main()
