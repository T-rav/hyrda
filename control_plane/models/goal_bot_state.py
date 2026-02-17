"""Goal bot state model for persistent state between runs."""

import json

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .base import Base


class GoalBotState(Base):
    """Goal bot persistent state model."""

    __tablename__ = "goal_bot_state"

    id = Column(Integer, primary_key=True, autoincrement=True)
    bot_id = Column(
        String(36),
        ForeignKey("goal_bots.bot_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    state_data = Column(Text, nullable=False)  # JSON
    state_version = Column(Integer, nullable=False, default=1)
    last_updated_at = Column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )
    last_run_id = Column(String(36), nullable=True)

    # Relationships
    bot = relationship("GoalBot", back_populates="state")

    def __repr__(self) -> str:
        return f"<GoalBotState(bot_id={self.bot_id}, version={self.state_version})>"

    def get_state(self) -> dict:
        """Parse and return state data as dict."""
        state_value = self.state_data
        if not state_value:
            return {}
        try:
            return json.loads(str(state_value))
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_state(self, state: dict) -> None:
        """Set state data from dict and increment version."""
        self.state_data = json.dumps(state) if state else "{}"
        # Increment version on each update
        current_version = self.state_version if self.state_version else 0
        self.state_version = current_version + 1

    def update_state(self, updates: dict) -> None:
        """Merge updates into existing state."""
        current = self.get_state()
        current.update(updates)
        self.set_state(current)

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "bot_id": self.bot_id,
            "state": self.get_state(),
            "state_version": self.state_version,
            "last_updated_at": (
                self.last_updated_at.isoformat() if self.last_updated_at else None
            ),
            "last_run_id": self.last_run_id,
        }
