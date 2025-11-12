"""APScheduler WebUI Flask application."""

import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

from flask import Flask, Response, jsonify, redirect, request, session
from flask_cors import CORS

from config.settings import get_settings
from jobs.job_registry import JobRegistry
from models.base import get_db_session
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

    # Enable CORS
    CORS(app)

    # Initialize services
    scheduler_service = SchedulerService(settings)
    job_registry = JobRegistry(settings, scheduler_service)

    # Start scheduler
    scheduler_service.start()

    return app


# UI serving removed - handled by nginx
# Flask app now serves only API routes


# API Routes
@app.route("/api/scheduler/info")
def scheduler_info() -> Response | tuple[Response, int]:
    """Get scheduler information."""
    if not scheduler_service:
        return jsonify({"error": "Scheduler not initialized"}), 500

    return jsonify(scheduler_service.get_scheduler_info())


@app.route("/api/jobs")
def list_jobs() -> Response | tuple[Response, int]:
    """List all jobs."""
    if not scheduler_service:
        return jsonify({"error": "Scheduler not initialized"}), 500

    jobs = scheduler_service.get_jobs()
    jobs_data = []

    for job in jobs:
        job_info = scheduler_service.get_job_info(job.id)
        if job_info:
            jobs_data.append(job_info)

    return jsonify({"jobs": jobs_data})


@app.route("/api/jobs/<job_id>")
def get_job(job_id: str) -> Response | tuple[Response, int]:
    """Get specific job details."""
    if not scheduler_service:
        return jsonify({"error": "Scheduler not initialized"}), 500

    job_info = scheduler_service.get_job_info(job_id)
    if not job_info:
        return jsonify({"error": "Job not found"}), 404

    return jsonify(job_info)


@app.route("/api/jobs/<job_id>/pause", methods=["POST"])
def pause_job(job_id: str) -> Response | tuple[Response, int]:
    """Pause a job."""
    if not scheduler_service:
        return jsonify({"error": "Scheduler not initialized"}), 500

    try:
        scheduler_service.pause_job(job_id)
        return jsonify({"message": f"Job {job_id} paused successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/jobs/<job_id>/resume", methods=["POST"])
def resume_job(job_id: str) -> Response | tuple[Response, int]:
    """Resume a job."""
    if not scheduler_service:
        return jsonify({"error": "Scheduler not initialized"}), 500

    try:
        scheduler_service.resume_job(job_id)
        return jsonify({"message": f"Job {job_id} resumed successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/jobs/<job_id>", methods=["DELETE"])
def delete_job(job_id: str) -> Response | tuple[Response, int]:
    """Delete a job."""
    if not scheduler_service:
        return jsonify({"error": "Scheduler not initialized"}), 500

    try:
        scheduler_service.remove_job(job_id)
        return jsonify({"message": f"Job {job_id} deleted successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/jobs", methods=["POST"])
def create_job() -> Response | tuple[Response, int]:
    """Create a new job."""
    if not scheduler_service or not job_registry:
        return jsonify({"error": "Services not initialized"}), 500

    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        job_type = data.get("job_type")
        job_id = data.get("job_id")
        schedule = data.get("schedule", {})
        job_params = data.get("parameters", {})

        if not job_type:
            return jsonify({"error": "job_type is required"}), 400

        # Create job using registry
        job = job_registry.create_job(
            job_type=job_type, job_id=job_id, schedule=schedule, **job_params
        )

        return jsonify(
            {"message": f"Job {job.id} created successfully", "job_id": job.id}
        )

    except Exception as e:
        logger.error(f"Error creating job: {e}")
        return jsonify({"error": str(e)}), 400


@app.route("/api/jobs/<job_id>", methods=["PUT"])
def update_job(job_id: str) -> Response | tuple[Response, int]:
    """Update an existing job."""
    if not scheduler_service:
        return jsonify({"error": "Scheduler not initialized"}), 500

    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        # Remove job_id from changes if present
        changes = {k: v for k, v in data.items() if k != "job_id"}

        scheduler_service.modify_job(job_id, **changes)
        return jsonify({"message": f"Job {job_id} updated successfully"})

    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/jobs/<job_id>/retry", methods=["POST"])
def retry_job(job_id: str) -> Response | tuple[Response, int]:
    """Retry/re-queue a failed job immediately."""
    if not scheduler_service:
        return jsonify({"error": "Scheduler not initialized"}), 500

    try:
        job = scheduler_service.get_job(job_id)
        if not job:
            return jsonify({"error": "Job not found"}), 404

        # Force job to run immediately by modifying next run time
        scheduler_service.modify_job(job_id, next_run_time=datetime.now(UTC))

        return jsonify({"message": f"Job {job_id} queued for immediate retry"})

    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/jobs/<job_id>/run-once", methods=["POST"])
def run_job_once(job_id: str) -> Response | tuple[Response, int]:
    """Run a job once immediately (ad-hoc execution)."""
    if not scheduler_service:
        return jsonify({"error": "Scheduler not initialized"}), 500

    try:
        job = scheduler_service.get_job(job_id)
        if not job:
            return jsonify({"error": "Job not found"}), 404

        # Create a one-time copy of the job
        one_time_id = f"{job_id}_manual_{int(datetime.now().timestamp())}"

        # Use the same function and args as the original job, but mark as manual
        manual_args = list(job.args) if job.args else []
        # Ensure we have the right number of args and set triggered_by to "manual"
        if len(manual_args) >= 2:
            # Update or add the triggered_by parameter
            if len(manual_args) >= 3:
                manual_args[2] = "manual"  # Replace existing triggered_by
            else:
                manual_args.append("manual")  # Add triggered_by

        scheduler_service.add_job(
            func=job.func,
            trigger="date",
            run_date=datetime.now(UTC),
            job_id=one_time_id,
            name=f"{job.name} (Manual Run)",
            args=manual_args,
        )

        return jsonify(
            {
                "message": f"Created one-time job {one_time_id}",
                "one_time_job_id": one_time_id,
            }
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/jobs/<job_id>/history")
def get_job_history(job_id: str) -> Response | tuple[Response, int]:
    """Get job execution history."""
    if not scheduler_service:
        return jsonify({"error": "Scheduler not initialized"}), 500

    try:
        # This would need to be implemented with a custom job listener
        # For now, return mock data structure
        return jsonify(
            {
                "job_id": job_id,
                "executions": [
                    {
                        "id": f"{job_id}_exec_1",
                        "start_time": "2024-01-20T10:00:00Z",
                        "end_time": "2024-01-20T10:02:30Z",
                        "status": "success",
                        "duration_seconds": 150,
                        "result": {"processed": 25},
                    },
                    {
                        "id": f"{job_id}_exec_2",
                        "start_time": "2024-01-20T11:00:00Z",
                        "end_time": "2024-01-20T11:00:15Z",
                        "status": "failed",
                        "duration_seconds": 15,
                        "error": "Connection timeout",
                    },
                ],
                "total_executions": 2,
                "success_rate": 50.0,
                "avg_duration_seconds": 82.5,
            }
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/job-types")
def list_job_types() -> Response | tuple[Response, int]:
    """List available job types."""
    if not job_registry:
        return jsonify({"error": "Job registry not initialized"}), 500

    return jsonify({"job_types": job_registry.get_available_job_types()})


@app.route("/api/task-runs")
def list_task_runs() -> Response | tuple[Response, int]:
    """List recent task runs."""
    try:
        with get_db_session() as session:
            # Get recent task runs, ordered by most recent first
            task_runs = (
                session.query(TaskRun)
                .order_by(TaskRun.started_at.desc())
                .limit(50)  # Limit to last 50 runs
                .all()
            )

            # Job type to name mapping
            job_type_names = {
                "slack_user_import": "Slack User Import",
                "google_drive_ingest": "Google Drive Ingest",
                "metrics_collection": "Metrics Collection",
            }

            runs_data = []
            for run in task_runs:
                # Extract job type from task config snapshot
                job_type = None
                job_name = "Unknown Job"
                if run.task_config_snapshot:
                    job_type = run.task_config_snapshot.get("job_type")
                    job_name = job_type_names.get(
                        job_type,
                        job_type.replace("_", " ").title()
                        if job_type
                        else "Unknown Job",
                    )

                runs_data.append(
                    {
                        "id": run.id,
                        "run_id": run.run_id,
                        "job_type": job_type,
                        "job_name": job_name,
                        "status": run.status,
                        "started_at": run.started_at.isoformat()
                        if run.started_at
                        else None,
                        "completed_at": run.completed_at.isoformat()
                        if run.completed_at
                        else None,
                        "duration_seconds": run.duration_seconds,
                        "triggered_by": run.triggered_by,
                        "triggered_by_user": run.triggered_by_user,
                        "error_message": run.error_message,
                        "records_processed": run.records_processed,
                        "records_success": run.records_success,
                        "records_failed": run.records_failed,
                    }
                )

            return jsonify({"task_runs": runs_data})

    except Exception as e:
        logger.error(f"Error fetching task runs: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/credentials", methods=["GET"])
def list_credentials() -> Response | tuple[Response, int]:
    """List all stored Google OAuth credentials."""
    try:
        import json
        creds_dir = Path(__file__).parent / "auth" / "gdrive_credentials"
        creds_dir.mkdir(parents=True, exist_ok=True)

        credentials = []
        for meta_file in creds_dir.glob("*.meta.json"):
            try:
                with open(meta_file) as f:
                    metadata = json.load(f)
                    credentials.append(metadata)
            except Exception as e:
                logger.warning(f"Failed to read metadata file {meta_file}: {e}")
                continue

        return jsonify({"credentials": credentials})

    except Exception as e:
        logger.error(f"Error listing credentials: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/credentials", methods=["POST"])
def create_credential() -> Response | tuple[Response, int]:
    """Register a new Google OAuth credential (metadata only - token saved during OAuth)."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        cred_name = data.get("name")
        cred_id = data.get("id")

        if not cred_name or not cred_id:
            return jsonify({"error": "name and id are required"}), 400

        # Check if token file exists (should have been created during OAuth)
        creds_dir = Path(__file__).parent / "auth" / "gdrive_credentials"
        creds_dir.mkdir(parents=True, exist_ok=True)
        token_file = creds_dir / f"{cred_id}.json"

        if not token_file.exists():
            return jsonify({
                "error": "Token not found",
                "details": "OAuth must be completed before saving credential metadata"
            }), 400

        # Save metadata file (just name and creation time)
        metadata_file = creds_dir / f"{cred_id}.meta.json"

        if metadata_file.exists():
            return jsonify({"error": "Credential with this ID already exists"}), 409

        import json
        with open(metadata_file, "w") as f:
            json.dump({
                "id": cred_id,
                "name": cred_name,
                "created_at": datetime.now(UTC).timestamp()
            }, f)

        logger.info(f"Credential metadata saved: {cred_name} ({cred_id})")

        return jsonify({
            "message": "Credential created successfully",
            "id": cred_id,
            "name": cred_name,
        })

    except Exception as e:
        logger.error(f"Error creating credential: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/credentials/<cred_id>", methods=["DELETE"])
def delete_credential(cred_id: str) -> Response | tuple[Response, int]:
    """Delete a stored Google OAuth credential (token + metadata)."""
    try:
        creds_dir = Path(__file__).parent / "auth" / "gdrive_credentials"
        token_file = creds_dir / f"{cred_id}.json"
        meta_file = creds_dir / f"{cred_id}.meta.json"

        if not meta_file.exists():
            return jsonify({"error": "Credential not found"}), 404

        # Delete both files
        if token_file.exists():
            token_file.unlink()
        if meta_file.exists():
            meta_file.unlink()

        logger.info(f"Credential deleted: {cred_id}")

        return jsonify({"message": f"Credential {cred_id} deleted successfully"})

    except Exception as e:
        logger.error(f"Error deleting credential: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/gdrive/auth/initiate", methods=["POST"])
def initiate_gdrive_auth() -> Response | tuple[Response, int]:
    """Initiate Google Drive OAuth flow."""
    try:
        data = request.get_json()
        task_id = data.get("task_id")  # Unique identifier for this task
        credential_id = data.get("credential_id")  # Which credential set to use

        if not task_id:
            return jsonify({"error": "task_id is required"}), 400

        if not credential_id:
            return jsonify({"error": "credential_id is required"}), 400

        # Add ingest path to sys.path
        ingest_path = str(Path(__file__).parent.parent / "ingest")
        if ingest_path not in sys.path:
            sys.path.insert(0, ingest_path)

        from google_auth_oauthlib.flow import Flow

        # Define scopes
        scopes = [
            "https://www.googleapis.com/auth/drive.readonly",
            "https://www.googleapis.com/auth/drive.metadata.readonly",
        ]

        # Get OAuth app credentials from environment (shared for all users)
        import os
        client_id = os.getenv("GOOGLE_OAUTH_CLIENT_ID")
        client_secret = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")

        if not client_id or not client_secret:
            return (
                jsonify(
                    {
                        "error": "Google OAuth not configured",
                        "details": "GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET environment variables must be set",
                    }
                ),
                500,
            )

        # Get settings for redirect URI
        settings = get_settings()
        # Use localhost for OAuth redirect (not 0.0.0.0)
        host = "localhost" if settings.host == "0.0.0.0" else settings.host
        redirect_uri = f"http://{host}:{settings.port}/api/gdrive/auth/callback"

        # Create flow from client config (not from file)
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
            },
            scopes=scopes,
            redirect_uri=redirect_uri
        )

        # Generate authorization URL
        authorization_url, state = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
        )

        # Store state, task_id, and credential_id in session
        session["oauth_state"] = state
        session["oauth_task_id"] = task_id
        session["oauth_credential_id"] = credential_id

        return jsonify({"authorization_url": authorization_url, "state": state})

    except Exception as e:
        logger.error(f"Error initiating Google Drive auth: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/gdrive/auth/callback")
def gdrive_auth_callback() -> Response | tuple[Response, int]:
    """Handle Google Drive OAuth callback."""
    try:
        # Get state, task_id, and credential_id from session
        state = session.get("oauth_state")
        task_id = session.get("oauth_task_id")
        credential_id = session.get("oauth_credential_id")

        if not state or not task_id or not credential_id:
            return jsonify({"error": "Invalid session state"}), 400

        # Add ingest path to sys.path
        ingest_path = str(Path(__file__).parent.parent / "ingest")
        if ingest_path not in sys.path:
            sys.path.insert(0, ingest_path)

        from google_auth_oauthlib.flow import Flow

        # Define scopes
        scopes = [
            "https://www.googleapis.com/auth/drive.readonly",
            "https://www.googleapis.com/auth/drive.metadata.readonly",
        ]

        # Get OAuth app credentials from environment (shared for all users)
        import os
        client_id = os.getenv("GOOGLE_OAUTH_CLIENT_ID")
        client_secret = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")

        if not client_id or not client_secret:
            return jsonify({"error": "Google OAuth not configured"}), 500

        # Get settings for redirect URI
        settings = get_settings()
        # Use localhost for OAuth redirect (not 0.0.0.0)
        host = "localhost" if settings.host == "0.0.0.0" else settings.host
        redirect_uri = f"http://{host}:{settings.port}/api/gdrive/auth/callback"

        # Create flow from client config
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
            },
            scopes=scopes,
            redirect_uri=redirect_uri,
            state=state
        )

        # Fetch token using authorization response
        authorization_response = request.url
        flow.fetch_token(authorization_response=authorization_response)

        # Get credentials (token)
        credentials = flow.credentials

        # Save token to credential-specific file (not task-specific)
        # This allows multiple tasks to share the same credential
        creds_dir = Path(__file__).parent / "auth" / "gdrive_credentials"
        creds_dir.mkdir(parents=True, exist_ok=True)
        token_file = creds_dir / f"{credential_id}.json"

        with open(token_file, "w") as f:
            f.write(credentials.to_json())

        logger.info(f"Google Drive token saved for credential: {credential_id}")

        # Clear session
        session.pop("oauth_state", None)
        session.pop("oauth_task_id", None)
        session.pop("oauth_credential_id", None)

        # Redirect to UI with success message
        return redirect(f"http://{settings.host}:3001/?auth_success=true&task_id={task_id}")

    except Exception as e:
        logger.error(f"Error handling Google Drive auth callback: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/gdrive/auth/status/<task_id>")
def check_gdrive_auth_status(task_id: str) -> Response | tuple[Response, int]:
    """Check if Google Drive authentication exists for a task."""
    try:
        token_file = Path(__file__).parent / "auth" / "gdrive_tokens" / f"{task_id}_token.json"

        if token_file.exists():
            # Verify token is valid
            from google.oauth2.credentials import Credentials

            creds = Credentials.from_authorized_user_file(
                str(token_file),
                [
                    "https://www.googleapis.com/auth/drive.readonly",
                    "https://www.googleapis.com/auth/drive.metadata.readonly",
                ],
            )

            return jsonify(
                {
                    "authenticated": True,
                    "token_file": str(token_file),
                    "valid": creds.valid,
                    "expired": creds.expired if hasattr(creds, "expired") else False,
                }
            )
        else:
            return jsonify({"authenticated": False})

    except Exception as e:
        logger.error(f"Error checking Google Drive auth status: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/health")
def health_check() -> Response:
    """Health check endpoint."""
    return jsonify(
        {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "scheduler_running": scheduler_service.scheduler.running
            if scheduler_service and scheduler_service.scheduler
            else False,
        }
    )


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
