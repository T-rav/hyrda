"""APScheduler WebUI FastAPI application.

Migrated from Flask to FastAPI for consistency with other services.
"""

import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from config.settings import get_settings
from jobs.job_registry import JobRegistry
from services.scheduler_service import SchedulerService

# Import shared middleware from control-plane
sys.path.insert(0, str(Path(__file__).parent.parent))
from shared.middleware.prometheus_metrics import (
    PrometheusMetricsMiddleware,
    create_metrics_endpoint,
)
from shared.middleware.security import SecurityHeadersMiddleware
from shared.middleware.tracing import TracingMiddleware

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

# Global instances (populated in lifespan)
scheduler_service: SchedulerService | None = None
job_registry: JobRegistry | None = None

# Templates directory for Jinja2 (OAuth success/error pages)
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan - startup and shutdown."""
    global scheduler_service, job_registry

    # Startup
    settings = get_settings()

    # Initialize services
    scheduler_service = SchedulerService(settings)
    job_registry = JobRegistry(settings, scheduler_service)

    # Store in app.state for dependency injection
    app.state.scheduler_service = scheduler_service
    app.state.job_registry = job_registry

    # Start scheduler (single worker mode - no distributed locking needed)
    # With --workers 1 in start.sh, only one process runs, so no lock required
    try:
        scheduler_service.start()
        logger.info(f"✅ Scheduler started successfully (PID {os.getpid()})")
        logger.info("Tasks service initialized")
    except Exception as e:
        logger.error(f"Failed to start scheduler: {e}")
        raise

    yield

    # Shutdown
    if scheduler_service:
        scheduler_service.shutdown()
        logger.info("Tasks service shutting down - scheduler stopped")


def register_routers(app: FastAPI) -> None:
    """Register all API routers."""
    from api.auth import router as auth_router
    from api.credentials import router as credentials_router
    from api.gdrive import router as gdrive_router
    from api.health import router as health_router
    from api.hubspot import router as hubspot_router
    from api.jobs import router as jobs_router
    from api.task_runs import router as task_runs_router

    # Register routers
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(jobs_router)
    app.include_router(credentials_router)
    app.include_router(gdrive_router)
    app.include_router(hubspot_router)
    app.include_router(task_runs_router)

    logger.info("Registered all API routers")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = (
        get_settings()
    )  # Will raise ValueError if SECRET_KEY invalid in production

    # Determine environment for middleware configuration
    environment = os.getenv("ENVIRONMENT", "production")
    is_production = environment == "production"

    # Create FastAPI app with lifespan management
    app = FastAPI(
        title="Tasks Service",
        description="APScheduler WebUI and scheduled task management",
        version="1.2.6",
        lifespan=lifespan,
    )

    # Add session middleware (for OAuth state)
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
        max_age=3600 * 24 * 7,  # 7 days
        same_site="lax",
        https_only=is_production,
    )

    # Add tracing middleware (must be early in chain)
    app.add_middleware(TracingMiddleware, service_name="tasks")

    # Add Prometheus metrics middleware (skip in tests/dev to avoid CollectorRegistry duplication)
    environment = os.getenv("ENVIRONMENT", "production")
    if environment not in ("test", "development"):
        app.add_middleware(PrometheusMetricsMiddleware, service_name="tasks")

    # Add security headers middleware
    app.add_middleware(SecurityHeadersMiddleware)

    # Enable CORS
    allowed_origins = os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:5001,http://localhost:6001,http://localhost:3000",
    )
    origins_list = [origin.strip() for origin in allowed_origins.split(",")]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-Request-ID",
            "X-Service-Token",
            "X-Idempotency-Key",
        ],
    )

    # Register API routers (all routes from api/* modules)
    register_routers(app)

    # Prometheus metrics endpoint (skip in tests/dev)
    if environment not in ("test", "development"):
        app.get("/metrics")(create_metrics_endpoint())

    logger.info("Tasks FastAPI application initialized on port 5001")
    return app


# Create module-level app for uvicorn
app = create_app()


def main():
    """Main entry point for direct execution."""
    try:
        settings = get_settings()

        logger.info(f"Starting Tasks Service on {settings.host}:{settings.port}")
        logger.info(f"Dashboard available at: http://localhost:{settings.port}/")

        # Run with uvicorn
        uvicorn.run(
            app,
            host=settings.host,
            port=settings.port,
            reload=(settings.flask_env == "development"),
            log_level="info",
        )

    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    except Exception as e:
        logger.error(f"Application error: {e}")


if __name__ == "__main__":
    main()
