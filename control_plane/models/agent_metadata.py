"""Agent metadata model for storing agent configuration."""

import json

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func

from .base import Base


class AgentMetadata(Base):
    """Model for storing agent configuration and metadata."""

    __tablename__ = "agent_metadata"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Agent identification
    # Note: unique constraint only applies to non-deleted agents (see __table_args__)
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
    is_public = Column(
        Boolean, nullable=False, default=True
    )  # Public = everyone can use
    requires_admin = Column(Boolean, nullable=False, default=False)  # Admin-only access
    is_system = Column(
        Boolean, nullable=False, default=False
    )  # System agents cannot be disabled and have special access rules
    is_deleted = Column(
        Boolean, nullable=False, default=False
    )  # Soft delete - hide from active agents list

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )

    # Note: Uniqueness of agent_name among non-deleted agents is enforced
    # in the application layer (see register_agent endpoint)
    # This allows reusing agent names after soft deletion

    def __repr__(self) -> str:
        return (
            f"<AgentMetadata(agent_name={self.agent_name}, is_public={self.is_public})>"
        )

    def get_aliases(self) -> list[str]:
        """Get aliases as a list."""
        if not self.aliases:
            return []
        try:
            return json.loads(self.aliases)
        except (json.JSONDecodeError, TypeError):
            return []

    def set_aliases(self, aliases: list[str]) -> None:
        """Set aliases from a list."""
        self.aliases = json.dumps(aliases) if aliases else None

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "name": self.agent_name,
            "display_name": self.display_name,
            "description": self.description,
            "aliases": self.get_aliases(),
            "endpoint_url": self.endpoint_url,
            "langgraph_assistant_id": self.langgraph_assistant_id,
            "langgraph_url": self.langgraph_url,
            "is_public": self.is_public,
            "requires_admin": self.requires_admin,
            "is_system": self.is_system,
            "is_deleted": self.is_deleted,
        }
