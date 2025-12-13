"""Tests for Google Drive metadata parser."""

from services.gdrive.google_metadata_parser import GoogleMetadataParser


class TestOwnerExtraction:
    """Test owner email extraction from various sources."""

    def test_extract_owners_from_owners_field(self):
        """Test extracting owners when owners field is populated."""
        parser = GoogleMetadataParser()
        item = {
            "id": "file123",
            "name": "test.pdf",
            "owners": [
                {"emailAddress": "owner1@example.com"},
                {"emailAddress": "owner2@example.com"},
            ],
        }

        enriched = parser.enrich_file_metadata(item)

        assert "owner_emails" in enriched
        assert enriched["owner_emails"] == "owner1@example.com, owner2@example.com"

    def test_extract_owners_from_detailed_permissions_when_owners_empty(self):
        """Test extracting owners from detailed_permissions when owners field is empty."""
        parser = GoogleMetadataParser()
        item = {
            "id": "file123",
            "name": "test.pdf",
            "owners": [],  # Empty owners (typical for Shared Drives)
            "detailed_permissions": [
                {
                    "role": "owner",
                    "type": "user",
                    "emailAddress": "owner@example.com",
                },
                {
                    "role": "reader",
                    "type": "user",
                    "emailAddress": "reader@example.com",
                },
            ],
        }

        enriched = parser.enrich_file_metadata(item)

        assert "owner_emails" in enriched
        assert enriched["owner_emails"] == "owner@example.com"
        # Should also populate owners field for consistency
        assert "owners" in enriched
        assert len(enriched["owners"]) == 1
        assert enriched["owners"][0]["emailAddress"] == "owner@example.com"

    def test_extract_multiple_owners_from_permissions(self):
        """Test extracting multiple owners from detailed_permissions."""
        parser = GoogleMetadataParser()
        item = {
            "id": "file123",
            "name": "test.pdf",
            "owners": [],
            "detailed_permissions": [
                {
                    "role": "owner",
                    "type": "user",
                    "emailAddress": "owner1@example.com",
                },
                {
                    "role": "owner",
                    "type": "user",
                    "emailAddress": "owner2@example.com",
                },
                {
                    "role": "writer",
                    "type": "user",
                    "emailAddress": "writer@example.com",
                },
            ],
        }

        enriched = parser.enrich_file_metadata(item)

        assert enriched["owner_emails"] == "owner1@example.com, owner2@example.com"
        assert len(enriched["owners"]) == 2

    def test_no_owners_in_either_field(self):
        """Test when no owners exist in either field."""
        parser = GoogleMetadataParser()
        item = {
            "id": "file123",
            "name": "test.pdf",
            "owners": [],
            "detailed_permissions": [
                {
                    "role": "reader",
                    "type": "user",
                    "emailAddress": "reader@example.com",
                }
            ],
        }

        enriched = parser.enrich_file_metadata(item)

        # Should not have owner_emails if no owners found
        assert "owner_emails" not in enriched

    def test_skip_permissions_without_email(self):
        """Test that permissions without email addresses are skipped."""
        parser = GoogleMetadataParser()
        item = {
            "id": "file123",
            "name": "test.pdf",
            "owners": [],
            "detailed_permissions": [
                {
                    "role": "owner",
                    "type": "anyone",  # No email for "anyone" type
                },
                {
                    "role": "owner",
                    "type": "user",
                    "emailAddress": "owner@example.com",
                },
            ],
        }

        enriched = parser.enrich_file_metadata(item)

        # Should only extract owner with email
        assert enriched["owner_emails"] == "owner@example.com"
        assert len(enriched["owners"]) == 1


class TestPermissionsSummary:
    """Test permissions summary generation."""

    def test_no_permissions(self):
        """Test summary when no permissions exist."""
        parser = GoogleMetadataParser()
        item = {
            "id": "file123",
            "name": "test.pdf",
            "permissions": [],
        }

        enriched = parser.enrich_file_metadata(item)

        # Should not have permissions_summary if no permissions
        assert "permissions_summary" not in enriched

    def test_public_access(self):
        """Test summary for publicly accessible file."""
        parser = GoogleMetadataParser()
        permissions = [
            {"role": "reader", "type": "anyone"},
        ]

        summary = parser.get_permissions_summary(permissions)
        assert summary == "anyone"  # Returns "anyone" for public files

    def test_private_with_users(self):
        """Test summary for private file with specific users."""
        parser = GoogleMetadataParser()
        permissions = [
            {
                "role": "owner",
                "type": "user",
                "emailAddress": "owner@example.com",
            },
            {
                "role": "reader",
                "type": "user",
                "emailAddress": "reader@example.com",
            },
        ]

        summary = parser.get_permissions_summary(permissions)
        # Returns comma-separated emails, not "private_N_users"
        assert summary == "owner@example.com, reader@example.com"


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


class TestEnrichFileMetadata:
    """Test the overall metadata enrichment process."""

    def test_full_path_generation(self):
        """Test that full_path is properly generated."""
        parser = GoogleMetadataParser()
        item = {"id": "file123", "name": "document.pdf"}

        enriched = parser.enrich_file_metadata(item, folder_path="Shared Drive/Folder")

        assert enriched["full_path"] == "Shared Drive/Folder/document.pdf"
        assert enriched["folder_path"] == "Shared Drive/Folder"

    def test_full_path_no_folder(self):
        """Test full_path when no folder path provided."""
        parser = GoogleMetadataParser()
        item = {"id": "file123", "name": "document.pdf"}

        enriched = parser.enrich_file_metadata(item)

        assert enriched["full_path"] == "document.pdf"
        assert enriched["folder_path"] == ""

    def test_comprehensive_enrichment(self):
        """Test full metadata enrichment with all fields."""
        parser = GoogleMetadataParser()
        item = {
            "id": "file123",
            "name": "document.pdf",
            "owners": [],
            "permissions": [
                {
                    "role": "owner",
                    "type": "user",
                    "emailAddress": "owner@example.com",
                },
                {
                    "role": "reader",
                    "type": "user",
                    "emailAddress": "reader@example.com",
                },
            ],
            "detailed_permissions": [
                {
                    "role": "owner",
                    "type": "user",
                    "emailAddress": "owner@example.com",
                },
                {
                    "role": "reader",
                    "type": "user",
                    "emailAddress": "reader@example.com",
                },
            ],
        }

        enriched = parser.enrich_file_metadata(item, folder_path="Shared/Folder")

        # Check all enriched fields
        assert enriched["full_path"] == "Shared/Folder/document.pdf"
        assert enriched["folder_path"] == "Shared/Folder"
        assert enriched["owner_emails"] == "owner@example.com"
        # Returns comma-separated emails, not "private_N_users"
        assert (
            enriched["permissions_summary"] == "owner@example.com, reader@example.com"
        )
        assert "formatted_permissions" in enriched
        assert len(enriched["owners"]) == 1
