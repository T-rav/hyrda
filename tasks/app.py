"""APScheduler WebUI FastAPI application."""

import logging
import os
import secrets
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

from config.settings import get_settings
from jobs.job_registry import JobRegistry
from services.scheduler_service import SchedulerService

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

    # Add session middleware (required for OAuth)
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
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

    # Add authentication middleware
    app.middleware("http")(authentication_middleware)

    # Register routers
    register_routers(app)

    return app


async def authentication_middleware(request: Request, call_next):
    """Require authentication for all routes except health checks and auth endpoints."""
    from utils.auth import AuditLogger, get_flow, get_redirect_uri, verify_domain

    # Skip auth for health checks, auth endpoints, and Google Drive OAuth endpoints
    if (
        request.url.path.startswith("/health")
        or request.url.path.startswith("/api/health")
        or request.url.path.startswith("/auth/")
        or request.url.path.startswith("/api/gdrive/auth/")  # Google Drive OAuth
    ):
        return await call_next(request)

    # Allow tests to bypass auth with a test header
    if request.headers.get("X-Test-Auth") == "authenticated":
        return await call_next(request)

    # Check if user is authenticated
    user_email = request.session.get("user_email")
    user_info = request.session.get("user_info")

    if user_email and user_info:
        # Verify domain on each request
        if verify_domain(user_email):
            return await call_next(request)
        else:
            # Domain changed or invalid
            request.session.clear()
            AuditLogger.log_auth_event(
                "access_denied_domain",
                email=user_email,
                path=request.url.path,
                success=False,
                error=f"Email domain not allowed: {user_email}",
            )

    # Not authenticated - redirect to login
    service_base_url = os.getenv("SERVER_BASE_URL", "http://localhost:5001")
    redirect_uri = get_redirect_uri(service_base_url, "/auth/callback")
    flow = get_flow(redirect_uri)
    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="select_account",
    )

    # Generate CSRF token for additional security
    csrf_token = secrets.token_urlsafe(32)
    request.session["oauth_state"] = state
    request.session["oauth_csrf"] = csrf_token
    request.session["oauth_redirect"] = str(request.url)

    AuditLogger.log_auth_event(
        "login_initiated",
        path=request.url.path,
    )

    return RedirectResponse(url=authorization_url, status_code=302)


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


def main():
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
        reload=(settings.flask_env == "development"),
        log_level="info",
    )


if __name__ == "__main__":
    main()
