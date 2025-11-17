"""User model synced from Google Workspace (source of truth)."""

from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.sql import func

from .base import Base


class User(Base):
    """User model - synced from Google Workspace."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Slack identity (used for permissions)
    slack_user_id = Column(String(255), nullable=False, unique=True, index=True)

    # Google Workspace identity (source of truth)
    google_id = Column(String(255), nullable=True, unique=True, index=True)
    email = Column(String(255), nullable=False, unique=True, index=True)

    # User profile (from Google)
    full_name = Column(String(255), nullable=False)
    given_name = Column(String(100), nullable=True)
    family_name = Column(String(100), nullable=True)

    # Status (from Google)
    is_active = Column(Boolean, nullable=False, default=True)
    is_admin = Column(Boolean, nullable=False, default=False)  # Google Workspace admin

    # Sync tracking
    last_synced_at = Column(DateTime, nullable=False, default=func.now())

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<User(email={self.email}, slack_id={self.slack_user_id})>"
