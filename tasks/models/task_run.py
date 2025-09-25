"""Task run model for tracking individual task executions."""

from datetime import UTC

from sqlalchemy import JSON, Column, DateTime, Float, Integer, String, Text
from sqlalchemy.sql import func

from .base import Base


class TaskRun(Base):
    """Model for tracking individual task execution history."""

    __tablename__ = "task_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Execution details
    run_id = Column(
        String(255), nullable=False, unique=True, index=True
    )  # UUID for this specific run
    status = Column(
        String(50), nullable=False
    )  # 'running', 'success', 'failed', 'cancelled'

    # Timing information
    started_at = Column(DateTime, nullable=False, default=func.now())
    completed_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Float, nullable=True)  # Calculated duration

    # Execution context
    triggered_by = Column(
        String(100), nullable=True
    )  # 'scheduler', 'manual', 'api', 'webhook'
    triggered_by_user = Column(
        String(255), nullable=True
    )  # Slack user ID if manually triggered

    # Results and logs
    result_data = Column(JSON, nullable=True)  # Any structured output from the task
    log_output = Column(Text, nullable=True)  # Captured stdout/stderr
    error_message = Column(Text, nullable=True)  # Error details if failed
    error_traceback = Column(Text, nullable=True)  # Full stack trace if available

    # Metrics
    records_processed = Column(Integer, nullable=True)  # Number of items processed
    records_success = Column(Integer, nullable=True)  # Number of successful items
    records_failed = Column(Integer, nullable=True)  # Number of failed items

    # Metadata
    task_config_snapshot = Column(JSON, nullable=True)  # Config at time of execution
    environment_info = Column(JSON, nullable=True)  # System info, versions, etc.

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<TaskRun(id={self.id}, run_id={self.run_id}, status={self.status})>"

    @property
    def is_running(self) -> bool:
        """Check if the task is currently running."""
        return self.status == "running"

    @property
    def is_completed(self) -> bool:
        """Check if the task has completed (success or failure)."""
        return self.status in ["success", "failed", "cancelled"]

    def calculate_duration(self) -> None:
        """Calculate and set the duration if both start and end times are available."""
        if self.started_at and self.completed_at:
            # Handle timezone-aware vs timezone-naive datetime comparison
            start_time = self.started_at
            end_time = self.completed_at

            # If one is timezone-aware and the other isn't, make them consistent
            if start_time.tzinfo is not None and end_time.tzinfo is None:
                # started_at is timezone-aware, completed_at is naive - assume UTC
                end_time = end_time.replace(tzinfo=UTC)
            elif start_time.tzinfo is None and end_time.tzinfo is not None:
                # started_at is naive, completed_at is timezone-aware - assume UTC
                start_time = start_time.replace(tzinfo=UTC)

            delta = end_time - start_time
            self.duration_seconds = delta.total_seconds()
