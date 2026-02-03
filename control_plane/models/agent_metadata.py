"""Agent metadata model for storing agent configuration."""

import json

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func

from .base import Base


class AgentMetadata(Base):
    __tablename__ = "agent_metadata"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Agent identification
    agent_name = Column(String(50), nullable=False, index=True)
    display_name = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)
    aliases = Column(Text, nullable=True)  # JSON array of aliases

    # Cloud mode deployment info (only used if AGENT_EXECUTION_MODE=cloud)
    langgraph_assistant_id = Column(
        String(255), nullable=True
    )  # LangGraph Cloud assistant ID
    langgraph_url = Column(String(512), nullable=True)  # LangGraph Cloud deployment URL
    endpoint_url = Column(
        String(512), nullable=True
    )  # HTTP endpoint for agent invocation (embedded or cloud)

    # Permission settings
    is_enabled = Column(
        Boolean, nullable=False, default=True
    )  # Agent is enabled (unless system agent, can be disabled)
    is_slack_visible = Column(
        Boolean, nullable=False, default=True
    )  # Agent visible in Slack (only if enabled)
    requires_admin = Column(Boolean, nullable=False, default=False)  # Admin-only access
    is_system = Column(
        Boolean, nullable=False, default=False
    )  # System agents cannot be disabled and have special access rules
    is_deleted = Column(
        Boolean, nullable=False, default=False
    )  # Soft delete - hide from active agents list
    aliases_customized = Column(
        Boolean, nullable=False, default=False
    )  # Track if admin edited aliases (preserve on agent re-registration)

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

    def get_aliases(self) -> list[str]:
        if not self.aliases:
            return []
        try:
            return json.loads(self.aliases)
        except (json.JSONDecodeError, TypeError):
            return []

    def set_aliases(self, aliases: list[str]) -> None:
        self.aliases = json.dumps(aliases) if aliases else None

    def to_dict(self) -> dict:
        return {
            "name": self.agent_name,
            "display_name": self.display_name,
            "description": self.description,
            "aliases": self.get_aliases(),
            "endpoint_url": self.endpoint_url,
            "langgraph_assistant_id": self.langgraph_assistant_id,
            "langgraph_url": self.langgraph_url,
            "is_enabled": self.is_enabled,
            "is_slack_visible": self.is_slack_visible,
            "requires_admin": self.requires_admin,
            "is_system": self.is_system,
            "is_deleted": self.is_deleted,
        }

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
