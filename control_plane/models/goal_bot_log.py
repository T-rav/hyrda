"""Goal bot log model for storing milestone events."""

import json
from enum import Enum as PyEnum

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .base import Base


class MilestoneType(str, PyEnum):
    """Milestone type enum."""

    PLAN_CREATED = "plan_created"
    PLAN_UPDATED = "plan_updated"
    ACTION_TAKEN = "action_taken"
    PROGRESS_CHECK = "progress_check"
    GOAL_ACHIEVED = "goal_achieved"
    GOAL_BLOCKED = "goal_blocked"
    ERROR = "error"
    INFO = "info"


class GoalBotLog(Base):
    """Goal bot milestone log model."""

    __tablename__ = "goal_bot_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(
        String(36),
        ForeignKey("goal_bot_runs.run_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    milestone_type = Column(
        Enum(MilestoneType, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        index=True,
    )
    milestone_name = Column(String(200), nullable=False)
    details = Column(Text, nullable=True)  # JSON
    logged_at = Column(DateTime, nullable=False, default=func.now(), index=True)
    iteration_number = Column(Integer, nullable=False, default=0)

    # Relationships
    run = relationship("GoalBotRun", back_populates="logs")

    def __repr__(self) -> str:
        return f"<GoalBotLog(milestone_type={self.milestone_type}, name={self.milestone_name})>"

    def get_details(self) -> dict:
        """Parse and return details as dict."""
        details_value = self.details
        if not details_value:
            return {}
        try:
            return json.loads(str(details_value))
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_details(self, details: dict) -> None:
        """Set details from dict."""
        self.details = json.dumps(details) if details else None

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "run_id": self.run_id,
            "milestone_type": self.milestone_type.value
            if self.milestone_type
            else None,
            "milestone_name": self.milestone_name,
            "details": self.get_details(),
            "logged_at": self.logged_at.isoformat() if self.logged_at else None,
            "iteration_number": self.iteration_number,
        }
