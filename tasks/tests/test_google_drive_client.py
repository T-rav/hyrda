"""
Comprehensive tests for GoogleDriveClient orchestrator.

Tests cover the high-level orchestration of Google Drive operations:
- Authentication flow
- Folder listing with recursive traversal
- File content download and processing
- Metadata enrichment integration
- Error handling and edge cases
- Client status reporting
"""

from unittest.mock import Mock, patch

import pytest

from services.gdrive.google_drive_client import GoogleDriveClient


@pytest.fixture
def mock_authenticator():
    """Create mock GoogleAuthenticator."""
    mock_auth = Mock()
    mock_auth.authenticate.return_value = Mock()  # Mock credentials
    return mock_auth


@pytest.fixture
def mock_api_service():
    """Create mock GoogleDriveAPI service."""
    return Mock()


@pytest.fixture
def mock_metadata_parser():
    """Create mock GoogleMetadataParser."""
    mock_parser = Mock()
    mock_parser.is_supported_file_type.return_value = True
    mock_parser.enrich_file_metadata.side_effect = lambda item, path: {
        **item,
        "full_path": f"{path}/{item['name']}" if path else item["name"],
    }
    return mock_parser


@pytest.fixture
def mock_document_processor():
    """Create mock DocumentProcessor."""
    mock_processor = Mock()
    mock_processor.extract_text.return_value = "Extracted text content"
    return mock_processor


@pytest.fixture
def google_drive_client():
    """Create GoogleDriveClient with mocked dependencies."""
    with (
        patch("services.gdrive.google_drive_client.GoogleAuthenticator"),
        patch("services.gdrive.google_drive_client.GoogleMetadataParser"),
        patch("services.gdrive.google_drive_client.DocumentProcessor"),
    ):
        client = GoogleDriveClient()
        yield client


class TestAuthentication:
    """Test authentication orchestration."""

    def test_authenticate_success(self, google_drive_client):
        """Test successful authentication flow."""
        # Arrange
        mock_credentials = Mock()
        google_drive_client.authenticator.authenticate.return_value = mock_credentials

        # Act
        with patch(
            "services.gdrive.google_drive_client.GoogleDriveAPI"
        ) as mock_api_cls:
            result = google_drive_client.authenticate()

        # Assert
        assert result is True
        google_drive_client.authenticator.authenticate.assert_called_once()
        mock_api_cls.assert_called_once_with(mock_credentials)
        assert google_drive_client.api_service is not None

    def test_authenticate_failure_no_credentials(self, google_drive_client):
        """Test authentication failure when no credentials returned."""
        # Arrange
        google_drive_client.authenticator.authenticate.return_value = None

        # Act
        result = google_drive_client.authenticate()

        # Assert
        assert result is False
        assert google_drive_client.api_service is None

    def test_authenticate_handles_exception(self, google_drive_client):
        """Test authentication handles exceptions gracefully."""
        # Arrange
        google_drive_client.authenticator.authenticate.side_effect = Exception(
            "Auth error"
        )

        # Act
        result = google_drive_client.authenticate()

        # Assert
        assert result is False
        assert google_drive_client.api_service is None

    def test_authenticate_initializes_api_service(self, google_drive_client):
        """Test that authentication initializes API service correctly."""
        # Arrange
        mock_credentials = Mock()
        google_drive_client.authenticator.authenticate.return_value = mock_credentials

        # Act
        with patch(
            "services.gdrive.google_drive_client.GoogleDriveAPI"
        ) as mock_api_cls:
            mock_api_instance = Mock()
            mock_api_cls.return_value = mock_api_instance
            google_drive_client.authenticate()

        # Assert
        assert google_drive_client.api_service == mock_api_instance


class TestListFolderContents:
    """Test folder listing orchestration."""

    def test_list_folder_requires_authentication(self, google_drive_client):
        """Test that listing folder requires prior authentication."""
        # Arrange - not authenticated
        google_drive_client.api_service = None

        # Act & Assert
        with pytest.raises(RuntimeError, match="Not authenticated"):
            google_drive_client.list_folder_contents("folder123")

    def test_list_folder_non_recursive(self, google_drive_client):
        """Test listing folder contents non-recursively."""
        # Arrange
        folder_id = "folder123"
        google_drive_client.api_service = Mock()
        google_drive_client.api_service.get_folder_info.return_value = {
            "id": folder_id,
            "name": "Test Folder",
        }
        google_drive_client.api_service.list_files_in_folder.return_value = [
            {
                "id": "file1",
                "name": "document.pdf",
                "mimeType": "application/pdf",
            },
        ]
        google_drive_client.api_service.get_detailed_permissions.return_value = []
        google_drive_client.metadata_parser.enrich_file_metadata.side_effect = (
            lambda item, path: {**item, "full_path": f"{path}/{item['name']}"}
        )

        # Act
        result = google_drive_client.list_folder_contents(
            folder_id, recursive=False, folder_path="/Test Folder"
        )

        # Assert
        assert len(result) == 1
        assert result[0]["name"] == "document.pdf"
        google_drive_client.api_service.list_files_in_folder.assert_called_once()

    def test_list_folder_recursive_includes_subfolders(self, google_drive_client):
        """Test recursive folder listing includes subfolder contents."""
        # Arrange
        folder_id = "folder123"
        google_drive_client.api_service = Mock()
        google_drive_client.api_service.get_folder_info.return_value = {
            "id": folder_id,
            "name": "Root",
        }

        # Root folder has a subfolder
        google_drive_client.api_service.list_files_in_folder.side_effect = [
            [
                {
                    "id": "subfolder1",
                    "name": "Subfolder",
                    "mimeType": "application/vnd.google-apps.folder",
                }
            ],
            [],  # Subfolder is empty
        ]

        google_drive_client.api_service.get_detailed_permissions.return_value = []
        google_drive_client.metadata_parser.enrich_file_metadata.side_effect = (
            lambda item, path: {
                **item,
                "full_path": f"{path}/{item['name']}" if path else item["name"],
            }
        )

        # Act
        result = google_drive_client.list_folder_contents(
            folder_id, recursive=True, folder_path=""
        )

        # Assert
        assert len(result) == 1  # Only the subfolder (no files in it)
        assert result[0]["name"] == "Subfolder"
        assert (
            google_drive_client.api_service.list_files_in_folder.call_count == 2
        )  # Root + subfolder

    def test_list_folder_enriches_metadata(self, google_drive_client):
        """Test that folder listing enriches file metadata."""
        # Arrange
        folder_id = "folder123"
        google_drive_client.api_service = Mock()
        google_drive_client.api_service.get_folder_info.return_value = {"id": folder_id}
        google_drive_client.api_service.list_files_in_folder.return_value = [
            {
                "id": "file1",
                "name": "doc.pdf",
                "mimeType": "application/pdf",
            }
        ]
        google_drive_client.api_service.get_detailed_permissions.return_value = [
            {"role": "owner", "emailAddress": "owner@example.com"}
        ]

        enriched_metadata = {
            "id": "file1",
            "name": "doc.pdf",
            "mimeType": "application/pdf",
            "full_path": "/doc.pdf",
            "owner_emails": "owner@example.com",
        }
        google_drive_client.metadata_parser.enrich_file_metadata.return_value = (
            enriched_metadata
        )

        # Act
        result = google_drive_client.list_folder_contents(
            folder_id, recursive=False, folder_path=""
        )

        # Assert
        assert len(result) == 1
        google_drive_client.metadata_parser.enrich_file_metadata.assert_called_once()
        assert result[0] == enriched_metadata

    def test_list_folder_handles_empty_folder(self, google_drive_client):
        """Test listing empty folder returns empty list."""
        # Arrange
        folder_id = "empty-folder"
        google_drive_client.api_service = Mock()
        google_drive_client.api_service.get_folder_info.return_value = {"id": folder_id}
        google_drive_client.api_service.list_files_in_folder.return_value = []
        google_drive_client.api_service.debug_folder_access.return_value = {
            "folder_exists": True,
            "files_found": 0,
        }

        # Act
        result = google_drive_client.list_folder_contents(folder_id, folder_path="")

        # Assert
        assert result == []
        google_drive_client.api_service.debug_folder_access.assert_called_once_with(
            folder_id
        )

    def test_list_folder_handles_inaccessible_folder(self, google_drive_client):
        """Test listing inaccessible folder returns empty list."""
        # Arrange
        folder_id = "forbidden-folder"
        google_drive_client.api_service = Mock()
        google_drive_client.api_service.get_folder_info.return_value = None

        # Act
        result = google_drive_client.list_folder_contents(folder_id, folder_path="")

        # Assert
        assert result == []

    def test_list_folder_retrieves_detailed_permissions(self, google_drive_client):
        """Test that detailed permissions are retrieved for each item."""
        # Arrange
        folder_id = "folder123"
        google_drive_client.api_service = Mock()
        google_drive_client.api_service.get_folder_info.return_value = {"id": folder_id}
        google_drive_client.api_service.list_files_in_folder.return_value = [
            {"id": "file1", "name": "doc.pdf", "mimeType": "application/pdf"}
        ]

        detailed_perms = [
            {"role": "owner", "emailAddress": "owner@example.com"},
            {"role": "reader", "emailAddress": "reader@example.com"},
        ]
        google_drive_client.api_service.get_detailed_permissions.return_value = (
            detailed_perms
        )
        google_drive_client.metadata_parser.enrich_file_metadata.side_effect = (
            lambda item, path: item
        )

        # Act
        result = google_drive_client.list_folder_contents(
            folder_id, recursive=False, folder_path=""
        )

        # Assert
        google_drive_client.api_service.get_detailed_permissions.assert_called_once_with(
            "file1"
        )
        assert result[0]["detailed_permissions"] == detailed_perms

    def test_list_folder_continues_on_item_error(self, google_drive_client):
        """Test that folder listing continues when one item fails."""
        # Arrange
        folder_id = "folder123"
        google_drive_client.api_service = Mock()
        google_drive_client.api_service.get_folder_info.return_value = {"id": folder_id}
        google_drive_client.api_service.list_files_in_folder.return_value = [
            {"id": "file1", "name": "good.pdf", "mimeType": "application/pdf"},
            {"id": "file2", "name": "bad.pdf", "mimeType": "application/pdf"},
            {"id": "file3", "name": "another.pdf", "mimeType": "application/pdf"},
        ]

        # First and third succeed, second fails
        def mock_get_permissions(file_id):
            if file_id == "file2":
                raise Exception("Permission error")
            return []

        google_drive_client.api_service.get_detailed_permissions.side_effect = (
            mock_get_permissions
        )
        google_drive_client.metadata_parser.enrich_file_metadata.side_effect = (
            lambda item, path: item
        )

        # Act
        result = google_drive_client.list_folder_contents(
            folder_id, recursive=False, folder_path=""
        )

        # Assert - should return 2 successful items
        assert len(result) == 2
        assert result[0]["name"] == "good.pdf"
        assert result[1]["name"] == "another.pdf"


class TestProcessFolderItem:
    """Test internal folder item processing."""

    def test_process_folder_item_enriches_metadata(self, google_drive_client):
        """Test that folder items are enriched with metadata."""
        # Arrange
        google_drive_client.api_service = Mock()
        google_drive_client.api_service.get_detailed_permissions.return_value = []

        item = {
            "id": "file1",
            "name": "doc.pdf",
            "mimeType": "application/pdf",
        }

        enriched = {**item, "full_path": "/folder/doc.pdf", "folder_id": "folder123"}
        google_drive_client.metadata_parser.enrich_file_metadata.return_value = enriched

        # Act
        result = google_drive_client._process_folder_item(
            item, "folder123", "/folder", recursive=False
        )

        # Assert
        assert len(result) == 1
        assert result[0]["folder_id"] == "folder123"
        google_drive_client.metadata_parser.enrich_file_metadata.assert_called_once()

    def test_process_folder_item_recursive_subfolder(self, google_drive_client):
        """Test processing subfolder when recursive is enabled."""
        # Arrange
        google_drive_client.api_service = Mock()
        google_drive_client.api_service.get_detailed_permissions.return_value = []
        google_drive_client.api_service.get_folder_info.return_value = {
            "id": "subfolder1"
        }
        google_drive_client.api_service.list_files_in_folder.return_value = [
            {"id": "subfile1", "name": "subdoc.pdf", "mimeType": "application/pdf"}
        ]

        item = {
            "id": "subfolder1",
            "name": "Subfolder",
            "mimeType": "application/vnd.google-apps.folder",
        }

        google_drive_client.metadata_parser.enrich_file_metadata.side_effect = (
            lambda i, p: {**i, "full_path": f"{p}/{i['name']}" if p else i["name"]}
        )

        # Act
        result = google_drive_client._process_folder_item(
            item, "parent123", "/parent", recursive=True
        )

        # Assert - should include subfolder + its contents
        assert len(result) == 2  # Subfolder itself + 1 file in it
        assert result[0]["name"] == "Subfolder"
        assert result[1]["name"] == "subdoc.pdf"

    def test_process_folder_item_non_recursive_skips_subfolder(
        self, google_drive_client
    ):
        """Test that subfolders are not traversed when recursive is False."""
        # Arrange
        google_drive_client.api_service = Mock()
        google_drive_client.api_service.get_detailed_permissions.return_value = []

        item = {
            "id": "subfolder1",
            "name": "Subfolder",
            "mimeType": "application/vnd.google-apps.folder",
        }

        google_drive_client.metadata_parser.enrich_file_metadata.return_value = item

        # Act
        result = google_drive_client._process_folder_item(
            item, "parent123", "/parent", recursive=False
        )

        # Assert - only the folder item itself, no traversal
        assert len(result) == 1
        assert result[0]["name"] == "Subfolder"
        # list_folder_contents should not be called for subfolder
        if hasattr(google_drive_client, "list_folder_contents"):
            assert not google_drive_client.api_service.list_files_in_folder.called

    def test_process_folder_item_handles_subfolder_error(self, google_drive_client):
        """Test handling errors when processing subfolder."""
        # Arrange
        google_drive_client.api_service = Mock()
        google_drive_client.api_service.get_detailed_permissions.return_value = []
        google_drive_client.api_service.get_folder_info.side_effect = Exception(
            "Access denied"
        )

        item = {
            "id": "subfolder1",
            "name": "BadSubfolder",
            "mimeType": "application/vnd.google-apps.folder",
        }

        google_drive_client.metadata_parser.enrich_file_metadata.return_value = {
            **item,
            "full_path": "/BadSubfolder",
        }

        # Act
        result = google_drive_client._process_folder_item(
            item, "parent123", "", recursive=True
        )

        # Assert - should return folder item even though subfolder failed
        assert len(result) == 1
        assert result[0]["name"] == "BadSubfolder"


class TestDownloadFileContent:
    """Test file content download and processing orchestration."""

    def test_download_file_requires_authentication(self, google_drive_client):
        """Test that downloading file requires authentication."""
        # Arrange
        google_drive_client.api_service = None

        # Act & Assert
        with pytest.raises(RuntimeError, match="Not authenticated"):
            google_drive_client.download_file_content("file123", "application/pdf")

    def test_download_file_checks_supported_types(self, google_drive_client):
        """Test that unsupported file types are rejected."""
        # Arrange
        google_drive_client.api_service = Mock()
        google_drive_client.metadata_parser.is_supported_file_type.return_value = False

        # Act
        result = google_drive_client.download_file_content(
            "file123", "application/x-unknown"
        )

        # Assert
        assert result is None
        google_drive_client.metadata_parser.is_supported_file_type.assert_called_once_with(
            "application/x-unknown"
        )

    def test_download_regular_file_uses_document_processor(self, google_drive_client):
        """Test downloading regular files uses document processor."""
        # Arrange
        google_drive_client.api_service = Mock()
        google_drive_client.api_service.download_file_content.return_value = (
            b"PDF content"
        )
        google_drive_client.metadata_parser.is_supported_file_type.return_value = True
        google_drive_client.document_processor.extract_text.return_value = (
            "Extracted text"
        )

        # Act
        result = google_drive_client.download_file_content(
            "file123", "application/pdf", "test.pdf"
        )

        # Assert
        assert result == "Extracted text"
        google_drive_client.api_service.download_file_content.assert_called_once_with(
            "file123", "application/pdf"
        )
        google_drive_client.document_processor.extract_text.assert_called_once_with(
            b"PDF content", "application/pdf", "test.pdf"
        )

    def test_download_google_doc_decodes_as_text(self, google_drive_client):
        """Test downloading Google Docs decodes UTF-8 text."""
        # Arrange
        google_drive_client.api_service = Mock()
        google_drive_client.api_service.download_file_content.return_value = (
            b"Google Doc text content"
        )
        google_drive_client.metadata_parser.is_supported_file_type.return_value = True

        # Act
        result = google_drive_client.download_file_content(
            "doc123", "application/vnd.google-apps.document"
        )

        # Assert
        assert result == "Google Doc text content"

    def test_download_google_doc_handles_unicode_decode_error(
        self, google_drive_client
    ):
        """Test Google Docs fallback to latin-1 on decode error."""
        # Arrange
        google_drive_client.api_service = Mock()
        # Invalid UTF-8 but valid latin-1
        google_drive_client.api_service.download_file_content.return_value = (
            b"\xff\xfe content"
        )
        google_drive_client.metadata_parser.is_supported_file_type.return_value = True

        # Act
        result = google_drive_client.download_file_content(
            "doc123", "application/vnd.google-apps.document"
        )

        # Assert - should decode with latin-1 fallback
        assert result is not None
        assert isinstance(result, str)

    def test_download_file_handles_api_error(self, google_drive_client):
        """Test handling API errors during download."""
        # Arrange
        google_drive_client.api_service = Mock()
        google_drive_client.api_service.download_file_content.return_value = None
        google_drive_client.metadata_parser.is_supported_file_type.return_value = True

        # Act
        result = google_drive_client.download_file_content("file123", "application/pdf")

        # Assert
        assert result is None

    def test_download_file_handles_processing_error(self, google_drive_client):
        """Test handling document processing errors."""
        # Arrange
        google_drive_client.api_service = Mock()
        google_drive_client.api_service.download_file_content.return_value = b"content"
        google_drive_client.metadata_parser.is_supported_file_type.return_value = True
        google_drive_client.document_processor.extract_text.side_effect = Exception(
            "Processing error"
        )

        # Act
        result = google_drive_client.download_file_content("file123", "application/pdf")

        # Assert
        assert result is None

    def test_download_file_converts_non_bytes_to_string(self, google_drive_client):
        """Test that non-bytes content is converted to string."""
        # Arrange
        google_drive_client.api_service = Mock()
        google_drive_client.api_service.download_file_content.return_value = (
            12345  # Not bytes or string
        )
        google_drive_client.metadata_parser.is_supported_file_type.return_value = True

        # Act
        result = google_drive_client.download_file_content("file123", "text/plain")

        # Assert
        assert result == "12345"


class TestClientStatus:
    """Test client status reporting."""

    def test_get_client_status_not_authenticated(self, google_drive_client):
        """Test status when not authenticated."""
        # Arrange
        google_drive_client.api_service = None

        # Act
        status = google_drive_client.get_client_status()

        # Assert
        assert status["authenticated"] is False
        assert status["services"]["api_service"] == "not_authenticated"
        assert status["services"]["authenticator"] == "initialized"
        assert status["services"]["metadata_parser"] == "initialized"
        assert status["services"]["document_processor"] == "initialized"

    def test_get_client_status_authenticated(self, google_drive_client):
        """Test status when authenticated."""
        # Arrange
        google_drive_client.api_service = Mock()

        # Act
        status = google_drive_client.get_client_status()

        # Assert
        assert status["authenticated"] is True
        assert status["services"]["api_service"] == "initialized"

    def test_client_status_structure(self, google_drive_client):
        """Test that status has expected structure."""
        # Act
        status = google_drive_client.get_client_status()

        # Assert
        assert "authenticated" in status
        assert "services" in status
        assert isinstance(status["services"], dict)


class TestBackwardCompatibilityMethods:
    """Test backward compatibility static methods."""

    def test_format_permissions_delegates_to_parser(self):
        """Test format_permissions delegates to metadata parser."""
        # Arrange
        permissions = [
            {"role": "owner", "emailAddress": "owner@example.com"},
            {"role": "reader", "emailAddress": "reader@example.com"},
        ]

        # Act
        with patch(
            "services.gdrive.google_drive_client.GoogleMetadataParser.format_permissions"
        ) as mock_format:
            mock_format.return_value = {
                "owner": ["owner@example.com"],
                "reader": ["reader@example.com"],
            }
            result = GoogleDriveClient.format_permissions(permissions)

        # Assert
        mock_format.assert_called_once_with(permissions)
        assert "owner" in result
        assert "reader" in result

    def test_get_permissions_summary_delegates_to_parser(self):
        """Test get_permissions_summary delegates to metadata parser."""
        # Arrange
        permissions = [{"role": "owner", "emailAddress": "owner@example.com"}]

        # Act
        with patch(
            "services.gdrive.google_drive_client.GoogleMetadataParser.get_permissions_summary"
        ) as mock_summary:
            mock_summary.return_value = "owner: owner@example.com"
            result = GoogleDriveClient.get_permissions_summary(permissions)

        # Assert
        mock_summary.assert_called_once_with(permissions)
        assert result == "owner: owner@example.com"

    def test_get_owner_emails_delegates_to_parser(self):
        """Test get_owner_emails delegates to metadata parser."""
        # Arrange
        owners = [
            {"emailAddress": "owner1@example.com"},
            {"emailAddress": "owner2@example.com"},
        ]

        # Act
        with patch(
            "services.gdrive.google_drive_client.GoogleMetadataParser.get_owner_emails"
        ) as mock_emails:
            mock_emails.return_value = "owner1@example.com, owner2@example.com"
            result = GoogleDriveClient.get_owner_emails(owners)

        # Assert
        mock_emails.assert_called_once_with(owners)
        assert result == "owner1@example.com, owner2@example.com"


class TestInitialization:
    """Test GoogleDriveClient initialization."""

    def test_init_creates_all_services(self):
        """Test initialization creates all required services."""
        # Act
        with (
            patch(
                "services.gdrive.google_drive_client.GoogleAuthenticator"
            ) as mock_auth,
            patch(
                "services.gdrive.google_drive_client.GoogleMetadataParser"
            ) as mock_parser,
            patch(
                "services.gdrive.google_drive_client.DocumentProcessor"
            ) as mock_processor,
        ):
            client = GoogleDriveClient()

        # Assert
        mock_auth.assert_called_once_with(None, None)
        mock_parser.assert_called_once()
        mock_processor.assert_called_once()
        assert client.api_service is None  # Not authenticated yet

    def test_init_accepts_credential_paths(self):
        """Test initialization accepts credential file paths."""
        # Act
        with patch(
            "services.gdrive.google_drive_client.GoogleAuthenticator"
        ) as mock_auth:
            GoogleDriveClient(
                credentials_file="/path/to/creds.json",
                token_file="/path/to/token.json",
            )

        # Assert
        mock_auth.assert_called_once_with("/path/to/creds.json", "/path/to/token.json")


class TestEdgeCases:
    """Test edge cases and error scenarios."""

    def test_list_folder_with_mixed_content(self, google_drive_client):
        """Test listing folder with files, folders, and Google Apps files."""
        # Arrange
        folder_id = "mixed-folder"
        google_drive_client.api_service = Mock()
        google_drive_client.api_service.get_folder_info.return_value = {"id": folder_id}
        google_drive_client.api_service.list_files_in_folder.return_value = [
            {"id": "file1", "name": "doc.pdf", "mimeType": "application/pdf"},
            {
                "id": "folder1",
                "name": "Subfolder",
                "mimeType": "application/vnd.google-apps.folder",
            },
            {
                "id": "gdoc1",
                "name": "Google Doc",
                "mimeType": "application/vnd.google-apps.document",
            },
        ]
        google_drive_client.api_service.get_detailed_permissions.return_value = []
        google_drive_client.metadata_parser.enrich_file_metadata.side_effect = (
            lambda item, path: item
        )

        # Act
        result = google_drive_client.list_folder_contents(
            folder_id, recursive=False, folder_path=""
        )

        # Assert
        assert len(result) == 3
        mimetypes = [item["mimeType"] for item in result]
        assert "application/pdf" in mimetypes
        assert "application/vnd.google-apps.folder" in mimetypes
        assert "application/vnd.google-apps.document" in mimetypes

    def test_download_empty_file(self, google_drive_client):
        """Test downloading file with no content."""
        # Arrange
        google_drive_client.api_service = Mock()
        google_drive_client.api_service.download_file_content.return_value = b""
        google_drive_client.metadata_parser.is_supported_file_type.return_value = True
        google_drive_client.document_processor.extract_text.return_value = None

        # Act
        result = google_drive_client.download_file_content("empty-file", "text/plain")

        # Assert
        assert result is None

    def test_list_folder_adds_folder_id_to_items(self, google_drive_client):
        """Test that folder_id is added to each item during processing."""
        # Arrange
        folder_id = "parent-folder"
        google_drive_client.api_service = Mock()
        google_drive_client.api_service.get_folder_info.return_value = {"id": folder_id}
        google_drive_client.api_service.list_files_in_folder.return_value = [
            {"id": "file1", "name": "doc.pdf", "mimeType": "application/pdf"}
        ]
        google_drive_client.api_service.get_detailed_permissions.return_value = []

        # Capture the enriched item
        captured_item = {}

        def capture_item(item, path):
            captured_item.update(item)
            return item

        google_drive_client.metadata_parser.enrich_file_metadata.side_effect = (
            capture_item
        )

        # Act
        google_drive_client.list_folder_contents(
            folder_id, recursive=False, folder_path=""
        )

        # Assert
        assert captured_item.get("folder_id") == folder_id

    def test_download_file_with_google_sheets(self, google_drive_client):
        """Test downloading Google Sheets as CSV bytes."""
        # Arrange
        google_drive_client.api_service = Mock()
        google_drive_client.api_service.download_file_content.return_value = (
            b"Name,Value\nTest,123"
        )
        google_drive_client.metadata_parser.is_supported_file_type.return_value = True

        # Act
        result = google_drive_client.download_file_content(
            "sheet123", "application/vnd.google-apps.spreadsheet"
        )

        # Assert
        assert result == "Name,Value\nTest,123"

    def test_list_folder_logs_debug_info_for_empty_root(
        self, google_drive_client, caplog
    ):
        """Test that debug info is logged for empty root folders."""
        # Arrange
        import logging

        caplog.set_level(logging.INFO)

        folder_id = "empty-root"
        google_drive_client.api_service = Mock()
        google_drive_client.api_service.get_folder_info.return_value = {"id": folder_id}
        google_drive_client.api_service.list_files_in_folder.return_value = []
        google_drive_client.api_service.debug_folder_access.return_value = {
            "folder_exists": True,
            "files_found": 0,
        }

        # Act
        google_drive_client.list_folder_contents(folder_id, folder_path="")

        # Assert
        google_drive_client.api_service.debug_folder_access.assert_called_once()
        assert any("Empty folder" in record.message for record in caplog.records)
