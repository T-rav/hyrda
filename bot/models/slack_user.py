"""Slack user model for storing user information."""

from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.sql import func

from .base import Base


class SlackUser(Base):
    """Model for storing Slack user information."""

    __tablename__ = "slack_users"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Slack user identification
    slack_user_id = Column(String(255), nullable=False, unique=True, index=True)
    email_address = Column(String(255), nullable=True, index=True)

    # Optional user metadata
    display_name = Column(String(255), nullable=True)
    real_name = Column(String(255), nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<SlackUser(id={self.id}, slack_user_id={self.slack_user_id}, email={self.email_address})>"
