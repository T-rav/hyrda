"""Tests for Google Drive metadata parser."""

from services.gdrive.google_metadata_parser import GoogleMetadataParser


class TestGetOwnerEmails:
    """Test the get_owner_emails static method."""

    def test_empty_owners_list(self):
        """Test with empty owners list."""
        result = GoogleMetadataParser.get_owner_emails([])
        assert result == "unknown"

    def test_single_owner(self):
        """Test with single owner."""
        owners = [{"emailAddress": "owner@example.com"}]
        result = GoogleMetadataParser.get_owner_emails(owners)
        assert result == "owner@example.com"

    def test_multiple_owners(self):
        """Test with multiple owners."""
        owners = [
            {"emailAddress": "owner1@example.com"},
            {"emailAddress": "owner2@example.com"},
            {"emailAddress": "owner3@example.com"},
        ]
        result = GoogleMetadataParser.get_owner_emails(owners)
        assert result == "owner1@example.com, owner2@example.com, owner3@example.com"

    def test_owners_without_email(self):
        """Test owners without emailAddress field."""
        owners = [
            {},  # No emailAddress
            {"emailAddress": "owner@example.com"},
        ]
        result = GoogleMetadataParser.get_owner_emails(owners)
        assert result == "owner@example.com"

    def test_all_owners_without_email(self):
        """Test when all owners lack email addresses."""
        owners = [
            {},
            {"displayName": "Some Owner"},
        ]
        result = GoogleMetadataParser.get_owner_emails(owners)
        assert result == "unknown"
