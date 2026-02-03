"""Service Account model for external API integrations."""

import secrets
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func

from .base import Base


def generate_api_key() -> str:
    """Generate a secure API key with prefix for identification."""
    return f"sa_{secrets.token_urlsafe(32)}"


class ServiceAccount(Base):
    __tablename__ = "service_accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Identification
    name = Column(
        String(255), nullable=False, unique=True, index=True
    )  # e.g., "HubSpot Production"
    description = Column(Text, nullable=True)  # Purpose and use case

    # Authentication
    api_key_hash = Column(
        String(255), nullable=False, unique=True, index=True
    )  # bcrypt hash
    api_key_prefix = Column(
        String(10), nullable=False, index=True
    )  # First 8 chars for identification

    # Permissions
    scopes = Column(
        String(1000), nullable=False, default="agents:read,agents:invoke"
    )  # Comma-separated
    allowed_agents = Column(
        Text, nullable=True
    )  # JSON array of allowed agent names, NULL = all
    rate_limit = Column(Integer, nullable=False, default=100)  # Requests per hour

    # Status
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    is_revoked = Column(Boolean, nullable=False, default=False, index=True)

    # Metadata
    created_by = Column(String(255), nullable=True)  # User email who created it
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(
        DateTime(timezone=True), nullable=True, index=True
    )  # Optional expiration

    # Audit
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    updated_at = Column(
        DateTime(timezone=True), nullable=False, default=func.now(), onupdate=func.now()
    )
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    revoked_by = Column(String(255), nullable=True)
    revoke_reason = Column(Text, nullable=True)

    # Usage tracking
    total_requests = Column(Integer, nullable=False, default=0)
    last_request_ip = Column(String(45), nullable=True)  # IPv6 support

    def __repr__(self) -> str:
        status = (
            "revoked"
            if self.is_revoked
            else ("active" if self.is_active else "inactive")
        )
        return f"<ServiceAccount(name='{self.name}', status='{status}')>"

    def is_expired(self) -> bool:
        if not self.expires_at:
            return False

        now = datetime.now(timezone.utc)
        expires = self.expires_at

        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)

        return now > expires

    def can_access_agent(self, agent_name: str) -> bool:
        if not self.allowed_agents:
            return True

        import json

        try:
            allowed = json.loads(self.allowed_agents)
            return agent_name in allowed
        except (json.JSONDecodeError, TypeError):
            return False

    def has_scope(self, scope: str) -> bool:
        if not self.scopes:
            return False
        return scope in self.scopes.split(",")
