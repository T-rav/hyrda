"""Agent metadata model for storing agent configuration."""

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func

from .security_base import SecurityBase


class AgentMetadata(SecurityBase):
    __tablename__ = "agent_metadata"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Agent identification
    agent_name = Column(String(50), nullable=False, unique=True, index=True)
    display_name = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)

    # Permission settings
    is_enabled = Column(
        Boolean, nullable=False, default=True
    )  # Agent is enabled (can be disabled unless system agent)
    is_slack_visible = Column(
        Boolean, nullable=False, default=True
    )  # Agent visible in Slack (only if enabled)
    requires_admin = Column(Boolean, nullable=False, default=False)  # Admin-only access
    is_system = Column(
        Boolean, nullable=False, default=False
    )  # System agents cannot be disabled
    is_deleted = Column(Boolean, nullable=False, default=False)  # Soft delete flag

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return (
            f"<AgentMetadata(agent_name={self.agent_name}, is_enabled={self.is_enabled}, "
            f"is_slack_visible={self.is_slack_visible})>"
        )

    def is_available(self) -> bool:
        """Check if agent is available for use (enabled and not deleted).

        System agents are always available regardless of is_enabled flag.
        """
        if self.is_system:
            return not self.is_deleted
        return self.is_enabled and not self.is_deleted

    def is_visible_in_slack(self) -> bool:
        """Check if agent should be visible in Slack.

        Agent must be enabled, not deleted, and have is_slack_visible=True.
        """
        return self.is_available() and self.is_slack_visible
