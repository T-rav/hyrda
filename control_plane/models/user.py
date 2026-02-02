"""User model for security database - supports multiple identity providers."""

from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .base import Base


class User(Base):
    """User model supporting multiple identity providers.

    Links to slack_users table in data database via slack_user_id.
    Supports linking multiple provider identities via user_identities table.
    """

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # DEPRECATED: Legacy fields maintained for backward compatibility
    # Use user_identities table for new multi-provider architecture
    slack_user_id = Column(String(255), nullable=False, unique=True, index=True)

    # Google Workspace data (DEPRECATED - use user_identities)
    google_id = Column(String(255), nullable=True, unique=True, index=True)

    # Core user data (synced from primary provider)
    email = Column(String(255), nullable=False, unique=True, index=True)
    full_name = Column(String(255), nullable=False)
    given_name = Column(String(255), nullable=True)
    family_name = Column(String(255), nullable=True)

    # Provider tracking
    primary_provider = Column(
        String(50), nullable=False, default="slack", index=True
    )

    # User status and role
    is_active = Column(Boolean, nullable=False, default=True)
    is_admin = Column(Boolean, nullable=False, default=False)

    # Sync tracking
    last_synced_at = Column(DateTime, nullable=False, default=func.now())
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )

    # Relationships
    identities = relationship(
        "UserIdentity", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<User(email='{self.email}', primary_provider='{self.primary_provider}')>"
        )
