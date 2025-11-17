"""User model for security database - synced from Google Workspace."""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.sql import func

from .base import Base


class User(Base):
    """User model synced from Google Workspace.

    Links to slack_users table in data database via slack_user_id.
    This table is in the security database and contains Google Workspace
    user data for permission management.
    """

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Link to slack_users table in data database
    slack_user_id = Column(String(255), nullable=False, unique=True, index=True)

    # Google Workspace data
    google_id = Column(String(255), nullable=True, unique=True, index=True)
    email = Column(String(255), nullable=False, unique=True, index=True)
    full_name = Column(String(255), nullable=False)
    given_name = Column(String(255), nullable=True)
    family_name = Column(String(255), nullable=True)

    # User status and role
    is_active = Column(Boolean, nullable=False, default=True)
    is_admin = Column(Boolean, nullable=False, default=False)

    # Sync tracking
    last_synced_at = Column(DateTime, nullable=False, default=func.now())
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        """Return string representation of user."""
        return f"<User(slack_user_id='{self.slack_user_id}', email='{self.email}')>"
