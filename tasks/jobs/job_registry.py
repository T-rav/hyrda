"""Job registry for managing different types of scheduled jobs."""

import logging
from typing import Any

from apscheduler.job import Job

from config.settings import TasksSettings
from services.scheduler_service import SchedulerService

from .metric_sync import MetricSyncJob
from .portal_sync import PortalSyncJob
from .sec_cleanup_job import SECCleanupJob
from .sec_ingestion_job import SECIngestionJob
from .slack_user_import import SlackUserImportJob

logger = logging.getLogger(__name__)


def execute_job_by_type(
    job_type: str, job_params: dict[str, Any], triggered_by: str = "scheduler"
) -> dict[str, Any]:
    """Global executor function that creates and runs jobs by type."""
    import asyncio
    import uuid
    from datetime import UTC, datetime
    from pathlib import Path

    from config.settings import TasksSettings
    from models.base import get_db_session
    from models.task_run import TaskRun

    # Configure logging for job execution (file + console)
    log_dir = Path(__file__).parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)

    # Add file handler if not already present
    root_logger = logging.getLogger()
    has_file_handler = any(
        isinstance(h, logging.FileHandler) for h in root_logger.handlers
    )

    if not has_file_handler:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        file_handler = logging.FileHandler(log_dir / "tasks.log")
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
        root_logger.setLevel(logging.INFO)
        logger.info(f"📝 File logging enabled for job: {job_type}")

    # Direct mapping - simpler than dynamic imports
    job_classes = {
        "slack_user_import": SlackUserImportJob,
        "metric_sync": MetricSyncJob,
        "portal_sync": PortalSyncJob,
        "sec_ingestion": SECIngestionJob,
        "sec_cleanup": SECCleanupJob,
    }

    job_class = job_classes.get(job_type)
    if not job_class:
        raise ValueError(f"Unknown job type: {job_type}")

    # Create job instance
    settings = TasksSettings()
    job_instance = job_class(settings, **job_params)

    # Create TaskRun record
    run_id = str(uuid.uuid4())
    task_run = TaskRun(
        run_id=run_id,
        status="running",
        started_at=datetime.now(UTC),
        triggered_by=triggered_by,
        task_config_snapshot={"job_type": job_type, "params": job_params},
    )

    try:
        # Save the initial TaskRun record
        with get_db_session() as session:
            session.add(task_run)
            session.commit()
            session.refresh(task_run)

        # Execute the job (async - need to run in event loop)
        result = asyncio.run(job_instance.execute())

        # Update TaskRun with success
        with get_db_session() as session:
            task_run = session.query(TaskRun).filter(TaskRun.run_id == run_id).first()
            if task_run:
                task_run.status = "success"
                task_run.completed_at = datetime.now(UTC)
                task_run.result_data = result
                task_run.calculate_duration()

                # Extract standardized metrics from job result
                if isinstance(result, dict):
                    # Handle BaseJob result structure (result is wrapped in "result" field)
                    job_result = (
                        result.get("result", {}) if "result" in result else result
                    )

                    # All jobs now return standardized fields
                    if isinstance(job_result, dict):
                        task_run.records_processed = job_result.get("records_processed")
                        task_run.records_success = job_result.get("records_success")
                        task_run.records_failed = job_result.get("records_failed")

                session.commit()

        return result

    except Exception as e:
        # Update TaskRun with failure
        try:
            with get_db_session() as session:
                task_run = (
                    session.query(TaskRun).filter(TaskRun.run_id == run_id).first()
                )
                if task_run:
                    task_run.status = "failed"
                    task_run.completed_at = datetime.now(UTC)
                    task_run.error_message = str(e)
                    task_run.calculate_duration()
                    session.commit()
        except Exception as db_error:
            logger.error(f"Failed to update TaskRun on error: {db_error}")

        # Re-raise the original exception
        raise e


class JobRegistry:
    """Registry for managing different types of scheduled jobs."""

    def __init__(self, settings: TasksSettings, scheduler_service: SchedulerService):
        """Initialize the job registry."""
        self.settings = settings
        self.scheduler_service = scheduler_service

        # Job type mapping - starts with built-in jobs
        self.job_types = {
            "slack_user_import": SlackUserImportJob,
            "metric_sync": MetricSyncJob,
            "portal_sync": PortalSyncJob,
            "sec_ingestion": SECIngestionJob,
            "sec_cleanup": SECCleanupJob,
        }

    def register_job_type(self, job_type: str, job_class: type) -> None:
        """
        Register a new job type.

        This allows jobs to self-register, similar to how agents work.

        Args:
            job_type: Unique identifier for the job type
            job_class: Job class (must extend BaseJob)
        """
        if job_type in self.job_types:
            logger.warning(f"Job type '{job_type}' already registered, overwriting")

        self.job_types[job_type] = job_class
        logger.info(f"Registered job type: {job_type} ({job_class.JOB_NAME})")

    def get_available_job_types(self) -> list[dict[str, Any]]:
        """Get available job types with their descriptions."""
        job_types = []

        for job_type, job_class in self.job_types.items():
            job_types.append(
                {
                    "type": job_type,
                    "name": getattr(job_class, "JOB_NAME", job_type),
                    "description": getattr(job_class, "JOB_DESCRIPTION", ""),
                    "required_params": getattr(job_class, "REQUIRED_PARAMS", []),
                    "optional_params": getattr(job_class, "OPTIONAL_PARAMS", []),
                }
            )

        return job_types

    def create_job(
        self,
        job_type: str,
        job_id: str | None = None,
        schedule: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Job:
        """Create a new job of the specified type."""
        if job_type not in self.job_types:
            raise ValueError(f"Unknown job type: {job_type}")

        job_class = self.job_types[job_type]

        # Create job instance to get job ID
        job_instance = job_class(self.settings, **kwargs)

        # Parse schedule configuration
        if not schedule:
            schedule = {"trigger": "interval", "hours": 1}  # Default schedule

        trigger = schedule.get("trigger", "interval")
        schedule_params = {k: v for k, v in schedule.items() if k != "trigger"}

        # Determine if this is a manual run based on job_id
        final_job_id = job_id or f"{job_type}_{job_instance.get_job_id()}"
        triggered_by = "manual" if "_manual_" in final_job_id else "scheduler"

        # Add job to scheduler using global executor function with only serializable data
        job = self.scheduler_service.add_job(
            func=execute_job_by_type,
            trigger=trigger,
            job_id=final_job_id,
            name=f"{job_class.JOB_NAME}",
            args=[job_type, kwargs, triggered_by],  # Include trigger type
            **schedule_params,
        )

        logger.info(f"Created {job_type} job: {job.id}")
        return job

    def get_job_class(self, job_type: str) -> type | None:
        """Get job class for a given job type."""
        return self.job_types.get(job_type)
