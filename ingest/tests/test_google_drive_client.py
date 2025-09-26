"""
Tests for GoogleDriveClient service - Fixed version matching actual implementation.
"""

from unittest.mock import Mock, patch

import pytest

from services.google_drive_client import GoogleDriveClient


class TestGoogleDriveClient:
    """Test cases for GoogleDriveClient service."""

    @pytest.fixture
    def client(self):
        """Create GoogleDriveClient instance for testing."""
        return GoogleDriveClient()

    def test_init_default_values(self, client):
        """Test GoogleDriveClient initialization with default values."""
        assert client.authenticator is not None
        assert client.api_service is None
        assert client.document_processor is not None
        assert client.metadata_parser is not None

    def test_init_custom_values(self):
        """Test GoogleDriveClient initialization with custom values."""
        client = GoogleDriveClient(
            credentials_file="custom_creds.json", token_file="custom_token.json"
        )
        assert client.authenticator is not None
        assert client.api_service is None
        assert client.document_processor is not None

    def test_authenticate_existing_valid_token(self, client):
        """Test authentication with existing valid token."""
        # Mock the authenticator to return valid credentials
        mock_creds = Mock()
        client.authenticator.authenticate = Mock(return_value=mock_creds)

        result = client.authenticate()

        assert result is True
        assert client.api_service is not None

    def test_authenticate_no_credentials_file(self, client):
        """Test authentication without credentials file."""
        # Mock the authenticator to return None (no credentials)
        client.authenticator.authenticate = Mock(return_value=None)

        result = client.authenticate()
        assert result is False

    def test_authenticate_new_flow(self, client):
        """Test authentication with new OAuth flow."""
        # Mock the authenticator to return valid credentials
        mock_creds = Mock()
        client.authenticator.authenticate = Mock(return_value=mock_creds)

        result = client.authenticate()

        assert result is True
        assert client.api_service is not None

    def test_list_folder_contents_not_authenticated(self, client):
        """Test list_folder_contents without authentication."""
        with pytest.raises(RuntimeError, match="Not authenticated"):
            client.list_folder_contents("folder_id")

    def test_list_folder_contents_success(self, client):
        """Test successful folder content listing."""
        # Mock authentication first
        mock_creds = Mock()
        client.authenticator.authenticate = Mock(return_value=mock_creds)
        client.authenticate()  # This sets up api_service

        # Mock API response
        mock_response = {
            "files": [
                {
                    "id": "file1",
                    "name": "document.pdf",
                    "mimeType": "application/pdf",
                    "size": "1024",
                    "modifiedTime": "2023-01-01T00:00:00.000Z",
                    "createdTime": "2023-01-01T00:00:00.000Z",
                    "webViewLink": "https://drive.google.com/file/d/file1/view",
                    "owners": [
                        {"emailAddress": "owner@example.com", "displayName": "Owner"}
                    ],
                    "parents": ["folder_id"],
                }
            ]
        }

        # Mock the API service methods
        mock_api_service = Mock()
        mock_api_service.list_files_in_folder.return_value = mock_response["files"]
        mock_api_service.get_file_permissions.return_value = []
        client.api_service = mock_api_service

        files = client.list_folder_contents("folder_id")

        assert len(files) == 1
        assert files[0]["id"] == "file1"
        assert files[0]["name"] == "document.pdf"

    def test_download_file_content_not_authenticated(self, client):
        """Test download_file_content without authentication."""
        with pytest.raises(RuntimeError, match="Not authenticated"):
            client.download_file_content("file_id", "application/pdf")

    def test_download_file_content_pdf(self, client):
        """Test downloading PDF file content."""
        # Mock authentication first
        mock_creds = Mock()
        client.authenticator.authenticate = Mock(return_value=mock_creds)
        client.authenticate()  # This sets up api_service

        # Mock the API service and document processor
        mock_api_service = Mock()
        mock_api_service.download_file_content.return_value = b"PDF content"
        client.api_service = mock_api_service

        # Mock the document processor method directly
        with patch.object(client.document_processor, 'extract_text', return_value="Extracted PDF text"):
            content = client.download_file_content("file_id", "application/pdf")

            assert content == "Extracted PDF text"
            mock_api_service.download_file_content.assert_called_once_with("file_id", "application/pdf")

    def test_download_file_content_google_docs(self, client):
        """Test downloading Google Docs as plain text."""
        # Mock authentication first
        mock_creds = Mock()
        client.authenticator.authenticate = Mock(return_value=mock_creds)
        client.authenticate()  # This sets up api_service

        # Mock the API service
        mock_api_service = Mock()
        mock_api_service.download_file_content.return_value = b"Document content"
        client.api_service = mock_api_service

        content = client.download_file_content(
            "file_id", "application/vnd.google-apps.document"
        )

        assert content == "Document content"
        mock_api_service.download_file_content.assert_called_once_with(
            "file_id", "application/vnd.google-apps.document"
        )

    def test_download_file_content_google_sheets(self, client):
        """Test downloading Google Sheets as CSV."""
        # Mock authentication first
        mock_creds = Mock()
        client.authenticator.authenticate = Mock(return_value=mock_creds)
        client.authenticate()  # This sets up api_service

        # Mock the API service
        mock_api_service = Mock()
        mock_api_service.download_file_content.return_value = b"CSV content"
        client.api_service = mock_api_service

        content = client.download_file_content(
            "file_id", "application/vnd.google-apps.spreadsheet"
        )

        assert content == "CSV content"
        mock_api_service.download_file_content.assert_called_once_with(
            "file_id", "application/vnd.google-apps.spreadsheet"
        )

    def test_download_file_content_unsupported(self, client):
        """Test downloading unsupported file type."""
        # Mock authentication first
        mock_creds = Mock()
        client.authenticator.authenticate = Mock(return_value=mock_creds)
        client.authenticate()  # This sets up api_service

        # Mock the API service
        mock_api_service = Mock()
        mock_api_service.download_file.return_value = b"Binary content"
        client.api_service = mock_api_service

        content = client.download_file_content("file_id", "image/jpeg")

        assert content is None  # Unsupported file type should return None

    def test_format_permissions_success(self):
        """Test successful permission formatting."""
        mock_permissions = [
            {
                "type": "user",
                "role": "reader",
                "emailAddress": "user@example.com",
                "displayName": "Test User",
            },
            {
                "type": "group",
                "role": "writer",
                "emailAddress": "group@example.com",
                "displayName": "Test Group",
            },
            {"type": "anyone", "role": "reader"},
        ]

        permissions = GoogleDriveClient.format_permissions(mock_permissions)

        assert len(permissions["readers"]) == 2
        assert len(permissions["writers"]) == 1
        assert permissions["is_public"] is True
        assert permissions["anyone_can_read"] is True
        assert permissions["anyone_can_write"] is False

    def test_format_permissions_empty(self):
        """Test permission formatting with empty permissions."""
        permissions = GoogleDriveClient.format_permissions([])

        assert permissions["readers"] == []
        assert permissions["writers"] == []
        assert permissions["owners"] == []
        assert permissions["is_public"] is False
        assert permissions["anyone_can_read"] is False
        assert permissions["anyone_can_write"] is False

    def test_get_permissions_summary(self):
        """Test getting permissions summary."""
        mock_permissions = [
            {"type": "anyone", "role": "reader"},
            {"type": "user", "role": "writer"},
        ]

        summary = GoogleDriveClient.get_permissions_summary(mock_permissions)
        assert summary == "public_plus_1_users"

    def test_get_permissions_summary_empty(self):
        """Test getting permissions summary for empty permissions."""
        summary = GoogleDriveClient.get_permissions_summary([])
        assert summary == "no_permissions"

    def test_get_owner_emails(self):
        """Test getting owner emails."""
        mock_owners = [
            {"emailAddress": "owner1@example.com"},
            {"emailAddress": "owner2@example.com"},
        ]

        emails = GoogleDriveClient.get_owner_emails(mock_owners)
        assert emails == "owner1@example.com, owner2@example.com"

    def test_get_owner_emails_empty(self):
        """Test getting owner emails with empty list."""
        emails = GoogleDriveClient.get_owner_emails([])
        assert emails == "unknown"
