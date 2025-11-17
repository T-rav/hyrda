"""Agent metadata model for storing agent configuration."""

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func

from .base import Base


class AgentMetadata(Base):
    """Model for storing agent configuration and metadata."""

    __tablename__ = "agent_metadata"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Agent identification
    agent_name = Column(String(50), nullable=False, unique=True, index=True)
    display_name = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)

    # Permission settings
    is_public = Column(
        Boolean, nullable=False, default=True
    )  # Public = everyone can use
    requires_admin = Column(Boolean, nullable=False, default=False)  # Admin-only access

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return (
            f"<AgentMetadata(agent_name={self.agent_name}, is_public={self.is_public})>"
        )
