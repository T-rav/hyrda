"""Builder for OAuth credential test objects.

Phase 1 improvement: Eliminate duplication of credential mock creation
across 15+ test occurrences.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import Mock


class CredentialBuilder:
    """Fluent builder for OAuthCredential test objects.

    Replaces repeated manual credential creation with a clean, fluent API.

    Examples:
        # Active credential (default)
        cred = CredentialBuilder().build()

        # Expiring soon
        cred = CredentialBuilder().expiring_soon().build()

        # Expired credential
        cred = CredentialBuilder.dead().with_name("Old Cred").build()

        # Custom configuration
        cred = (
            CredentialBuilder()
            .with_id("prod-cred-123")
            .with_provider("slack")
            .with_user("admin@8thlight.com")
            .build()
        )
    """

    def __init__(self):
        """Initialize builder with sensible defaults."""
        self._credential_id = "test-cred"
        self._credential_name = "Test Credential"
        self._provider = "google_drive"
        self._expiry = datetime.now(UTC) + timedelta(days=7)  # Default: active
        self._user_email = "test@8thlight.com"

    def with_id(self, credential_id: str) -> "CredentialBuilder":
        """Set credential ID."""
        self._credential_id = credential_id
        return self

    def with_name(self, name: str) -> "CredentialBuilder":
        """Set credential name."""
        self._credential_name = name
        return self

    def with_provider(self, provider: str) -> "CredentialBuilder":
        """Set provider (google_drive, slack, etc.)."""
        self._provider = provider
        return self

    def expiring_soon(self) -> "CredentialBuilder":
        """Set credential expiring in 12 hours."""
        self._expiry = datetime.now(UTC) + timedelta(hours=12)
        return self

    def expired(self) -> "CredentialBuilder":
        """Set credential as expired (1 day ago)."""
        self._expiry = datetime.now(UTC) - timedelta(days=1)
        return self

    def no_expiry(self) -> "CredentialBuilder":
        """Set credential with no expiry metadata (never expires)."""
        self._expiry = None
        return self

    def with_user(self, email: str) -> "CredentialBuilder":
        """Set credential owner email."""
        self._user_email = email
        return self

    def build(self) -> Mock:
        """Build the credential mock object.

        Returns:
            Mock object with credential_id, credential_name, provider,
            user_email, token_metadata, and to_dict() method.
        """
        mock_cred = Mock()
        mock_cred.credential_id = self._credential_id
        mock_cred.credential_name = self._credential_name
        mock_cred.provider = self._provider
        mock_cred.user_email = self._user_email

        # Token metadata
        token_metadata = {}
        if self._expiry:
            token_metadata["expiry"] = self._expiry.isoformat()
        mock_cred.token_metadata = token_metadata

        # to_dict() method
        mock_cred.to_dict.return_value = {
            "credential_id": self._credential_id,
            "credential_name": self._credential_name,
            "provider": self._provider,
            "user_email": self._user_email,
            "token_metadata": token_metadata,
        }

        return mock_cred

    @classmethod
    def active(cls) -> "CredentialBuilder":
        """Quick builder for active credential (expires in 7 days).

        Usage:
            cred = CredentialBuilder.active().build()
        """
        return cls()

    @classmethod
    def expiring(cls) -> "CredentialBuilder":
        """Quick builder for expiring credential (12 hours remaining).

        Usage:
            cred = CredentialBuilder.expiring().build()
        """
        return cls().expiring_soon()

    @classmethod
    def dead(cls) -> "CredentialBuilder":
        """Quick builder for expired credential.

        Usage:
            cred = CredentialBuilder.dead().build()
        """
        return cls().expired()
