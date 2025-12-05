"""Unit tests for GoogleDriveAPI service."""

from unittest.mock import MagicMock, Mock, patch

import pytest
from googleapiclient.errors import HttpError

from services.gdrive.google_drive_api import GoogleDriveAPI


@pytest.fixture
def mock_credentials():
    """Create mock Google credentials."""
    return Mock()


@pytest.fixture
def mock_service():
    """Create mock Google Drive service."""
    return Mock()


@pytest.fixture
def google_drive_api(mock_credentials):
    """Create GoogleDriveAPI instance with mocked service."""
    with patch("services.gdrive.google_drive_api.build") as mock_build:
        mock_service = Mock()
        mock_build.return_value = mock_service
        api = GoogleDriveAPI(mock_credentials)
        api.service = mock_service
        return api


class TestGetDetailedPermissions:
    """Test get_detailed_permissions() method."""

    def test_get_detailed_permissions_success(self, google_drive_api):
        """Test successful permissions retrieval using permissions().list() API."""
        # Arrange
        file_id = "test-file-id"
        expected_permissions = [
            {
                "id": "perm1",
                "type": "user",
                "role": "owner",
                "emailAddress": "owner@example.com",
            },
            {
                "id": "perm2",
                "type": "domain",
                "role": "reader",
                "domain": "example.com",
            },
        ]

        # Mock the permissions().list() API chain
        mock_permissions = Mock()
        mock_list = Mock()
        mock_execute = Mock(return_value={"permissions": expected_permissions})

        google_drive_api.service.permissions.return_value = mock_permissions
        mock_permissions.list.return_value = mock_list
        mock_list.execute.return_value = {"permissions": expected_permissions}

        # Act
        result = google_drive_api.get_detailed_permissions(file_id)

        # Assert
        assert result == expected_permissions
        google_drive_api.service.permissions().list.assert_called_once_with(
            fileId=file_id, fields="permissions(*)", supportsAllDrives=True
        )

    def test_get_detailed_permissions_empty_list(self, google_drive_api):
        """Test permissions retrieval returns empty list when no permissions."""
        # Arrange
        file_id = "test-file-id"

        # Mock the API to return empty permissions list
        mock_permissions = Mock()
        mock_list = Mock()
        mock_list.execute.return_value = {"permissions": []}

        google_drive_api.service.permissions.return_value = mock_permissions
        mock_permissions.list.return_value = mock_list

        # Act
        result = google_drive_api.get_detailed_permissions(file_id)

        # Assert
        assert result == []

    def test_get_detailed_permissions_missing_permissions_key(self, google_drive_api):
        """Test permissions retrieval when response lacks 'permissions' key."""
        # Arrange
        file_id = "test-file-id"

        # Mock the API to return response without 'permissions' key
        mock_permissions = Mock()
        mock_list = Mock()
        mock_list.execute.return_value = {}  # No permissions key

        google_drive_api.service.permissions.return_value = mock_permissions
        mock_permissions.list.return_value = mock_list

        # Act
        result = google_drive_api.get_detailed_permissions(file_id)

        # Assert
        assert result == []

    def test_get_detailed_permissions_http_error_403(self, google_drive_api):
        """Test permissions retrieval handles 403 Forbidden error."""
        # Arrange
        file_id = "test-file-id"

        # Create a mock HttpError
        mock_response = Mock()
        mock_response.status = 403
        http_error = HttpError(mock_response, b"Forbidden")

        # Mock the API to raise HttpError
        mock_permissions = Mock()
        mock_list = Mock()
        mock_list.execute.side_effect = http_error

        google_drive_api.service.permissions.return_value = mock_permissions
        mock_permissions.list.return_value = mock_list

        # Act
        result = google_drive_api.get_detailed_permissions(file_id)

        # Assert
        assert result == []  # Should return empty list on error

    def test_get_detailed_permissions_http_error_404(self, google_drive_api):
        """Test permissions retrieval handles 404 Not Found error."""
        # Arrange
        file_id = "nonexistent-file-id"

        # Create a mock HttpError
        mock_response = Mock()
        mock_response.status = 404
        http_error = HttpError(mock_response, b"Not Found")

        # Mock the API to raise HttpError
        mock_permissions = Mock()
        mock_list = Mock()
        mock_list.execute.side_effect = http_error

        google_drive_api.service.permissions.return_value = mock_permissions
        mock_permissions.list.return_value = mock_list

        # Act
        result = google_drive_api.get_detailed_permissions(file_id)

        # Assert
        assert result == []

    def test_get_detailed_permissions_uses_permissions_list_api(
        self, google_drive_api
    ):
        """
        Test that get_detailed_permissions uses permissions().list() API.

        This is the fix for the bug where files().get() doesn't return permissions
        for Shared Drive files.
        """
        # Arrange
        file_id = "shared-drive-file-id"
        mock_permissions = Mock()
        mock_list = Mock()
        mock_list.execute.return_value = {"permissions": []}

        google_drive_api.service.permissions.return_value = mock_permissions
        mock_permissions.list.return_value = mock_list

        # Act
        google_drive_api.get_detailed_permissions(file_id)

        # Assert - Verify it uses permissions().list() not files().get()
        google_drive_api.service.permissions.assert_called_once()
        mock_permissions.list.assert_called_once_with(
            fileId=file_id, fields="permissions(*)", supportsAllDrives=True
        )

    def test_get_detailed_permissions_includes_all_permission_fields(
        self, google_drive_api
    ):
        """Test that permissions().list() is called with fields='permissions(*)'."""
        # Arrange
        file_id = "test-file-id"
        mock_permissions = Mock()
        mock_list = Mock()
        mock_list.execute.return_value = {"permissions": []}

        google_drive_api.service.permissions.return_value = mock_permissions
        mock_permissions.list.return_value = mock_list

        # Act
        google_drive_api.get_detailed_permissions(file_id)

        # Assert - Verify fields parameter requests all permission fields
        mock_permissions.list.assert_called_once_with(
            fileId=file_id, fields="permissions(*)", supportsAllDrives=True
        )

    def test_get_detailed_permissions_supports_all_drives(self, google_drive_api):
        """Test that permissions().list() is called with supportsAllDrives=True."""
        # Arrange
        file_id = "shared-drive-file-id"
        mock_permissions = Mock()
        mock_list = Mock()
        mock_list.execute.return_value = {"permissions": []}

        google_drive_api.service.permissions.return_value = mock_permissions
        mock_permissions.list.return_value = mock_list

        # Act
        google_drive_api.get_detailed_permissions(file_id)

        # Assert - Verify supportsAllDrives=True for Shared Drive support
        call_kwargs = mock_permissions.list.call_args[1]
        assert call_kwargs["supportsAllDrives"] is True
