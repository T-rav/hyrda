"""Scheduled task model for task management."""

import uuid

from sqlalchemy import JSON, Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .base import Base


class ScheduledTask(Base):
    """Model for tracking scheduled tasks and their execution history."""

    __tablename__ = "scheduled_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Task identification (system-generated)
    task_id = Column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
        default=lambda: str(uuid.uuid4()),
    )

    # User-provided task information
    name = Column(String(255), nullable=False)  # User-friendly task name/description
    task_type = Column(
        String(100), nullable=False
    )  # e.g., 'slack_user_import', 'google_drive_sync'

    # Task configuration
    schedule_expression = Column(
        String(255), nullable=False
    )  # Cron expression or interval
    task_config = Column(JSON, nullable=True)  # Task-specific configuration

    # Status tracking
    is_active = Column(Boolean, nullable=False, default=True)
    last_run_at = Column(DateTime, nullable=True)
    next_run_at = Column(DateTime, nullable=True)
    last_status = Column(String(50), nullable=True)  # 'success', 'failed', 'running'
    last_error = Column(Text, nullable=True)

    # Execution statistics
    total_runs = Column(Integer, nullable=False, default=0)
    successful_runs = Column(Integer, nullable=False, default=0)
    failed_runs = Column(Integer, nullable=False, default=0)

    # Metadata
    created_by = Column(
        String(255), nullable=True
    )  # Slack user ID who created the task
    description = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )

    # Relationship to task runs
    task_runs = relationship(
        "TaskRun", back_populates="scheduled_task", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<ScheduledTask(id={self.id}, name={self.name}, type={self.task_type})>"

    @property
    def latest_run(self):
        """Get the most recent task run."""
        if self.task_runs:
            return max(self.task_runs, key=lambda run: run.started_at)
        return None

    @property
    def success_rate(self) -> float:
        """Calculate success rate as a percentage."""
        if self.total_runs == 0:
            return 0.0
        return (self.successful_runs / self.total_runs) * 100
