"""Goal bot model for storing autonomous agent bot configuration."""

import json
import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum as PyEnum

from croniter import croniter
from sqlalchemy import Boolean, Column, DateTime, Enum, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .base import Base


class ScheduleType(str, PyEnum):
    """Schedule type enum."""

    CRON = "cron"
    INTERVAL = "interval"


class GoalBot(Base):
    """Goal bot definition model."""

    __tablename__ = "goal_bots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    bot_id = Column(String(36), nullable=False, unique=True, index=True)
    name = Column(String(100), nullable=False, index=True)
    description = Column(Text, nullable=True)
    agent_name = Column(String(50), nullable=False)
    goal_prompt = Column(Text, nullable=False)
    schedule_type = Column(
        Enum(ScheduleType, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    schedule_config = Column(Text, nullable=False)  # JSON
    max_runtime_seconds = Column(Integer, nullable=False, default=3600)
    max_iterations = Column(Integer, nullable=False, default=10)
    is_enabled = Column(Boolean, nullable=False, default=True)
    is_paused = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )
    last_run_at = Column(DateTime, nullable=True)
    next_run_at = Column(DateTime, nullable=True, index=True)
    created_by = Column(String(50), nullable=True)
    notification_channel = Column(String(100), nullable=True)
    tools_config = Column(Text, nullable=True)  # JSON array of tool names

    # Relationships
    runs = relationship(
        "GoalBotRun", back_populates="bot", cascade="all, delete-orphan"
    )
    state = relationship(
        "GoalBotState",
        back_populates="bot",
        uselist=False,
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<GoalBot(name={self.name}, is_enabled={self.is_enabled}, is_paused={self.is_paused})>"

    @staticmethod
    def generate_bot_id() -> str:
        """Generate a new UUID for bot_id."""
        return str(uuid.uuid4())

    def get_schedule_config(self) -> dict:
        """Parse and return schedule config as dict."""
        if not self.schedule_config:
            return {}
        try:
            return json.loads(self.schedule_config)
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_schedule_config(self, config: dict) -> None:
        """Set schedule config from dict."""
        self.schedule_config = json.dumps(config) if config else "{}"

    def get_tools(self) -> list[str]:
        """Get list of tool names."""
        if not self.tools_config:
            return []
        try:
            return json.loads(self.tools_config)
        except (json.JSONDecodeError, TypeError):
            return []

    def set_tools(self, tools: list[str]) -> None:
        """Set tools list."""
        self.tools_config = json.dumps(tools) if tools else None

    def calculate_next_run(self, base_time: datetime | None = None) -> datetime | None:
        """Calculate the next run time based on schedule."""
        if base_time is None:
            base_time = datetime.now(timezone.utc)

        config = self.get_schedule_config()

        if self.schedule_type == ScheduleType.CRON:
            cron_expr = config.get("cron_expression")
            if cron_expr:
                cron = croniter(cron_expr, base_time)
                return cron.get_next(datetime)
        elif self.schedule_type == ScheduleType.INTERVAL:
            interval_seconds = config.get("interval_seconds", 3600)
            return base_time + timedelta(seconds=interval_seconds)

        return None

    def is_due(self, current_time: datetime | None = None) -> bool:
        """Check if bot is due to run."""
        if not self.is_enabled or self.is_paused:
            return False
        if not self.next_run_at:
            return False
        if current_time is None:
            current_time = datetime.now(timezone.utc)
        return self.next_run_at <= current_time

    def is_active(self) -> bool:
        """Check if bot is active (enabled and not paused)."""
        return self.is_enabled and not self.is_paused

    def to_dict(self, include_runs: bool = False) -> dict:
        """Convert to dictionary for API responses."""
        data = {
            "bot_id": self.bot_id,
            "name": self.name,
            "description": self.description,
            "agent_name": self.agent_name,
            "goal_prompt": self.goal_prompt,
            "schedule_type": self.schedule_type.value if self.schedule_type else None,
            "schedule_config": self.get_schedule_config(),
            "max_runtime_seconds": self.max_runtime_seconds,
            "max_iterations": self.max_iterations,
            "is_enabled": self.is_enabled,
            "is_paused": self.is_paused,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
            "next_run_at": self.next_run_at.isoformat() if self.next_run_at else None,
            "created_by": self.created_by,
            "notification_channel": self.notification_channel,
            "tools": self.get_tools(),
        }

        if include_runs and self.runs:
            data["recent_runs"] = [run.to_dict() for run in self.runs[:5]]

        return data
