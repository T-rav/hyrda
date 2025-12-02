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
from starlette.middleware.sessions import SessionMiddleware

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

    # Add session middleware (required for OAuth)
    secret_key = os.getenv("SECRET_KEY", "dev-secret-key-change-in-prod")
    app.add_middleware(
        SessionMiddleware,
        secret_key=secret_key,
        session_cookie="session",
        max_age=3600 * 24 * 7,  # 7 days
        same_site="lax",
        https_only=(os.getenv("ENVIRONMENT") == "production"),
    )

    # Enable CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure based on needs
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers
    register_routers(app)

    # Serve static files (React UI)
    static_folder = Path(__file__).parent / "ui" / "dist"
    if static_folder.exists():
        app.mount("/static", StaticFiles(directory=str(static_folder)), name="static")

        @app.get("/")
        @app.get("/{path:path}")
        async def serve_react_app(path: str = ""):
            """Serve React app for all routes (SPA)."""
            index_file = static_folder / "index.html"
            if index_file.exists():
                return FileResponse(index_file)
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
                logger.info(f"Added {new_members_added} users to 'All Users' group")

    except Exception as e:
        logger.error(f"Error ensuring 'All Users' group: {e}")


def ensure_help_agent_system() -> None:
    """Ensure the help agent system metadata exists."""
    try:
        from models import AgentMetadata, get_db_session

        with get_db_session() as session:
            existing_agent = session.query(AgentMetadata).filter(
                AgentMetadata.agent_name == "help"
            ).first()

            if not existing_agent:
                help_agent = AgentMetadata(
                    agent_name="help",
                    display_name="Help",
                    description="Built-in help command",
                    prompt_template="",
                    created_by="system",
                    is_system=True,
                )
                session.add(help_agent)
                session.commit()
                logger.info("Created 'help' system agent")

    except Exception as e:
        logger.error(f"Error ensuring help agent: {e}")


def main():
    """Run the application."""
    app = create_app()
    port = int(os.getenv("CONTROL_PLANE_PORT", "6001"))

    logger.info(f"Starting Control Plane on port {port}")
    logger.info(f"Dashboard available at: http://localhost:{port}/")

    # Run with uvicorn
    uvicorn.run(
        "app_fastapi:app",
        host="0.0.0.0",
        port=port,
        reload=(os.getenv("FLASK_ENV") == "development"),
        log_level="info",
    )


if __name__ == "__main__":
    main()
