"""Task run history endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from dependencies.auth import get_current_user
from models.base import get_db_session
from models.task_metadata import TaskMetadata
from models.task_run import TaskRun

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/task-runs")

# Pagination constants
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 100  # Prevent DoS attacks by limiting max page size


@router.get("")
async def list_task_runs(
    request: Request,
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    per_page: int = Query(
        DEFAULT_PAGE_SIZE,
        ge=1,
        description=f"Items per page (max {MAX_PAGE_SIZE})",
    ),
    user: dict = Depends(get_current_user),
):
    """List recent task runs with pagination.

    Query Parameters:
        page: Page number (1-indexed, default: 1)
        per_page: Items per page (default: 50, max: 100)

    Returns:
        JSON response with task runs and pagination metadata
    """
    try:
        # Cap per_page at MAX_PAGE_SIZE (silent capping for better UX)
        per_page = min(per_page, MAX_PAGE_SIZE)
        with get_db_session() as session:
            # Build query
            query = session.query(TaskRun).order_by(TaskRun.started_at.desc())

            # Get total count for pagination metadata
            total_count = query.count()

            # Calculate offset and get paginated results
            offset = (page - 1) * per_page
            task_runs = query.offset(offset).limit(per_page).all()

            # Job type to name mapping
            job_type_names = {
                "slack_user_import": "Slack User Import",
                "google_drive_ingest": "Google Drive Ingest",
                "metrics_collection": "Metrics Collection",
            }

            # Extract job IDs from task runs to only load needed metadata
            job_ids = set()
            for run in task_runs:
                if run.task_config_snapshot:
                    job_id = run.task_config_snapshot.get("job_id")
                    if job_id:
                        job_ids.add(job_id)

            # Load ONLY the metadata we need
            metadata_map = {}
            if job_ids:
                try:
                    metadata_records = (
                        session.query(TaskMetadata)
                        .filter(TaskMetadata.job_id.in_(job_ids))
                        .all()
                    )
                    metadata_map = {m.job_id: m.task_name for m in metadata_records}
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
                    task_name_from_snapshot = run.task_config_snapshot.get(
                        "task_name"
                    )
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
                                (
                                    job_type.replace("_", " ").title()
                                    if job_type
                                    else "Unknown Job"
                                ),
                            )

                runs_data.append(
                    {
                        "id": run.id,
                        "run_id": run.run_id,
                        "job_type": job_type,
                        "job_name": job_name,
                        "status": run.status,
                        "started_at": (
                            run.started_at.isoformat() if run.started_at else None
                        ),
                        "completed_at": (
                            run.completed_at.isoformat() if run.completed_at else None
                        ),
                        "duration_seconds": run.duration_seconds,
                        "triggered_by": run.triggered_by,
                        "triggered_by_user": run.triggered_by_user,
                        "error_message": run.error_message,
                        "records_processed": run.records_processed,
                        "records_success": run.records_success,
                        "records_failed": run.records_failed,
                    }
                )

            # Calculate pagination metadata
            total_pages = (total_count + per_page - 1) // per_page  # Ceiling division

            return {
                "task_runs": runs_data,
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total": total_count,
                    "total_pages": total_pages,
                    "has_prev": page > 1,
                    "has_next": page < total_pages,
                },
            }

    except Exception as e:
        logger.error(f"Error fetching task runs: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e
