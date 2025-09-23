"""Job registry for managing different types of scheduled jobs."""

import logging
from typing import Any

from apscheduler.job import Job

from config.settings import TasksSettings
from services.scheduler_service import SchedulerService

from .google_drive_ingest import GoogleDriveIngestJob
from .metrics_collection import MetricsCollectionJob
from .slack_user_import import SlackUserImportJob

logger = logging.getLogger(__name__)


def execute_job_by_type(job_type: str, job_params: dict[str, Any]) -> dict[str, Any]:
    """Global executor function that creates and runs jobs by type."""
    from config.settings import TasksSettings

    # Job type mapping - keep this simple and static
    job_types = {
        "slack_user_import": "jobs.slack_user_import.SlackUserImportJob",
        "google_drive_ingest": "jobs.google_drive_ingest.GoogleDriveIngestJob",
        "metrics_collection": "jobs.metrics_collection.MetricsCollectionJob",
    }

    if job_type not in job_types:
        raise ValueError(f"Unknown job type: {job_type}")

    # Import the job class dynamically
    module_path, class_name = job_types[job_type].rsplit('.', 1)
    module = __import__(module_path, fromlist=[class_name])
    job_class = getattr(module, class_name)

    # Create settings and job instance
    settings = TasksSettings()
    job_instance = job_class(settings, **job_params)
    return job_instance.execute()


class JobRegistry:
    """Registry for managing different types of scheduled jobs."""

    def __init__(self, settings: TasksSettings, scheduler_service: SchedulerService):
        """Initialize the job registry."""
        self.settings = settings
        self.scheduler_service = scheduler_service

        # Job type mapping
        self.job_types = {
            "slack_user_import": SlackUserImportJob,
            "google_drive_ingest": GoogleDriveIngestJob,
            "metrics_collection": MetricsCollectionJob,
        }

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

        # Add job to scheduler using global executor function with only serializable data
        job = self.scheduler_service.add_job(
            func=execute_job_by_type,
            trigger=trigger,
            job_id=job_id or f"{job_type}_{job_instance.get_job_id()}",
            name=f"{job_class.JOB_NAME}",
            args=[job_type, kwargs],  # Only pass serializable data
            **schedule_params,
        )

        logger.info(f"Created {job_type} job: {job.id}")
        return job

    def get_job_class(self, job_type: str) -> type | None:
        """Get job class for a given job type."""
        return self.job_types.get(job_type)
