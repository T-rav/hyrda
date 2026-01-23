"""Builder for TaskRun test objects.

Phase 2 improvement: Eliminate duplication of task run mock creation
across test files.
"""

from datetime import UTC, datetime
from unittest.mock import Mock


class TaskRunBuilder:
    """Fluent builder for TaskRun test objects.

    Replaces repeated manual task run creation with a clean, fluent API.

    Examples:
        # Completed run (default)
        run = TaskRunBuilder().build()

        # Failed run
        run = TaskRunBuilder.failed("Connection timeout").build()

        # Running task
        run = TaskRunBuilder.running().with_id(5).build()

        # Custom configuration
        run = (
            TaskRunBuilder()
            .with_id(10)
            .with_type("slack_user_import")
            .with_records(100, success=95, failed=5)
            .completed()
            .build()
        )
    """

    def __init__(self):
        """Initialize builder with sensible defaults."""
        self._run_id = 1
        self._job_type = "slack_user_import"
        self._status = "completed"
        self._job_id = None
        self._task_name = None
        self._started_at = datetime.now(UTC)
        self._duration = 120
        self._records_processed = 100
        self._records_success = 95
        self._records_failed = 5
        self._error_message = None
        self._triggered_by = "auto"

    def with_id(self, run_id: int) -> "TaskRunBuilder":
        """Set run ID."""
        self._run_id = run_id
        return self

    def with_type(self, job_type: str) -> "TaskRunBuilder":
        """Set job type."""
        self._job_type = job_type
        return self

    def with_job_id(self, job_id: str) -> "TaskRunBuilder":
        """Set associated job ID."""
        self._job_id = job_id
        return self

    def with_task_name(self, task_name: str) -> "TaskRunBuilder":
        """Set task name."""
        self._task_name = task_name
        return self

    def completed(self) -> "TaskRunBuilder":
        """Mark as completed."""
        self._status = "completed"
        self._error_message = None
        return self

    def failed(self, error: str = "Test error") -> "TaskRunBuilder":
        """Mark as failed with error message."""
        self._status = "failed"
        self._error_message = error
        return self

    def running(self) -> "TaskRunBuilder":
        """Mark as currently running."""
        self._status = "running"
        return self

    def with_records(
        self, processed: int, success: int | None = None, failed: int | None = None
    ) -> "TaskRunBuilder":
        """Set record processing counts.

        Args:
            processed: Total records processed
            success: Successful records (defaults to processed)
            failed: Failed records (defaults to 0)
        """
        self._records_processed = processed
        self._records_success = success if success is not None else processed
        self._records_failed = failed if failed is not None else 0
        return self

    def with_duration(self, seconds: int) -> "TaskRunBuilder":
        """Set execution duration in seconds."""
        self._duration = seconds
        return self

    def triggered_by(self, source: str) -> "TaskRunBuilder":
        """Set trigger source (auto, manual, api, etc.)."""
        self._triggered_by = source
        return self

    def build(self) -> Mock:
        """Build the TaskRun mock object.

        Returns:
            Mock object with id, run_id, status, timestamps, and all metadata.
        """
        mock_run = Mock()
        mock_run.id = self._run_id
        mock_run.run_id = f"run-{self._run_id}"
        mock_run.status = self._status
        mock_run.started_at = self._started_at

        # Completed timestamp only if not running
        mock_run.completed_at = (
            datetime.now(UTC) if self._status in ("completed", "failed") else None
        )

        mock_run.duration_seconds = self._duration
        mock_run.triggered_by = self._triggered_by
        mock_run.triggered_by_user = None  # Default to None unless set explicitly
        mock_run.error_message = self._error_message
        mock_run.records_processed = self._records_processed
        mock_run.records_success = self._records_success
        mock_run.records_failed = self._records_failed

        # Task config snapshot
        config = {"job_type": self._job_type}
        if self._job_id:
            config["job_id"] = self._job_id
        if self._task_name:
            config["task_name"] = self._task_name
        mock_run.task_config_snapshot = config

        return mock_run

    @classmethod
    def success(cls) -> "TaskRunBuilder":
        """Quick builder for successful run.

        Usage:
            run = TaskRunBuilder.success().build()
        """
        return cls().completed()

    @classmethod
    def error(cls, message: str = "Test error") -> "TaskRunBuilder":
        """Quick builder for failed run.

        Usage:
            run = TaskRunBuilder.error("Database timeout").build()
        """
        return cls().failed(message)

    @classmethod
    def in_progress(cls) -> "TaskRunBuilder":
        """Quick builder for running task.

        Usage:
            run = TaskRunBuilder.in_progress().build()
        """
        return cls().running()
