"""Job management endpoints."""

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request

from dependencies.auth import get_current_user, require_admin_from_database
from models.base import get_db_session
from models.task_metadata import TaskMetadata

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


@router.get("/scheduler/info")
async def scheduler_info(request: Request, user: dict = Depends(get_current_user)):
    scheduler_service = request.app.state.scheduler_service
    if not scheduler_service:
        raise HTTPException(status_code=500, detail="Scheduler not initialized")
    return scheduler_service.get_scheduler_info()


@router.get("/jobs")
async def list_jobs(request: Request, user: dict = Depends(get_current_user)):
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
            # Add custom task name and group if available
            metadata = metadata_map.get(job.id)
            if metadata:
                job_info["name"] = metadata.task_name
                job_info["group_name"] = metadata.group_name
            jobs_data.append(job_info)

    return {"jobs": jobs_data}


@router.get("/jobs/{job_id}")
async def get_job(
    request: Request, job_id: str, user: dict = Depends(get_current_user)
):
    scheduler_service = request.app.state.scheduler_service
    if not scheduler_service:
        raise HTTPException(status_code=500, detail="Scheduler not initialized")

    job_info = scheduler_service.get_job_info(job_id)
    if not job_info:
        raise HTTPException(status_code=404, detail="Job not found")

    # Add metadata (name, group) if available
    with get_db_session() as db_session:
        metadata = (
            db_session.query(TaskMetadata).filter(TaskMetadata.job_id == job_id).first()
        )
        if metadata:
            job_info["name"] = metadata.task_name
            job_info["group_name"] = metadata.group_name

    return job_info


@router.post("/jobs/{job_id}/pause")
async def pause_job(
    request: Request, job_id: str, user: dict = Depends(require_admin_from_database)
):
    scheduler_service = request.app.state.scheduler_service
    if not scheduler_service:
        raise HTTPException(status_code=500, detail="Scheduler not initialized")

    try:
        scheduler_service.pause_job(job_id)
        logger.info(f"Job {job_id} paused by {user.get('email')}")
        return {"message": f"Job {job_id} paused successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/jobs/{job_id}/resume")
async def resume_job(
    request: Request, job_id: str, user: dict = Depends(require_admin_from_database)
):
    scheduler_service = request.app.state.scheduler_service
    if not scheduler_service:
        raise HTTPException(status_code=500, detail="Scheduler not initialized")

    try:
        scheduler_service.resume_job(job_id)
        logger.info(f"Job {job_id} resumed by {user.get('email')}")
        return {"message": f"Job {job_id} resumed successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.delete("/jobs/{job_id}")
async def delete_job(
    request: Request, job_id: str, user: dict = Depends(require_admin_from_database)
):
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
                logger.info(f"Deleted metadata for job {job_id} by {user.get('email')}")

        return {"message": f"Job {job_id} deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting job {job_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/jobs")
async def create_job(request: Request, user: dict = Depends(get_current_user)):
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
        group_name = data.get("group_name")

        logger.info(
            f"Creating job: type={job_type}, task_name={task_name}, "
            f"group_name={group_name}, data={data}"
        )

        if not job_type:
            raise HTTPException(status_code=400, detail="job_type is required")

        # Validate job parameters using Pydantic schemas
        from api.job_schemas import validate_job_params

        try:
            validated_params = validate_job_params(job_type, job_params)
        except ValueError as e:
            raise HTTPException(
                status_code=400, detail=f"Invalid job parameters: {str(e)}"
            ) from e

        # Create job using registry (with validated parameters)
        job = job_registry.create_job(
            job_type=job_type, job_id=job_id, schedule=schedule, **validated_params
        )

        # Save task metadata (custom name and group)
        if task_name:
            try:
                logger.info(
                    f"Saving task metadata: job_id={job.id}, task_name={task_name}, "
                    f"group_name={group_name}"
                )
                with get_db_session() as db_session:
                    metadata = TaskMetadata(
                        job_id=job.id, task_name=task_name, group_name=group_name
                    )
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
    scheduler_service = request.app.state.scheduler_service
    if not scheduler_service:
        raise HTTPException(status_code=500, detail="Scheduler not initialized")

    try:
        data = await request.json()
        if not data:
            raise HTTPException(status_code=400, detail="No data provided")

        # Handle metadata updates (task_name, group_name)
        metadata_fields = {"task_name", "group_name"}
        metadata_updates = {k: v for k, v in data.items() if k in metadata_fields}

        if metadata_updates:
            with get_db_session() as db_session:
                metadata = (
                    db_session.query(TaskMetadata)
                    .filter(TaskMetadata.job_id == job_id)
                    .first()
                )
                if metadata:
                    for key, value in metadata_updates.items():
                        setattr(metadata, key, value)
                    db_session.commit()
                    logger.info(
                        f"Updated metadata for job {job_id}: {metadata_updates}"
                    )

        # Remove metadata fields and job_id from scheduler changes
        scheduler_changes = {
            k: v for k, v in data.items() if k not in metadata_fields and k != "job_id"
        }

        if scheduler_changes:
            scheduler_service.modify_job(job_id, **scheduler_changes)

        return {"message": f"Job {job_id} updated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/jobs/{job_id}/retry")
async def retry_job(request: Request, job_id: str):
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
    job_registry = request.app.state.job_registry
    if not job_registry:
        raise HTTPException(status_code=500, detail="Job registry not initialized")

    return {"job_types": job_registry.get_available_job_types()}


@router.get("/groups")
async def list_groups(request: Request, user: dict = Depends(get_current_user)):
    """List all unique group names from task metadata."""
    try:
        with get_db_session() as db_session:
            # Get distinct non-null group names
            groups = (
                db_session.query(TaskMetadata.group_name)
                .filter(TaskMetadata.group_name.isnot(None))
                .filter(TaskMetadata.group_name != "")
                .distinct()
                .all()
            )
            group_names = sorted([g[0] for g in groups])

        return {"groups": group_names}

    except Exception as e:
        logger.error(f"Error listing groups: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e
