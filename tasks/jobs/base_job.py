"""Base class for all scheduled jobs."""

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from config.settings import TasksSettings

logger = logging.getLogger(__name__)


class BaseJob(ABC):
    """Base class for all scheduled jobs."""

    JOB_NAME: str = "Base Job"
    JOB_DESCRIPTION: str = "Base job class"
    REQUIRED_PARAMS: list = []
    OPTIONAL_PARAMS: list = []

    def __init__(self, settings: TasksSettings, **kwargs: Any):
        """Initialize the base job."""
        self.settings = settings
        self.params = kwargs
        self.job_id = self._generate_job_id()

    def _generate_job_id(self) -> str:
        """Generate a unique job ID."""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        return f"{self.__class__.__name__.lower()}_{timestamp}"

    def get_job_id(self) -> str:
        """Get the job ID."""
        return self.job_id

    @abstractmethod
    async def _execute_job(self) -> dict[str, Any]:
        """Execute the actual job logic. Must be implemented by subclasses."""
        ...

    async def execute(self) -> dict[str, Any]:
        """Execute the job with error handling and logging."""
        start_time = datetime.utcnow()
        logger.info(f"Starting job: {self.JOB_NAME} (ID: {self.job_id})")

        try:
            # Execute the job
            result = await self._execute_job()

            # Calculate execution time
            execution_time = (datetime.utcnow() - start_time).total_seconds()

            # Log success
            logger.info(
                f"Job completed successfully: {self.JOB_NAME} "
                f"(ID: {self.job_id}, Duration: {execution_time:.2f}s)"
            )

            # Return result with metadata
            return {
                "status": "success",
                "job_id": self.job_id,
                "job_name": self.JOB_NAME,
                "start_time": start_time.isoformat(),
                "execution_time_seconds": execution_time,
                "result": result,
            }

        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds()

            logger.error(
                f"Job failed: {self.JOB_NAME} (ID: {self.job_id}, "
                f"Duration: {execution_time:.2f}s, Error: {str(e)})"
            )

            return {
                "status": "error",
                "job_id": self.job_id,
                "job_name": self.JOB_NAME,
                "start_time": start_time.isoformat(),
                "execution_time_seconds": execution_time,
                "error": str(e),
            }

    def validate_params(self) -> bool:
        """Validate required parameters are present."""
        for param in self.REQUIRED_PARAMS:
            if param not in self.params:
                raise ValueError(f"Required parameter missing: {param}")
        return True
