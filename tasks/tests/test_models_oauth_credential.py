"""Tests for OAuthCredential model (models/oauth_credential.py)."""

from datetime import datetime

from models.oauth_credential import OAuthCredential


class TestOAuthCredentialCreation:
    """Test OAuthCredential model creation."""

    def test_create_oauth_credential_minimal(self):
        """Test creating OAuth credential with required fields."""
        cred = OAuthCredential(
            credential_id="test-cred-1",
            credential_name="Test Credential",
            encrypted_token="encrypted-token-data",
        )

        assert cred.credential_id == "test-cred-1"
        assert cred.credential_name == "Test Credential"
        assert cred.encrypted_token == "encrypted-token-data"
        # Provider default is database-level (server_default), not Python-level
        assert cred.provider is None or cred.provider == "google_drive"

    def test_create_oauth_credential_with_provider(self):
        """Test creating OAuth credential with custom provider."""
        cred = OAuthCredential(
            credential_id="test-cred-2",
            credential_name="Custom Provider",
            provider="custom_service",
            encrypted_token="encrypted-data",
        )

        assert cred.provider == "custom_service"

    def test_create_oauth_credential_with_metadata(self):
        """Test creating OAuth credential with token metadata."""
        metadata = {
            "scopes": ["drive.readonly", "drive.metadata"],
            "email": "user@example.com",
            "expiry": "2024-12-31T23:59:59Z",
        }

        cred = OAuthCredential(
            credential_id="test-cred-3",
            credential_name="With Metadata",
            encrypted_token="encrypted-data",
            token_metadata=metadata,
        )

        assert cred.token_metadata == metadata
        assert cred.token_metadata["email"] == "user@example.com"

    def test_provider_can_be_explicitly_set(self):
        """Test that provider can be explicitly set."""
        cred = OAuthCredential(
            credential_id="test-cred-4",
            credential_name="Explicit Provider",
            encrypted_token="encrypted-data",
            provider="google_drive",
        )

        assert cred.provider == "google_drive"


class TestToDict:
    """Test to_dict() method."""

    def test_to_dict_basic(self):
        """Test to_dict returns correct structure."""
        cred = OAuthCredential(
            credential_id="test-cred-5",
            credential_name="Test Credential",
            encrypted_token="should-not-appear",
            provider="google_drive",
        )

        result = cred.to_dict()

        assert isinstance(result, dict)
        assert result["credential_id"] == "test-cred-5"
        assert result["credential_name"] == "Test Credential"
        assert result["provider"] == "google_drive"

    def test_to_dict_excludes_encrypted_token(self):
        """Test that to_dict does not include encrypted_token for security."""
        cred = OAuthCredential(
            credential_id="test-cred-6",
            credential_name="Secure Cred",
            encrypted_token="super-secret-encrypted-data",
        )

        result = cred.to_dict()

        assert "encrypted_token" not in result
        assert "super-secret-encrypted-data" not in str(result)

    def test_to_dict_includes_token_metadata(self):
        """Test that to_dict includes token_metadata."""
        metadata = {"scopes": ["drive"], "email": "test@example.com"}

        cred = OAuthCredential(
            credential_id="test-cred-7",
            credential_name="With Metadata",
            encrypted_token="encrypted",
            token_metadata=metadata,
        )

        result = cred.to_dict()

        assert "token_metadata" in result
        assert result["token_metadata"] == metadata

    def test_to_dict_empty_metadata(self):
        """Test to_dict with empty token_metadata."""
        cred = OAuthCredential(
            credential_id="test-cred-8",
            credential_name="Empty Metadata",
            encrypted_token="encrypted",
            token_metadata=None,
        )

        result = cred.to_dict()

        assert "token_metadata" in result
        assert result["token_metadata"] == {}

    def test_to_dict_with_timestamps(self):
        """Test to_dict includes formatted timestamps."""
        now = datetime(2024, 1, 15, 10, 30, 0)

        cred = OAuthCredential(
            credential_id="test-cred-9",
            credential_name="With Timestamps",
            encrypted_token="encrypted",
        )
        cred.created_at = now
        cred.updated_at = now

        result = cred.to_dict()

        assert "created_at" in result
        assert "updated_at" in result
        assert result["created_at"] == "2024-01-15T10:30:00"
        assert result["updated_at"] == "2024-01-15T10:30:00"

    def test_to_dict_with_last_used_at(self):
        """Test to_dict includes last_used_at when set."""
        last_used = datetime(2024, 1, 20, 15, 45, 0)

        cred = OAuthCredential(
            credential_id="test-cred-10",
            credential_name="Recently Used",
            encrypted_token="encrypted",
        )
        cred.last_used_at = last_used

        result = cred.to_dict()

        assert "last_used_at" in result
        assert result["last_used_at"] == "2024-01-20T15:45:00"

    def test_to_dict_without_last_used_at(self):
        """Test to_dict when last_used_at is None."""
        cred = OAuthCredential(
            credential_id="test-cred-11",
            credential_name="Never Used",
            encrypted_token="encrypted",
        )
        cred.last_used_at = None

        result = cred.to_dict()

        assert "last_used_at" in result
        assert result["last_used_at"] is None

    def test_to_dict_none_timestamps(self):
        """Test to_dict handles None timestamps gracefully."""
        cred = OAuthCredential(
            credential_id="test-cred-12",
            credential_name="No Timestamps",
            encrypted_token="encrypted",
        )
        cred.created_at = None
        cred.updated_at = None
        cred.last_used_at = None

        result = cred.to_dict()

        assert result["created_at"] is None
        assert result["updated_at"] is None
        assert result["last_used_at"] is None


class TestCredentialFields:
    """Test various credential field configurations."""

    def test_credential_id_max_length(self):
        """Test credential_id can be up to 191 characters."""
        long_id = "x" * 191

        cred = OAuthCredential(
            credential_id=long_id,
            credential_name="Long ID",
            encrypted_token="encrypted",
        )

        assert cred.credential_id == long_id
        assert len(cred.credential_id) == 191

    def test_credential_name_max_length(self):
        """Test credential_name can be up to 255 characters."""
        long_name = "x" * 255

        cred = OAuthCredential(
            credential_id="test-cred-13",
            credential_name=long_name,
            encrypted_token="encrypted",
        )

        assert cred.credential_name == long_name
        assert len(cred.credential_name) == 255

    def test_provider_max_length(self):
        """Test provider can be up to 50 characters."""
        long_provider = "x" * 50

        cred = OAuthCredential(
            credential_id="test-cred-14",
            credential_name="Long Provider",
            provider=long_provider,
            encrypted_token="encrypted",
        )

        assert cred.provider == long_provider
        assert len(cred.provider) == 50

    def test_encrypted_token_can_be_long(self):
        """Test encrypted_token can store large encrypted data."""
        # Encrypted tokens can be quite long
        long_token = "x" * 5000

        cred = OAuthCredential(
            credential_id="test-cred-15",
            credential_name="Long Token",
            encrypted_token=long_token,
        )

        assert cred.encrypted_token == long_token
        assert len(cred.encrypted_token) == 5000


class TestTokenMetadata:
    """Test token_metadata field handling."""

    def test_metadata_with_scopes_list(self):
        """Test metadata with list of scopes."""
        metadata = {"scopes": ["drive.readonly", "drive.file", "drive.metadata"]}

        cred = OAuthCredential(
            credential_id="test-cred-16",
            credential_name="Scoped Credential",
            encrypted_token="encrypted",
            token_metadata=metadata,
        )

        assert "scopes" in cred.token_metadata
        assert len(cred.token_metadata["scopes"]) == 3

    def test_metadata_with_nested_data(self):
        """Test metadata can contain nested structures."""
        metadata = {
            "user": {"email": "test@example.com", "name": "Test User"},
            "token_info": {"expires_in": 3600, "token_type": "Bearer"},
        }

        cred = OAuthCredential(
            credential_id="test-cred-17",
            credential_name="Nested Metadata",
            encrypted_token="encrypted",
            token_metadata=metadata,
        )

        assert cred.token_metadata["user"]["email"] == "test@example.com"
        assert cred.token_metadata["token_info"]["expires_in"] == 3600

    def test_metadata_empty_dict(self):
        """Test metadata can be empty dict."""
        cred = OAuthCredential(
            credential_id="test-cred-18",
            credential_name="Empty Dict Metadata",
            encrypted_token="encrypted",
            token_metadata={},
        )

        assert cred.token_metadata == {}

    def test_metadata_none(self):
        """Test metadata can be None."""
        cred = OAuthCredential(
            credential_id="test-cred-19",
            credential_name="None Metadata",
            encrypted_token="encrypted",
            token_metadata=None,
        )

        assert cred.token_metadata is None
