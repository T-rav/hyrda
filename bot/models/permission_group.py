"""Permission group models for group-based access control."""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from .security_base import SecurityBase


class PermissionGroup(SecurityBase):
    __tablename__ = "permission_groups"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Group identification
    group_name = Column(String(50), nullable=False, unique=True, index=True)
    display_name = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)

    # Audit trail
    created_by = Column(String(255), nullable=True)  # Slack user ID who created group
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<PermissionGroup(group_name={self.group_name})>"


class UserGroup(SecurityBase):
    __tablename__ = "user_groups"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # User and group relationship
    slack_user_id = Column(String(255), nullable=False, index=True)
    group_name = Column(
        String(50),
        ForeignKey("permission_groups.group_name"),
        nullable=False,
        index=True,
    )

    # Audit trail
    added_by = Column(
        String(255), nullable=True
    )  # Slack user ID who added user to group
    added_at = Column(DateTime, nullable=False, default=func.now())

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<UserGroup(user={self.slack_user_id}, group={self.group_name})>"


class AgentGroupPermission(SecurityBase):
    __tablename__ = "agent_group_permissions"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Agent and group relationship
    agent_name = Column(String(50), nullable=False, index=True)
    group_name = Column(
        String(50),
        ForeignKey("permission_groups.group_name"),
        nullable=False,
        index=True,
    )

    # Permission type
    permission_type = Column(
        String(10), nullable=False, default="allow"
    )  # 'allow' or 'deny'

    # Audit trail
    granted_by = Column(
        String(255), nullable=True
    )  # Slack user ID who granted permission
    granted_at = Column(DateTime, nullable=False, default=func.now())

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<AgentGroupPermission(agent={self.agent_name}, group={self.group_name}, type={self.permission_type})>"
