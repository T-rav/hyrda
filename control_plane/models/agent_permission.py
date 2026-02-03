"""Agent permission model for storing user access grants."""

from sqlalchemy import Column, DateTime, Enum, Integer, String
from sqlalchemy.sql import func

from .base import Base


class AgentPermission(Base):
    __tablename__ = "agent_permissions"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Agent and user identification
    agent_name = Column(String(50), nullable=False, index=True)
    slack_user_id = Column(String(255), nullable=False, index=True)

    # Permission type
    permission_type = Column(
        Enum("allow", "deny", name="permission_type_enum"),
        nullable=False,
        default="allow",
    )

    # Audit trail
    granted_by = Column(
        String(255), nullable=True
    )  # Slack user ID who granted permission
    granted_at = Column(DateTime, nullable=False, default=func.now())
    expires_at = Column(DateTime, nullable=True)  # Optional expiration

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<AgentPermission(agent={self.agent_name}, user={self.slack_user_id}, type={self.permission_type})>"
