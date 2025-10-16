"""APScheduler WebUI Flask application."""

import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

from flask import Flask, Response, jsonify, request
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
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

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
