"""Job management endpoints."""

import logging
from datetime import UTC, datetime

from flask import Blueprint, Response, g, jsonify, request

from models.base import get_db_session
from models.task_metadata import TaskMetadata

logger = logging.getLogger(__name__)

# Create blueprint
jobs_bp = Blueprint("jobs", __name__, url_prefix="/api")


@jobs_bp.before_request
def load_services():
    """Load services into Flask's g object before each request.

    This eliminates the need for global variables while keeping route code clean.
    Services are stored in current_app.extensions and made available via g.
    """
    from flask import current_app, g

    g.scheduler_service = current_app.extensions.get("scheduler_service")
    g.job_registry = current_app.extensions.get("job_registry")


def init_services(scheduler_svc, job_reg):
    """Initialize service references (kept for compatibility).

    Services are now stored in current_app.extensions and accessed via g.
    This function is kept for backward compatibility but is no longer needed.
    """
    # No-op: Services are accessed via g in routes (loaded by before_request hook)
    pass


@jobs_bp.route("/scheduler/info")
def scheduler_info() -> Response | tuple[Response, int]:
    """Get scheduler information."""
    if not g.scheduler_service:
        return jsonify({"error": "Scheduler not initialized"}), 500
    return jsonify(g.scheduler_service.get_scheduler_info())


@jobs_bp.route("/jobs")
def list_jobs() -> Response | tuple[Response, int]:
    """List all jobs."""
    if not g.scheduler_service:
        return jsonify({"error": "Scheduler not initialized"}), 500

    jobs = g.scheduler_service.get_jobs()
    jobs_data = []

    # Load all task metadata
    with get_db_session() as db_session:
        metadata_map = {m.job_id: m for m in db_session.query(TaskMetadata).all()}

    for job in jobs:
        job_info = g.scheduler_service.get_job_info(job.id)
        if job_info:
            # Add custom task name if available
            metadata = metadata_map.get(job.id)
            if metadata:
                job_info["name"] = metadata.task_name
            jobs_data.append(job_info)

    return jsonify({"jobs": jobs_data})


@jobs_bp.route("/jobs/<job_id>")
def get_job(job_id: str) -> Response | tuple[Response, int]:
    """Get specific job details."""
    if not g.scheduler_service:
        return jsonify({"error": "Scheduler not initialized"}), 500

    job_info = g.scheduler_service.get_job_info(job_id)
    if not job_info:
        return jsonify({"error": "Job not found"}), 404

    return jsonify(job_info)


@jobs_bp.route("/jobs/<job_id>/pause", methods=["POST"])
def pause_job(job_id: str) -> Response | tuple[Response, int]:
    """Pause a job."""
    if not g.scheduler_service:
        return jsonify({"error": "Scheduler not initialized"}), 500

    try:
        g.scheduler_service.pause_job(job_id)
        return jsonify({"message": f"Job {job_id} paused successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@jobs_bp.route("/jobs/<job_id>/resume", methods=["POST"])
def resume_job(job_id: str) -> Response | tuple[Response, int]:
    """Resume a job."""
    if not g.scheduler_service:
        return jsonify({"error": "Scheduler not initialized"}), 500

    try:
        g.scheduler_service.resume_job(job_id)
        return jsonify({"message": f"Job {job_id} resumed successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@jobs_bp.route("/jobs/<job_id>", methods=["DELETE"])
def delete_job(job_id: str) -> Response | tuple[Response, int]:
    """Delete a job and its associated metadata."""
    if not g.scheduler_service:
        return jsonify({"error": "Scheduler not initialized"}), 500

    try:
        # Remove the scheduled job from APScheduler
        g.scheduler_service.remove_job(job_id)

        # Clean up associated metadata from database
        with get_db_session() as db_session:
            metadata = (
                db_session.query(TaskMetadata)
                .filter(TaskMetadata.job_id == job_id)
                .first()
            )
            if metadata:
                db_session.delete(metadata)
                db_session.commit()
                logger.info(f"Deleted metadata for job {job_id}")

        return jsonify({"message": f"Job {job_id} deleted successfully"})
    except Exception as e:
        logger.error(f"Error deleting job {job_id}: {e}")
        return jsonify({"error": str(e)}), 400


@jobs_bp.route("/jobs", methods=["POST"])
def create_job() -> Response | tuple[Response, int]:
    """Create a new job."""
    if not g.scheduler_service or not g.job_registry:
        return jsonify({"error": "Services not initialized"}), 500

    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        job_type = data.get("job_type")
        job_id = data.get("job_id")
        schedule = data.get("schedule", {})
        job_params = data.get("parameters", {})
        task_name = data.get("task_name")

        logger.info(
            f"Creating job: type={job_type}, task_name={task_name}, data={data}"
        )

        if not job_type:
            return jsonify({"error": "job_type is required"}), 400

        # Create job using registry
        job = g.job_registry.create_job(
            job_type=job_type, job_id=job_id, schedule=schedule, **job_params
        )

        # Save task metadata (custom name)
        if task_name:
            try:
                logger.info(
                    f"Saving task metadata: job_id={job.id}, task_name={task_name}"
                )
                with get_db_session() as db_session:
                    metadata = TaskMetadata(job_id=job.id, task_name=task_name)
                    db_session.add(metadata)
                    db_session.commit()
                    logger.info(f"Task metadata saved successfully for job {job.id}")
            except Exception as e:
                logger.error(f"Error saving task metadata: {e}", exc_info=True)
        else:
            logger.warning(
                f"No task_name provided for job {job.id}, skipping metadata save"
            )

        return jsonify(
            {"message": f"Job {job.id} created successfully", "job_id": job.id}
        )

    except Exception as e:
        logger.error(f"Error creating job: {e}")
        return jsonify({"error": str(e)}), 400


@jobs_bp.route("/jobs/<job_id>", methods=["PUT"])
def update_job(job_id: str) -> Response | tuple[Response, int]:
    """Update an existing job."""
    if not g.scheduler_service:
        return jsonify({"error": "Scheduler not initialized"}), 500

    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        # Remove job_id from changes if present
        changes = {k: v for k, v in data.items() if k != "job_id"}

        g.scheduler_service.modify_job(job_id, **changes)
        return jsonify({"message": f"Job {job_id} updated successfully"})

    except Exception as e:
        return jsonify({"error": str(e)}), 400


@jobs_bp.route("/jobs/<job_id>/retry", methods=["POST"])
def retry_job(job_id: str) -> Response | tuple[Response, int]:
    """Retry/re-queue a failed job immediately."""
    if not g.scheduler_service:
        return jsonify({"error": "Scheduler not initialized"}), 500

    try:
        job = g.scheduler_service.get_job(job_id)
        if not job:
            return jsonify({"error": "Job not found"}), 404

        # Force job to run immediately by modifying next run time
        g.scheduler_service.modify_job(job_id, next_run_time=datetime.now(UTC))

        return jsonify({"message": f"Job {job_id} queued for immediate retry"})

    except Exception as e:
        return jsonify({"error": str(e)}), 400


@jobs_bp.route("/jobs/<job_id>/run-once", methods=["POST"])
def run_job_once(job_id: str) -> Response | tuple[Response, int]:
    """Run a job once immediately (ad-hoc execution)."""
    if not g.scheduler_service:
        return jsonify({"error": "Scheduler not initialized"}), 500

    try:
        job = g.scheduler_service.get_job(job_id)
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

        g.scheduler_service.add_job(
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


@jobs_bp.route("/jobs/<job_id>/history")
def get_job_history(job_id: str) -> Response | tuple[Response, int]:
    """Get job execution history."""
    if not g.scheduler_service:
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


@jobs_bp.route("/job-types")
def list_job_types() -> Response | tuple[Response, int]:
    """List available job types."""
    if not g.job_registry:
        return jsonify({"error": "Job registry not initialized"}), 500

    return jsonify({"job_types": g.job_registry.get_available_job_types()})
