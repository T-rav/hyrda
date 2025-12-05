"""APScheduler WebUI FastAPI application."""

import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from config.settings import get_settings
from jobs.job_registry import JobRegistry
from services.scheduler_service import SchedulerService

# Import security middleware from shared directory
sys.path.insert(0, str(Path(__file__).parent.parent))  # Add parent to path for shared
from shared.middleware.redis_session import RedisSessionMiddleware
from shared.middleware.security import HTTPSRedirectMiddleware, SecurityHeadersMiddleware

# Environment variables loaded by Pydantic from docker-compose.yml

# Configure logging with both console and file handlers
log_dir = Path(__file__).parent / "logs"
log_dir.mkdir(exist_ok=True)

# Create formatters and handlers
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

# Console handler (for docker logs)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)

# File handler (persistent logs with immediate flush)
file_handler = logging.FileHandler(log_dir / "tasks.log")
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(formatter)

# Configure root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.addHandler(console_handler)
root_logger.addHandler(file_handler)

logger = logging.getLogger(__name__)

# Global services (will be initialized in lifespan)
scheduler_service = None
job_registry = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan - startup and shutdown."""
    global scheduler_service, job_registry

    # Startup
    settings = get_settings()

    # Initialize services
    scheduler_service = SchedulerService(settings)
    job_registry = JobRegistry(settings, scheduler_service)

    # Store in app state for access in routes
    app.state.scheduler_service = scheduler_service
    app.state.job_registry = job_registry

    # Start scheduler
    scheduler_service.start()
    logger.info("Scheduler service started")

    yield

    # Shutdown
    if scheduler_service:
        try:
            scheduler_service.shutdown()
            logger.info("Scheduler service shut down successfully")
        except Exception as e:
            logger.error(f"Error shutting down scheduler: {e}")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    # Load settings
    settings = get_settings()

    # Create FastAPI app with lifespan management
    app = FastAPI(
        title="AI Slack Bot - Tasks Service",
        description="APScheduler WebUI for scheduled task management",
        version="1.2.6",
        lifespan=lifespan,
    )

    # Add session middleware with Redis backend (required for OAuth)
    app.add_middleware(
        RedisSessionMiddleware,
        secret_key=settings.secret_key,
        session_cookie="session_id",
        max_age=3600 * 24 * 7,  # 7 days
        same_site="lax",
        https_only=(os.getenv("ENVIRONMENT") == "production"),
    )

    # Add security middleware (must be early in the chain)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(HTTPSRedirectMiddleware)

    # Enable CORS - restrict to specific origins
    allowed_origins = os.getenv(
        "ALLOWED_ORIGINS", "http://localhost:5001,http://localhost:3000"
    )
    origins_list = [origin.strip() for origin in allowed_origins.split(",")]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Add authentication middleware
    app.middleware("http")(authentication_middleware)

    # Register routers
    register_routers(app)

    return app


async def authentication_middleware(request: Request, call_next):
    """
    Lightweight middleware for session setup.

    Authentication is now handled via dependency injection (get_current_user).
    This middleware only ensures sessions are available.
    """
    # All routes can proceed - authentication is handled by dependencies
    return await call_next(request)


def register_routers(app: FastAPI) -> None:
    """Register all API routers."""
    from api.auth import router as auth_router
    from api.credentials import router as credentials_router
    from api.gdrive import router as gdrive_router
    from api.health import router as health_router
    from api.jobs import router as jobs_router
    from api.task_runs import router as task_runs_router

    # Register routers
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(jobs_router)
    app.include_router(task_runs_router)
    app.include_router(credentials_router)
    app.include_router(gdrive_router)

    logger.info("Registered all API routers")


# Create app instance
app = create_app()


def main() -> None:
    """Main entry point."""
    import uvicorn

    settings = get_settings()

    logger.info(f"Starting Tasks WebUI on {settings.host}:{settings.port}")
    logger.info(f"Dashboard available at: http://{settings.host}:{settings.port}/")

    # Run with uvicorn
    uvicorn.run(
        "app:app",
        host=settings.host,
        port=settings.port,
        reload=(os.getenv("ENVIRONMENT", "development") == "development"),
        log_level="info",
    )


if __name__ == "__main__":
    main()
