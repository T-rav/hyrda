"""OAuth credential model for secure token storage."""

from sqlalchemy import JSON, Column, DateTime, Index, String, Text
from sqlalchemy.sql import func

from .base import Base


class OAuthCredential(Base):
    """
    Store OAuth credentials with encrypted tokens.

    Tokens are encrypted using Fernet symmetric encryption before storage.
    The encryption key is stored in environment variable OAUTH_ENCRYPTION_KEY.
    """

    __tablename__ = "task_credentials"

    credential_id = Column(String(191), primary_key=True)
    credential_name = Column(String(255), nullable=False)
    provider = Column(String(50), nullable=False, server_default="google_drive")
    encrypted_token = Column(Text, nullable=False)  # Fernet-encrypted JSON token
    token_metadata = Column(
        JSON, nullable=True
    )  # Non-sensitive metadata (scopes, email, etc.)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
    last_used_at = Column(DateTime, nullable=True)

    __table_args__ = (Index("idx_task_credentials_provider", "provider"),)

    def to_dict(self) -> dict:
        """Convert to dictionary (excludes encrypted_token for security)."""
        return {
            "credential_id": self.credential_id,
            "credential_name": self.credential_name,
            "provider": self.provider,
            "token_metadata": self.token_metadata or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_used_at": self.last_used_at.isoformat()
            if self.last_used_at
            else None,
        }
