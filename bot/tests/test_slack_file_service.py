"""
Tests for SlackFileService functionality.

Tests file downloads, metadata extraction, and processable file detection.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from slack_sdk.web.async_client import AsyncWebClient

from bot_types import SlackFileInfo
from services.slack_file_service import SlackFileService


class SlackFileInfoFactory:
    """Factory for creating SlackFileInfo test data"""

    @staticmethod
    def create_pdf_file(
        file_id: str = "F12345",
        name: str = "document.pdf",
        size: int = 1024000,
    ) -> SlackFileInfo:
        """Create PDF file info"""
        return {
            "id": file_id,
            "name": name,
            "title": "Test Document",
            "mimetype": "application/pdf",
            "filetype": "pdf",
            "size": size,
            "url_private": "https://files.slack.com/files-pri/T123/F123/document.pdf",
            "url_private_download": "https://files.slack.com/files-pri/T123/F123/download/document.pdf",
            "permalink": "https://example.slack.com/files/U123/F123/document.pdf",
            "user": "U123456",
            "timestamp": 1234567890,
            "created": 1234567890,
            "is_external": False,
        }

    @staticmethod
    def create_docx_file(
        file_id: str = "F23456",
        name: str = "report.docx",
    ) -> SlackFileInfo:
        """Create Word document file info"""
        return {
            "id": file_id,
            "name": name,
            "title": "Test Report",
            "mimetype": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "filetype": "docx",
            "size": 512000,
            "url_private": f"https://files.slack.com/files-pri/T123/{file_id}/report.docx",
            "url_private_download": f"https://files.slack.com/files-pri/T123/{file_id}/download/report.docx",
            "permalink": f"https://example.slack.com/files/U123/{file_id}/report.docx",
            "user": "U789012",
            "timestamp": 1234567900,
            "created": 1234567900,
            "is_external": False,
        }

    @staticmethod
    def create_xlsx_file(
        file_id: str = "F34567",
        name: str = "data.xlsx",
    ) -> SlackFileInfo:
        """Create Excel file info"""
        return {
            "id": file_id,
            "name": name,
            "title": "Test Data",
            "mimetype": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "filetype": "xlsx",
            "size": 256000,
            "url_private_download": f"https://files.slack.com/files-pri/T123/{file_id}/download/data.xlsx",
            "user": "U345678",
            "created": 1234567910,
        }

    @staticmethod
    def create_pptx_file(
        file_id: str = "F45678",
        name: str = "presentation.pptx",
    ) -> SlackFileInfo:
        """Create PowerPoint file info"""
        return {
            "id": file_id,
            "name": name,
            "title": "Test Presentation",
            "mimetype": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "filetype": "pptx",
            "size": 2048000,
            "url_private_download": f"https://files.slack.com/files-pri/T123/{file_id}/download/presentation.pptx",
            "user": "U456789",
            "created": 1234567920,
        }

    @staticmethod
    def create_text_file(
        file_id: str = "F56789",
        name: str = "notes.txt",
    ) -> SlackFileInfo:
        """Create text file info"""
        return {
            "id": file_id,
            "name": name,
            "title": "Notes",
            "mimetype": "text/plain",
            "filetype": "txt",
            "size": 4096,
            "url_private_download": f"https://files.slack.com/files-pri/T123/{file_id}/download/notes.txt",
            "user": "U567890",
            "created": 1234567930,
        }

    @staticmethod
    def create_markdown_file(
        file_id: str = "F67890",
        name: str = "readme.md",
    ) -> SlackFileInfo:
        """Create markdown file info"""
        return {
            "id": file_id,
            "name": name,
            "title": "README",
            "mimetype": "text/markdown",
            "filetype": "md",
            "size": 8192,
            "url_private_download": f"https://files.slack.com/files-pri/T123/{file_id}/download/readme.md",
            "user": "U678901",
            "created": 1234567940,
        }

    @staticmethod
    def create_csv_file(
        file_id: str = "F78901",
        name: str = "data.csv",
    ) -> SlackFileInfo:
        """Create CSV file info"""
        return {
            "id": file_id,
            "name": name,
            "title": "Data CSV",
            "mimetype": "text/csv",
            "filetype": "csv",
            "size": 16384,
            "url_private_download": f"https://files.slack.com/files-pri/T123/{file_id}/download/data.csv",
            "user": "U789012",
            "created": 1234567950,
        }

    @staticmethod
    def create_image_file(
        file_id: str = "F89012",
        name: str = "screenshot.png",
    ) -> SlackFileInfo:
        """Create image file info (not processable)"""
        return {
            "id": file_id,
            "name": name,
            "title": "Screenshot",
            "mimetype": "image/png",
            "filetype": "png",
            "size": 524288,
            "url_private_download": f"https://files.slack.com/files-pri/T123/{file_id}/download/screenshot.png",
            "user": "U890123",
            "created": 1234567960,
        }

    @staticmethod
    def create_file_without_download_url(
        file_id: str = "F90123",
        name: str = "no_download.pdf",
    ) -> SlackFileInfo:
        """Create file info without download URL"""
        return {
            "id": file_id,
            "name": name,
            "title": "No Download",
            "mimetype": "application/pdf",
            "filetype": "pdf",
            "size": 1024,
            "user": "U901234",
            "created": 1234567970,
        }

    @staticmethod
    def create_minimal_file(file_id: str = "F01234") -> SlackFileInfo:
        """Create minimal file info with only required fields"""
        return {
            "id": file_id,
            "url_private_download": f"https://files.slack.com/files-pri/T123/{file_id}/download/file.bin",
        }


class SlackClientFactory:
    """Factory for creating mock Slack clients"""

    @staticmethod
    def create_client_with_token(token: str = "xoxb-test-token") -> AsyncWebClient:
        """Create mock Slack client with token"""
        client = AsyncMock(spec=AsyncWebClient)
        client.token = token
        return client

    @staticmethod
    def create_client_without_token() -> AsyncWebClient:
        """Create mock Slack client without token"""
        client = AsyncMock(spec=AsyncWebClient)
        # Client exists but token is None
        return client


# Fixtures
@pytest.fixture
def mock_slack_client() -> AsyncWebClient:
    """Fixture for mock Slack client with token"""
    return SlackClientFactory.create_client_with_token()


@pytest.fixture
def slack_file_service(mock_slack_client: AsyncWebClient) -> SlackFileService:
    """Fixture for SlackFileService instance"""
    return SlackFileService(mock_slack_client)


# Tests for __init__
class TestSlackFileServiceInit:
    """Tests for SlackFileService initialization"""

    def test_init_with_valid_client(self, mock_slack_client: AsyncWebClient) -> None:
        """Test service initialization with valid client"""
        # Arrange & Act
        service = SlackFileService(mock_slack_client)

        # Assert
        assert service.client == mock_slack_client


# Tests for download_file_content
class TestDownloadFileContent:
    """Tests for download_file_content method"""

    @pytest.mark.asyncio
    async def test_download_file_success(
        self, slack_file_service: SlackFileService
    ) -> None:
        """Test successful file download"""
        # Arrange
        file_info = SlackFileInfoFactory.create_pdf_file()
        file_content = b"PDF file content"

        # Mock aiohttp response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=file_content)
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        # Act
        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await slack_file_service.download_file_content(file_info)

        # Assert
        assert result == file_content
        mock_session.get.assert_called_once()
        call_args = mock_session.get.call_args
        assert call_args[0][0] == file_info["url_private_download"]
        assert call_args[1]["headers"]["Authorization"] == "Bearer xoxb-test-token"

    @pytest.mark.asyncio
    async def test_download_file_no_download_url(
        self, slack_file_service: SlackFileService
    ) -> None:
        """Test file download with missing download URL"""
        # Arrange
        file_info = SlackFileInfoFactory.create_file_without_download_url()

        # Act
        result = await slack_file_service.download_file_content(file_info)

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_download_file_no_token(self) -> None:
        """Test file download without bot token"""
        # Arrange
        client = SlackClientFactory.create_client_without_token()
        service = SlackFileService(client)
        file_info = SlackFileInfoFactory.create_pdf_file()

        # Act
        result = await service.download_file_content(file_info)

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_download_file_http_error(
        self, slack_file_service: SlackFileService
    ) -> None:
        """Test file download with HTTP error response"""
        # Arrange
        file_info = SlackFileInfoFactory.create_pdf_file()

        # Mock aiohttp response with error
        mock_response = AsyncMock()
        mock_response.status = 403
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        # Act
        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await slack_file_service.download_file_content(file_info)

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_download_file_network_exception(
        self, slack_file_service: SlackFileService
    ) -> None:
        """Test file download with network exception"""
        # Arrange
        file_info = SlackFileInfoFactory.create_pdf_file()

        mock_session = AsyncMock()
        mock_session.get = MagicMock(side_effect=aiohttp.ClientError("Network error"))
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        # Act
        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await slack_file_service.download_file_content(file_info)

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_download_file_generic_exception(
        self, slack_file_service: SlackFileService
    ) -> None:
        """Test file download with generic exception"""
        # Arrange
        file_info = SlackFileInfoFactory.create_pdf_file()

        # Act
        with patch(
            "aiohttp.ClientSession",
            side_effect=Exception("Unexpected error"),
        ):
            result = await slack_file_service.download_file_content(file_info)

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_download_file_different_file_types(
        self, slack_file_service: SlackFileService
    ) -> None:
        """Test downloading different file types"""
        # Arrange
        test_cases = [
            (SlackFileInfoFactory.create_docx_file(), b"Word content"),
            (SlackFileInfoFactory.create_xlsx_file(), b"Excel content"),
            (SlackFileInfoFactory.create_pptx_file(), b"PowerPoint content"),
            (SlackFileInfoFactory.create_text_file(), b"Text content"),
        ]

        for file_info, expected_content in test_cases:
            # Mock aiohttp response
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.read = AsyncMock(return_value=expected_content)
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=None)

            mock_session = AsyncMock()
            mock_session.get = MagicMock(return_value=mock_response)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)

            # Act
            with patch("aiohttp.ClientSession", return_value=mock_session):
                result = await slack_file_service.download_file_content(file_info)

            # Assert
            assert result == expected_content


# Tests for extract_file_metadata
class TestExtractFileMetadata:
    """Tests for extract_file_metadata method"""

    def test_extract_metadata_complete_file(
        self, slack_file_service: SlackFileService
    ) -> None:
        """Test extracting metadata from complete file info"""
        # Arrange
        file_info = SlackFileInfoFactory.create_pdf_file()

        # Act
        metadata = slack_file_service.extract_file_metadata(file_info)

        # Assert
        assert metadata["file_id"] == "F12345"
        assert metadata["name"] == "document.pdf"
        assert metadata["title"] == "Test Document"
        assert metadata["mimetype"] == "application/pdf"
        assert metadata["filetype"] == "pdf"
        assert metadata["size"] == 1024000
        assert metadata["uploaded_by"] == "U123456"
        assert metadata["created"] == 1234567890
        assert metadata["is_external"] is False

    def test_extract_metadata_minimal_file(
        self, slack_file_service: SlackFileService
    ) -> None:
        """Test extracting metadata from minimal file info"""
        # Arrange
        file_info = SlackFileInfoFactory.create_minimal_file()

        # Act
        metadata = slack_file_service.extract_file_metadata(file_info)

        # Assert
        assert metadata["file_id"] == "F01234"
        assert metadata["name"] is None
        assert metadata["title"] is None
        assert metadata["mimetype"] is None
        assert metadata["filetype"] is None
        assert metadata["size"] is None
        assert metadata["uploaded_by"] is None
        assert metadata["created"] is None
        assert metadata["is_external"] is False  # Default value

    def test_extract_metadata_missing_fields(
        self, slack_file_service: SlackFileService
    ) -> None:
        """Test extracting metadata with missing optional fields"""
        # Arrange
        file_info = SlackFileInfoFactory.create_file_without_download_url()

        # Act
        metadata = slack_file_service.extract_file_metadata(file_info)

        # Assert
        assert metadata["file_id"] == "F90123"
        assert metadata["name"] == "no_download.pdf"
        assert metadata["title"] == "No Download"
        assert metadata["is_external"] is False

    def test_extract_metadata_external_file(
        self, slack_file_service: SlackFileService
    ) -> None:
        """Test extracting metadata from external file"""
        # Arrange
        file_info = SlackFileInfoFactory.create_pdf_file()
        file_info["is_external"] = True

        # Act
        metadata = slack_file_service.extract_file_metadata(file_info)

        # Assert
        assert metadata["is_external"] is True

    def test_extract_metadata_different_file_types(
        self, slack_file_service: SlackFileService
    ) -> None:
        """Test extracting metadata from different file types"""
        # Arrange
        test_cases = [
            (
                SlackFileInfoFactory.create_docx_file(),
                "docx",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ),
            (
                SlackFileInfoFactory.create_xlsx_file(),
                "xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
            (
                SlackFileInfoFactory.create_pptx_file(),
                "pptx",
                "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            ),
            (SlackFileInfoFactory.create_text_file(), "txt", "text/plain"),
            (SlackFileInfoFactory.create_markdown_file(), "md", "text/markdown"),
            (SlackFileInfoFactory.create_csv_file(), "csv", "text/csv"),
        ]

        for file_info, expected_filetype, expected_mimetype in test_cases:
            # Act
            metadata = slack_file_service.extract_file_metadata(file_info)

            # Assert
            assert metadata["filetype"] == expected_filetype
            assert metadata["mimetype"] == expected_mimetype


# Tests for is_processable_file
class TestIsProcessableFile:
    """Tests for is_processable_file method"""

    def test_is_processable_pdf(self, slack_file_service: SlackFileService) -> None:
        """Test PDF files are processable"""
        # Arrange
        file_info = SlackFileInfoFactory.create_pdf_file()

        # Act
        result = slack_file_service.is_processable_file(file_info)

        # Assert
        assert result is True

    def test_is_processable_docx(self, slack_file_service: SlackFileService) -> None:
        """Test Word documents are processable"""
        # Arrange
        file_info = SlackFileInfoFactory.create_docx_file()

        # Act
        result = slack_file_service.is_processable_file(file_info)

        # Assert
        assert result is True

    def test_is_processable_xlsx(self, slack_file_service: SlackFileService) -> None:
        """Test Excel files are processable"""
        # Arrange
        file_info = SlackFileInfoFactory.create_xlsx_file()

        # Act
        result = slack_file_service.is_processable_file(file_info)

        # Assert
        assert result is True

    def test_is_processable_pptx(self, slack_file_service: SlackFileService) -> None:
        """Test PowerPoint files are processable"""
        # Arrange
        file_info = SlackFileInfoFactory.create_pptx_file()

        # Act
        result = slack_file_service.is_processable_file(file_info)

        # Assert
        assert result is True

    def test_is_processable_text(self, slack_file_service: SlackFileService) -> None:
        """Test text files are processable"""
        # Arrange
        file_info = SlackFileInfoFactory.create_text_file()

        # Act
        result = slack_file_service.is_processable_file(file_info)

        # Assert
        assert result is True

    def test_is_processable_markdown(
        self, slack_file_service: SlackFileService
    ) -> None:
        """Test markdown files are processable"""
        # Arrange
        file_info = SlackFileInfoFactory.create_markdown_file()

        # Act
        result = slack_file_service.is_processable_file(file_info)

        # Assert
        assert result is True

    def test_is_processable_csv(self, slack_file_service: SlackFileService) -> None:
        """Test CSV files are processable"""
        # Arrange
        file_info = SlackFileInfoFactory.create_csv_file()

        # Act
        result = slack_file_service.is_processable_file(file_info)

        # Assert
        assert result is True

    def test_is_not_processable_image(
        self, slack_file_service: SlackFileService
    ) -> None:
        """Test image files are not processable"""
        # Arrange
        file_info = SlackFileInfoFactory.create_image_file()

        # Act
        result = slack_file_service.is_processable_file(file_info)

        # Assert
        assert result is False

    def test_is_not_processable_unknown_type(
        self, slack_file_service: SlackFileService
    ) -> None:
        """Test unknown file types are not processable"""
        # Arrange
        file_info: SlackFileInfo = {
            "id": "F99999",
            "name": "unknown.xyz",
            "mimetype": "application/octet-stream",
            "filetype": "xyz",
        }

        # Act
        result = slack_file_service.is_processable_file(file_info)

        # Assert
        assert result is False

    def test_is_processable_missing_mimetype(
        self, slack_file_service: SlackFileService
    ) -> None:
        """Test file with missing mimetype but valid filetype"""
        # Arrange
        file_info: SlackFileInfo = {
            "id": "F88888",
            "name": "document.pdf",
            "filetype": "pdf",
        }

        # Act
        result = slack_file_service.is_processable_file(file_info)

        # Assert
        assert result is True

    def test_is_processable_missing_filetype(
        self, slack_file_service: SlackFileService
    ) -> None:
        """Test file with missing filetype but valid mimetype"""
        # Arrange
        file_info: SlackFileInfo = {
            "id": "F77777",
            "name": "document.pdf",
            "mimetype": "application/pdf",
        }

        # Act
        result = slack_file_service.is_processable_file(file_info)

        # Assert
        assert result is True

    def test_is_processable_case_insensitive(
        self, slack_file_service: SlackFileService
    ) -> None:
        """Test file type checking is case insensitive"""
        # Arrange
        file_info: SlackFileInfo = {
            "id": "F66666",
            "name": "DOCUMENT.PDF",
            "mimetype": "APPLICATION/PDF",
            "filetype": "PDF",
        }

        # Act
        result = slack_file_service.is_processable_file(file_info)

        # Assert
        assert result is True

    def test_is_processable_text_mimetype_variants(
        self, slack_file_service: SlackFileService
    ) -> None:
        """Test various text/* mimetypes are processable"""
        # Arrange
        text_mimetypes = [
            "text/plain",
            "text/markdown",
            "text/html",
            "text/csv",
            "text/xml",
        ]

        for mimetype in text_mimetypes:
            file_info: SlackFileInfo = {
                "id": f"F{mimetype.replace('/', '')}",
                "name": "file.txt",
                "mimetype": mimetype,
                "filetype": "txt",
            }

            # Act
            result = slack_file_service.is_processable_file(file_info)

            # Assert
            assert result is True, f"Failed for mimetype: {mimetype}"

    def test_is_processable_empty_file_info(
        self, slack_file_service: SlackFileService
    ) -> None:
        """Test file with empty mimetype and filetype"""
        # Arrange
        file_info: SlackFileInfo = {
            "id": "F55555",
            "name": "empty_info.bin",
        }

        # Act
        result = slack_file_service.is_processable_file(file_info)

        # Assert
        assert result is False
