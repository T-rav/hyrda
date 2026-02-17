"""Goal bot run model for tracking execution history."""

import uuid
from datetime import datetime, timezone
from enum import Enum as PyEnum

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .base import Base


class RunStatus(str, PyEnum):
    """Run status enum."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class TriggeredBy(str, PyEnum):
    """Triggered by enum."""

    SCHEDULER = "scheduler"
    MANUAL = "manual"
    API = "api"


class GoalBotRun(Base):
    """Goal bot execution run model."""

    __tablename__ = "goal_bot_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(36), nullable=False, unique=True, index=True)
    bot_id = Column(
        String(36),
        ForeignKey("goal_bots.bot_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status = Column(
        Enum(RunStatus, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=RunStatus.PENDING,
    )
    started_at = Column(DateTime, nullable=True, index=True)
    completed_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    iterations_used = Column(Integer, nullable=False, default=0)
    final_outcome = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    error_traceback = Column(Text, nullable=True)
    triggered_by = Column(
        Enum(TriggeredBy, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=TriggeredBy.SCHEDULER,
    )
    triggered_by_user = Column(String(50), nullable=True)
    created_at = Column(DateTime, nullable=False, default=func.now())

    # Relationships
    bot = relationship("GoalBot", back_populates="runs")
    logs = relationship(
        "GoalBotLog", back_populates="run", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<GoalBotRun(run_id={self.run_id}, status={self.status})>"

    @staticmethod
    def generate_run_id() -> str:
        """Generate a new UUID for run_id."""
        return str(uuid.uuid4())

    def start(self) -> None:
        """Mark run as started."""
        self.status = RunStatus.RUNNING
        self.started_at = datetime.now(timezone.utc)

    def complete(self, outcome: str | None = None) -> None:
        """Mark run as completed successfully."""
        self.status = RunStatus.COMPLETED
        self.completed_at = datetime.now(timezone.utc)
        self.final_outcome = outcome
        self._calculate_duration()

    def fail(self, error_message: str, traceback: str | None = None) -> None:
        """Mark run as failed."""
        self.status = RunStatus.FAILED
        self.completed_at = datetime.now(timezone.utc)
        self.error_message = error_message
        self.error_traceback = traceback
        self._calculate_duration()

    def cancel(self) -> None:
        """Mark run as cancelled."""
        self.status = RunStatus.CANCELLED
        self.completed_at = datetime.now(timezone.utc)
        self._calculate_duration()

    def timeout(self) -> None:
        """Mark run as timed out."""
        self.status = RunStatus.TIMEOUT
        self.completed_at = datetime.now(timezone.utc)
        self.error_message = "Run exceeded maximum runtime"
        self._calculate_duration()

    def _calculate_duration(self) -> None:
        """Calculate duration in seconds."""
        if self.started_at and self.completed_at:
            # Handle timezone-aware vs naive datetimes
            started = self.started_at
            completed = self.completed_at

            # Make both naive for comparison if one is aware
            if started.tzinfo is not None:
                started = started.replace(tzinfo=None)
            if completed.tzinfo is not None:
                completed = completed.replace(tzinfo=None)

            delta = completed - started
            self.duration_seconds = int(delta.total_seconds())

    def is_running(self) -> bool:
        """Check if run is currently running."""
        return self.status == RunStatus.RUNNING

    def is_terminal(self) -> bool:
        """Check if run is in a terminal state."""
        return self.status in (
            RunStatus.COMPLETED,
            RunStatus.FAILED,
            RunStatus.CANCELLED,
            RunStatus.TIMEOUT,
        )

    def to_dict(self, include_logs: bool = False) -> dict:
        """Convert to dictionary for API responses."""
        data = {
            "run_id": self.run_id,
            "bot_id": self.bot_id,
            "status": self.status.value if self.status else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat()
            if self.completed_at
            else None,
            "duration_seconds": self.duration_seconds,
            "iterations_used": self.iterations_used,
            "final_outcome": self.final_outcome,
            "error_message": self.error_message,
            "triggered_by": self.triggered_by.value if self.triggered_by else None,
            "triggered_by_user": self.triggered_by_user,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

        if include_logs and self.logs:
            data["logs"] = [log.to_dict() for log in self.logs]

        return data
