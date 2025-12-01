"""APScheduler WebUI Flask application."""

import logging
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from flask import Flask, Response, jsonify, redirect, render_template, request, session
from flask_cors import CORS

from config.settings import get_settings
from jobs.job_registry import JobRegistry
from models.base import get_db_session
from models.task_metadata import TaskMetadata
from models.task_run import TaskRun
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

# Global instances
app = Flask(__name__)
scheduler_service: SchedulerService | None = None
job_registry: JobRegistry | None = None


def create_app() -> Flask:
    """Create and configure the Flask application."""
    global scheduler_service, job_registry

    # Load settings
    settings = get_settings()

    # Configure Flask
    app.config["SECRET_KEY"] = settings.secret_key
    app.config["ENV"] = settings.flask_env
    app.config["SESSION_COOKIE_SECURE"] = os.getenv("ENVIRONMENT") == "production"
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

    # Enable CORS
    CORS(app)

    # Initialize services
    scheduler_service = SchedulerService(settings)
    job_registry = JobRegistry(settings, scheduler_service)

    # Register blueprints
    register_blueprints()

    # Start scheduler
    scheduler_service.start()

    return app


def register_blueprints() -> None:
    """Register all API blueprints."""
    from api.auth import auth_bp
    from api.credentials import credentials_bp
    from api.gdrive import gdrive_bp
    from api.health import health_bp
    from api.health import init_services as init_health_services
    from api.jobs import init_services as init_job_services
    from api.jobs import jobs_bp
    from api.task_runs import task_runs_bp

    # Initialize services with global references
    init_health_services(scheduler_service)
    init_job_services(scheduler_service, job_registry)

    # Register blueprints
    app.register_blueprint(health_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(jobs_bp)
    app.register_blueprint(task_runs_bp)
    app.register_blueprint(credentials_bp)
    app.register_blueprint(gdrive_bp)

    logger.info("Registered all API blueprints")


# UI serving removed - handled by nginx
# Flask app now serves only API routes

# Authentication middleware - protect all routes except health and auth
@app.before_request
def require_authentication():
    """Require authentication for all routes except health checks and auth endpoints."""
    from utils.auth import verify_domain

    # Skip auth for health checks, auth endpoints, and Google Drive OAuth endpoints
    if (
        request.path.startswith("/health")
        or request.path.startswith("/api/health")
        or request.path.startswith("/auth/")
        or request.path.startswith("/api/gdrive/auth/")  # Google Drive OAuth uses different flow
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
            from utils.auth import AuditLogger

            AuditLogger.log_auth_event(
                "access_denied_domain",
                email=email,
                path=request.path,
                success=False,
                error=f"Email domain not allowed: {email}",
            )

    # Not authenticated - redirect to login
    from utils.auth import get_flow, get_redirect_uri

    service_base_url = os.getenv("SERVER_BASE_URL", "http://localhost:5001")
    redirect_uri = get_redirect_uri(service_base_url, "/auth/callback")
    flow = get_flow(redirect_uri)
    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="select_account",
    )
    session["oauth_state"] = state
    session["oauth_redirect"] = request.url

    from utils.auth import AuditLogger

    AuditLogger.log_auth_event(
        "login_initiated",
        path=request.path,
    )

    return redirect(authorization_url)


def shutdown_scheduler():
    """Shutdown the scheduler gracefully."""
    if scheduler_service:
        scheduler_service.shutdown()


def main():
    """Main entry point."""
    try:
        # Create the app
        flask_app = create_app()

        # Get settings for server configuration
        settings = get_settings()

        logger.info(f"Starting Tasks WebUI on {settings.host}:{settings.port}")
        logger.info(f"Dashboard available at: http://{settings.host}:{settings.port}/")

        # Run the Flask app
        flask_app.run(
            host=settings.host,
            port=settings.port,
            debug=(settings.flask_env == "development"),
            use_reloader=False,  # Avoid double initialization
        )

    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    except Exception as e:
        logger.error(f"Application error: {e}")
    finally:
        shutdown_scheduler()


if __name__ == "__main__":
    main()
