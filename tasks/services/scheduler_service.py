"""APScheduler service with WebUI integration."""

import logging
from typing import Any

from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.job import Job
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler
from pytz import timezone as pytz_timezone

from config.settings import TasksSettings

logger = logging.getLogger(__name__)


class SchedulerService:
    """APScheduler service with WebUI support."""

    def __init__(self, settings: TasksSettings):
        """Initialize the scheduler service."""
        self.settings = settings
        self.scheduler: BackgroundScheduler | None = None
        self._setup_scheduler()

    def _setup_scheduler(self) -> None:
        """Set up the APScheduler instance."""
        # Job stores configuration - using SQLite only
        jobstores = {
            "default": SQLAlchemyJobStore(url=self.settings.database_url),
        }

        # Executors configuration
        executors = {
            "default": ThreadPoolExecutor(
                self.settings.scheduler_executors_thread_pool_max_workers
            ),
        }

        # Job defaults
        job_defaults = {
            "coalesce": self.settings.scheduler_job_defaults_coalesce,
            "max_instances": self.settings.scheduler_job_defaults_max_instances,
        }

        # Create scheduler
        self.scheduler = BackgroundScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone=pytz_timezone(self.settings.scheduler_timezone),
        )

    def start(self) -> None:
        """Start the scheduler."""
        if self.scheduler and not self.scheduler.running:
            self.scheduler.start()
            logger.info("Scheduler started successfully")

    def shutdown(self, wait: bool = True) -> None:
        """Shutdown the scheduler."""
        if self.scheduler and self.scheduler.running:
            self.scheduler.shutdown(wait=wait)
            logger.info("Scheduler shut down")

    def add_job(
        self,
        func: Any,
        trigger: str,
        job_id: str | None = None,
        **kwargs: Any,
    ) -> Job:
        """Add a job to the scheduler."""
        if not self.scheduler or not self.scheduler.running:
            raise RuntimeError("Scheduler not initialized or not running")

        job = self.scheduler.add_job(func=func, trigger=trigger, id=job_id, **kwargs)
        logger.info(f"Added job: {job.id}")
        return job

    def remove_job(self, job_id: str) -> None:
        """Remove a job from the scheduler."""
        if not self.scheduler or not self.scheduler.running:
            raise RuntimeError("Scheduler not initialized or not running")

        self.scheduler.remove_job(job_id)
        logger.info(f"Removed job: {job_id}")

    def get_jobs(self) -> list[Job]:
        """Get all jobs from the scheduler."""
        if not self.scheduler or not self.scheduler.running:
            return []

        return self.scheduler.get_jobs()

    def get_job(self, job_id: str) -> Job | None:
        """Get a specific job by ID."""
        if not self.scheduler:
            return None

        return self.scheduler.get_job(job_id)

    def pause_job(self, job_id: str) -> None:
        """Pause a job."""
        if not self.scheduler or not self.scheduler.running:
            raise RuntimeError("Scheduler not initialized or not running")

        self.scheduler.pause_job(job_id)
        logger.info(f"Paused job: {job_id}")

    def resume_job(self, job_id: str) -> None:
        """Resume a job."""
        if not self.scheduler or not self.scheduler.running:
            raise RuntimeError("Scheduler not initialized or not running")

        self.scheduler.resume_job(job_id)
        logger.info(f"Resumed job: {job_id}")

    def modify_job(self, job_id: str, **changes: Any) -> Job:
        """Modify an existing job."""
        if not self.scheduler or not self.scheduler.running:
            raise RuntimeError("Scheduler not initialized or not running")

        job = self.scheduler.modify_job(job_id, **changes)
        logger.info(f"Modified job: {job_id}")
        return job

    def get_job_info(self, job_id: str) -> dict[str, Any] | None:
        """Get detailed job information."""
        job = self.get_job(job_id)
        if not job:
            return None

        # Simple serialization - only include basic serializable data
        safe_kwargs = {}
        safe_args = []

        # Only include simple serializable types
        if job.kwargs:
            for key, value in job.kwargs.items():
                if isinstance(value, (str, int, float, bool, list, dict, type(None))):
                    safe_kwargs[key] = value
                else:
                    safe_kwargs[key] = str(value)

        if job.args:
            for arg in job.args:
                if isinstance(arg, (str, int, float, bool, list, dict, type(None))):
                    safe_args.append(arg)
                else:
                    safe_args.append(str(arg))

        return {
            "id": job.id,
            "name": job.name,
            "func": str(job.func),
            "trigger": str(job.trigger),
            "next_run_time": job.next_run_time.isoformat()
            if job.next_run_time
            else None,
            "pending": job.pending,
            "kwargs": safe_kwargs,
            "args": safe_args,
        }

    def get_scheduler_info(self) -> dict[str, Any]:
        """Get scheduler information."""
        if not self.scheduler:
            return {"running": False, "jobs_count": 0}

        jobs = self.get_jobs()
        return {
            "running": self.scheduler.running,
            "jobs_count": len(jobs),
            "timezone": str(self.scheduler.timezone),
            "job_stores": list(self.scheduler._jobstores.keys()),
            "executors": list(self.scheduler._executors.keys()),
        }
