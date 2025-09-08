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
        assert client.credentials_file == "credentials.json"
        assert client.token_file == "token.json"
        assert client.service is None
        assert client.document_processor is not None

    def test_init_custom_values(self):
        """Test GoogleDriveClient initialization with custom values."""
        client = GoogleDriveClient(
            credentials_file="custom_creds.json",
            token_file="custom_token.json"
        )
        assert client.credentials_file == "custom_creds.json"
        assert client.token_file == "custom_token.json"

    @patch('services.google_drive_client.os.path.exists')
    @patch('services.google_drive_client.Credentials.from_authorized_user_file')
    def test_authenticate_existing_valid_token(self, mock_from_file, mock_exists, client):
        """Test authentication with existing valid token."""
        # Mock no environment variables
        with patch.dict('os.environ', {}, clear=True):
            mock_exists.return_value = True
            mock_creds = Mock()
            mock_creds.valid = True
            mock_from_file.return_value = mock_creds

            with patch('services.google_drive_client.build') as mock_build:
                result = client.authenticate()

                assert result is True
                mock_build.assert_called_once_with('drive', 'v3', credentials=mock_creds)

    @patch('services.google_drive_client.os.path.exists')
    def test_authenticate_no_credentials_file(self, mock_exists, client):
        """Test authentication without credentials file."""
        with patch.dict('os.environ', {}, clear=True):
            mock_exists.return_value = False

            result = client.authenticate()
            assert result is False

    @patch('services.google_drive_client.os.path.exists')
    @patch('services.google_drive_client.InstalledAppFlow.from_client_secrets_file')
    def test_authenticate_new_flow(self, mock_flow, mock_exists, client):
        """Test authentication with new OAuth flow."""
        with patch.dict('os.environ', {}, clear=True):
            mock_exists.side_effect = lambda path: "credentials.json" in path

            mock_flow_instance = Mock()
            mock_new_creds = Mock()
            mock_new_creds.valid = True
            mock_flow_instance.run_local_server.return_value = mock_new_creds
            mock_flow.return_value = mock_flow_instance

            with patch('services.google_drive_client.build') as mock_build, \
                 patch('builtins.open', create=True):

                result = client.authenticate()

                assert result is True
                mock_flow.assert_called_once()

    def test_list_folder_contents_not_authenticated(self, client):
        """Test list_folder_contents without authentication."""
        with pytest.raises(RuntimeError, match="Not authenticated"):
            client.list_folder_contents("folder_id")

    def test_list_folder_contents_success(self, client):
        """Test successful folder content listing."""
        client.service = Mock()

        # Mock API response
        mock_response = {
            'files': [
                {
                    'id': 'file1',
                    'name': 'document.pdf',
                    'mimeType': 'application/pdf',
                    'size': '1024',
                    'modifiedTime': '2023-01-01T00:00:00.000Z',
                    'createdTime': '2023-01-01T00:00:00.000Z',
                    'webViewLink': 'https://drive.google.com/file/d/file1/view',
                    'owners': [{'emailAddress': 'owner@example.com', 'displayName': 'Owner'}],
                    'parents': ['folder_id']
                }
            ]
        }

        # Mock the complex query logic - need to handle both broad and specific queries
        client.service.files().list().execute.return_value = mock_response

        # Mock permissions request
        client.service.files().get().execute.return_value = {'permissions': []}

        files = client.list_folder_contents("folder_id")

        assert len(files) == 1
        assert files[0]['id'] == 'file1'
        assert files[0]['name'] == 'document.pdf'

    def test_download_file_content_not_authenticated(self, client):
        """Test download_file_content without authentication."""
        with pytest.raises(RuntimeError, match="Not authenticated"):
            client.download_file_content("file_id", "application/pdf")

    def test_download_file_content_pdf(self, client):
        """Test downloading PDF file content."""
        client.service = Mock()
        client.document_processor = Mock()
        client.document_processor.extract_text.return_value = "Extracted PDF text"

        # Set up the mock chain properly
        mock_get_media = Mock()
        mock_get_media.execute.return_value = b"PDF content"
        client.service.files().get_media.return_value = mock_get_media

        content = client.download_file_content("file_id", "application/pdf")

        assert content == "Extracted PDF text"
        client.service.files().get_media.assert_called_once_with(fileId="file_id")
        client.document_processor.extract_text.assert_called_once_with(b"PDF content", "application/pdf")

    def test_download_file_content_google_docs(self, client):
        """Test downloading Google Docs as plain text."""
        client.service = Mock()

        # Set up the mock chain properly
        mock_export_media = Mock()
        mock_export_media.execute.return_value = b"Document content"
        client.service.files().export_media.return_value = mock_export_media

        content = client.download_file_content("file_id", "application/vnd.google-apps.document")

        assert content == "Document content"
        client.service.files().export_media.assert_called_once_with(
            fileId="file_id", mimeType="text/plain"
        )

    def test_download_file_content_google_sheets(self, client):
        """Test downloading Google Sheets as CSV."""
        client.service = Mock()

        # Set up the mock chain properly
        mock_export_media = Mock()
        mock_export_media.execute.return_value = b"CSV content"
        client.service.files().export_media.return_value = mock_export_media

        content = client.download_file_content("file_id", "application/vnd.google-apps.spreadsheet")

        assert content == "CSV content"
        client.service.files().export_media.assert_called_once_with(
            fileId="file_id", mimeType="text/csv"
        )

    def test_download_file_content_unsupported(self, client):
        """Test downloading unsupported file type."""
        client.service = Mock()

        content = client.download_file_content("file_id", "image/jpeg")

        assert content is None

    def test_format_permissions_success(self):
        """Test successful permission formatting."""
        mock_permissions = [
            {
                'type': 'user',
                'role': 'reader',
                'emailAddress': 'user@example.com',
                'displayName': 'Test User'
            },
            {
                'type': 'group',
                'role': 'writer',
                'emailAddress': 'group@example.com',
                'displayName': 'Test Group'
            },
            {
                'type': 'anyone',
                'role': 'reader'
            }
        ]

        permissions = GoogleDriveClient.format_permissions(mock_permissions)

        assert len(permissions['readers']) == 2
        assert len(permissions['writers']) == 1
        assert permissions['is_public'] is True
        assert permissions['anyone_can_read'] is True
        assert permissions['anyone_can_write'] is False

    def test_format_permissions_empty(self):
        """Test permission formatting with empty permissions."""
        permissions = GoogleDriveClient.format_permissions([])

        assert permissions['readers'] == []
        assert permissions['writers'] == []
        assert permissions['owners'] == []
        assert permissions['is_public'] is False
        assert permissions['anyone_can_read'] is False
        assert permissions['anyone_can_write'] is False

    def test_get_permissions_summary(self):
        """Test getting permissions summary."""
        mock_permissions = [
            {'type': 'anyone', 'role': 'reader'},
            {'type': 'user', 'role': 'writer'}
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
            {'emailAddress': 'owner1@example.com'},
            {'emailAddress': 'owner2@example.com'}
        ]

        emails = GoogleDriveClient.get_owner_emails(mock_owners)
        assert emails == "owner1@example.com, owner2@example.com"

    def test_get_owner_emails_empty(self):
        """Test getting owner emails with empty list."""
        emails = GoogleDriveClient.get_owner_emails([])
        assert emails == "unknown"
