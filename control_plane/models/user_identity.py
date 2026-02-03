"""UserIdentity model for tracking multiple provider identities per user."""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .base import Base


class UserIdentity(Base):
    """Provider identity for a user.

    Allows tracking multiple identity providers (Slack, Google, etc.) for a single user.
    This enables migration scenarios where a user starts with Slack, then links Google,
    maintaining both identities.
    """

    __tablename__ = "user_identities"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Link to user
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Provider information
    provider_type = Column(
        String(50), nullable=False, index=True
    )  # 'slack', 'google', 'azure', etc.
    provider_user_id = Column(
        String(255), nullable=False, index=True
    )  # ID from provider
    provider_email = Column(
        String(255), nullable=False, index=True
    )  # Email from provider

    # Identity metadata
    is_primary = Column(
        Boolean, nullable=False, default=False
    )  # Which identity is primary
    display_name = Column(String(255), nullable=True)  # Display name from provider
    given_name = Column(String(255), nullable=True)
    family_name = Column(String(255), nullable=True)

    # Status
    is_active = Column(Boolean, nullable=False, default=True)

    # Sync tracking
    last_synced_at = Column(DateTime, nullable=False, default=func.now())
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )

    # Relationship
    user = relationship("User", back_populates="identities")

    # Composite indexes for common query patterns
    __table_args__ = (
        Index(
            "uq_user_identities_provider_user",
            "provider_type",
            "provider_user_id",
            unique=True,
        ),
        Index("ix_user_identities_provider_active", "provider_type", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<UserIdentity(provider='{self.provider_type}', email='{self.provider_email}', primary={self.is_primary})>"
