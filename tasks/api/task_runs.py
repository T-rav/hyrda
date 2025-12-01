"""Task run history endpoints."""

import logging

from flask import Blueprint, Response, jsonify
from models.base import get_db_session
from models.task_metadata import TaskMetadata
from models.task_run import TaskRun

logger = logging.getLogger(__name__)

# Create blueprint
task_runs_bp = Blueprint("task_runs", __name__, url_prefix="/api/task-runs")


@task_runs_bp.route("")
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

            # Load task metadata to get custom names
            metadata_map = {}
            try:
                with get_db_session() as db_session:
                    metadata_map = {
                        m.job_id: m.task_name
                        for m in db_session.query(TaskMetadata).all()
                    }
            except Exception as e:
                logger.error(f"Error loading task metadata: {e}")

            runs_data = []
            for run in task_runs:
                # Extract job type and name from task config snapshot
                job_type = None
                job_name = "Unknown Job"
                if run.task_config_snapshot:
                    job_type = run.task_config_snapshot.get("job_type")
                    # Try to get task_name from snapshot first (most reliable)
                    task_name_from_snapshot = run.task_config_snapshot.get("task_name")
                    if task_name_from_snapshot:
                        job_name = task_name_from_snapshot
                    else:
                        # Fallback to metadata lookup
                        job_id = run.task_config_snapshot.get("job_id")
                        if job_id and job_id in metadata_map:
                            job_name = metadata_map[job_id]
                        else:
                            # Final fallback to job type name
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
