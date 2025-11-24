"""Agent usage metrics model for persistence."""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.sql import func

from models.base import Base


class AgentUsage(Base):
    """Persistent storage for agent usage metrics.

    Tracks cumulative invocation counts per agent across restarts.
    """

    __tablename__ = "agent_usage"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_name = Column(String(100), nullable=False, unique=True, index=True)

    # Cumulative counters (survive restarts)
    total_invocations = Column(Integer, nullable=False, default=0)
    successful_invocations = Column(Integer, nullable=False, default=0)
    failed_invocations = Column(Integer, nullable=False, default=0)

    # Metadata
    first_invocation = Column(DateTime, nullable=True)
    last_invocation = Column(DateTime, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self):
        return f"<AgentUsage(agent_name='{self.agent_name}', total={self.total_invocations})>"

    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage."""
        if self.total_invocations == 0:
            return 0.0
        return round((self.successful_invocations / self.total_invocations) * 100, 1)

    @property
    def error_rate(self) -> float:
        """Calculate error rate percentage."""
        if self.total_invocations == 0:
            return 0.0
        return round((self.failed_invocations / self.total_invocations) * 100, 1)

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "agent_name": self.agent_name,
            "total_invocations": self.total_invocations,
            "successful_invocations": self.successful_invocations,
            "failed_invocations": self.failed_invocations,
            "success_rate": self.success_rate,
            "error_rate": self.error_rate,
            "first_invocation": self.first_invocation.isoformat()
            if self.first_invocation
            else None,
            "last_invocation": self.last_invocation.isoformat()
            if self.last_invocation
            else None,
            "is_active": self.is_active,
        }
