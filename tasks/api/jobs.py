"""Job management endpoints."""

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from dependencies.auth import get_current_user
from fastapi.responses import JSONResponse

from models.base import get_db_session
from models.task_metadata import TaskMetadata

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


@router.get("/scheduler/info")
async def scheduler_info(request: Request, user: dict = Depends(get_current_user)):
    """Get scheduler information.

    Returns:
        Scheduler status and configuration
    """
    scheduler_service = request.app.state.scheduler_service
    if not scheduler_service:
        raise HTTPException(status_code=500, detail="Scheduler not initialized")
    return scheduler_service.get_scheduler_info()


@router.get("/jobs")
async def list_jobs(request: Request, user: dict = Depends(get_current_user)):
    """List all jobs.

    Returns:
        Dictionary with list of all scheduled jobs
    """
    scheduler_service = request.app.state.scheduler_service
    if not scheduler_service:
        raise HTTPException(status_code=500, detail="Scheduler not initialized")

    jobs = scheduler_service.get_jobs()
    jobs_data = []

    # Load all task metadata
    with get_db_session() as db_session:
        metadata_map = {m.job_id: m for m in db_session.query(TaskMetadata).all()}

    for job in jobs:
        job_info = scheduler_service.get_job_info(job.id)
        if job_info:
            # Add custom task name if available
            metadata = metadata_map.get(job.id)
            if metadata:
                job_info["name"] = metadata.task_name
            jobs_data.append(job_info)

    return {"jobs": jobs_data}


@router.get("/jobs/{job_id}")
async def get_job(
    request: Request, job_id: str, user: dict = Depends(get_current_user)
):
    """Get specific job details.

    Args:
        job_id: Job identifier

    Returns:
        Job details
    """
    scheduler_service = request.app.state.scheduler_service
    if not scheduler_service:
        raise HTTPException(status_code=500, detail="Scheduler not initialized")

    job_info = scheduler_service.get_job_info(job_id)
    if not job_info:
        raise HTTPException(status_code=404, detail="Job not found")

    return job_info


@router.post("/jobs/{job_id}/pause")
async def pause_job(request: Request, job_id: str):
    """Pause a job.

    Args:
        job_id: Job identifier

    Returns:
        Success message
    """
    scheduler_service = request.app.state.scheduler_service
    if not scheduler_service:
        raise HTTPException(status_code=500, detail="Scheduler not initialized")

    try:
        scheduler_service.pause_job(job_id)
        return {"message": f"Job {job_id} paused successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/jobs/{job_id}/resume")
async def resume_job(request: Request, job_id: str):
    """Resume a job.

    Args:
        job_id: Job identifier

    Returns:
        Success message
    """
    scheduler_service = request.app.state.scheduler_service
    if not scheduler_service:
        raise HTTPException(status_code=500, detail="Scheduler not initialized")

    try:
        scheduler_service.resume_job(job_id)
        return {"message": f"Job {job_id} resumed successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.delete("/jobs/{job_id}")
async def delete_job(request: Request, job_id: str):
    """Delete a job and its associated metadata.

    Args:
        job_id: Job identifier

    Returns:
        Success message
    """
    scheduler_service = request.app.state.scheduler_service
    if not scheduler_service:
        raise HTTPException(status_code=500, detail="Scheduler not initialized")

    try:
        # Remove the scheduled job from APScheduler
        scheduler_service.remove_job(job_id)

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

        return {"message": f"Job {job_id} deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting job {job_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/jobs")
async def create_job(request: Request, user: dict = Depends(get_current_user)):
    """Create a new job.

    Request Body:
        - job_type: Type of job to create
        - job_id: Optional job identifier
        - schedule: Schedule configuration
        - parameters: Job parameters
        - task_name: Optional custom task name

    Returns:
        Success message with job ID
    """
    scheduler_service = request.app.state.scheduler_service
    job_registry = request.app.state.job_registry

    if not scheduler_service or not job_registry:
        raise HTTPException(status_code=500, detail="Services not initialized")

    try:
        data = await request.json()
        if not data:
            raise HTTPException(status_code=400, detail="No data provided")

        job_type = data.get("job_type")
        job_id = data.get("job_id")
        schedule = data.get("schedule", {})
        job_params = data.get("parameters", {})
        task_name = data.get("task_name")

        logger.info(
            f"Creating job: type={job_type}, task_name={task_name}, data={data}"
        )

        if not job_type:
            raise HTTPException(status_code=400, detail="job_type is required")

        # Create job using registry
        job = job_registry.create_job(
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

        return {"message": f"Job {job.id} created successfully", "job_id": job.id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating job: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.put("/jobs/{job_id}")
async def update_job(request: Request, job_id: str):
    """Update an existing job.

    Args:
        job_id: Job identifier

    Request Body:
        Job configuration changes

    Returns:
        Success message
    """
    scheduler_service = request.app.state.scheduler_service
    if not scheduler_service:
        raise HTTPException(status_code=500, detail="Scheduler not initialized")

    try:
        data = await request.json()
        if not data:
            raise HTTPException(status_code=400, detail="No data provided")

        # Remove job_id from changes if present
        changes = {k: v for k, v in data.items() if k != "job_id"}

        scheduler_service.modify_job(job_id, **changes)
        return {"message": f"Job {job_id} updated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/jobs/{job_id}/retry")
async def retry_job(request: Request, job_id: str):
    """Retry/re-queue a failed job immediately.

    Args:
        job_id: Job identifier

    Returns:
        Success message
    """
    scheduler_service = request.app.state.scheduler_service
    if not scheduler_service:
        raise HTTPException(status_code=500, detail="Scheduler not initialized")

    try:
        job = scheduler_service.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        # Force job to run immediately by modifying next run time
        scheduler_service.modify_job(job_id, next_run_time=datetime.now(UTC))

        return {"message": f"Job {job_id} queued for immediate retry"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/jobs/{job_id}/run-once")
async def run_job_once(request: Request, job_id: str):
    """Run a job once immediately (ad-hoc execution).

    Args:
        job_id: Job identifier

    Returns:
        Success message with one-time job ID
    """
    scheduler_service = request.app.state.scheduler_service
    if not scheduler_service:
        raise HTTPException(status_code=500, detail="Scheduler not initialized")

    try:
        job = scheduler_service.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

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

        return {
            "message": f"Created one-time job {one_time_id}",
            "one_time_job_id": one_time_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/jobs/{job_id}/history")
async def get_job_history(request: Request, job_id: str):
    """Get job execution history.

    Args:
        job_id: Job identifier

    Returns:
        Job execution history with statistics
    """
    scheduler_service = request.app.state.scheduler_service
    if not scheduler_service:
        raise HTTPException(status_code=500, detail="Scheduler not initialized")

    try:
        # This would need to be implemented with a custom job listener
        # For now, return mock data structure
        return {
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

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/job-types")
async def list_job_types(request: Request, user: dict = Depends(get_current_user)):
    """List available job types.

    Returns:
        Dictionary with list of available job types
    """
    job_registry = request.app.state.job_registry
    if not job_registry:
        raise HTTPException(status_code=500, detail="Job registry not initialized")

    return {"job_types": job_registry.get_available_job_types()}
