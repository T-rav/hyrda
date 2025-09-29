import io
import os
import sys
from typing import Any
from unittest.mock import Mock, patch

import pytest

# Add the parent directory to sys.path to allow importing the module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from handlers.message_handlers import (
    OPENPYXL_AVAILABLE,
    PYMUPDF_AVAILABLE,
    PYTHON_DOCX_AVAILABLE,
    PYTHON_PPTX_AVAILABLE,
    extract_excel_text,
    extract_office_text,
    extract_pdf_text,
    extract_powerpoint_text,
    extract_word_text,
    get_user_system_prompt,
    handle_message,
    process_file_attachments,
)


# TDD Factory Patterns for Message Handler Testing
class SlackFileBuilder:
    """Builder for creating Slack file attachment objects"""

    def __init__(self):
        self._name = "test.txt"
        self._mimetype = "text/plain"
        self._size = 1000
        self._url_private = "https://test.com/file"
        self._additional_fields = {}

    def with_name(self, name: str) -> "SlackFileBuilder":
        self._name = name
        return self

    def with_mimetype(self, mimetype: str) -> "SlackFileBuilder":
        self._mimetype = mimetype
        return self

    def with_size(self, size: int) -> "SlackFileBuilder":
        self._size = size
        return self

    def with_url(self, url: str) -> "SlackFileBuilder":
        self._url_private = url
        return self

    def with_no_url(self) -> "SlackFileBuilder":
        """Remove private URL to simulate files without download access"""
        if "url_private" in self._additional_fields:
            del self._additional_fields["url_private"]
        self._url_private = None
        return self

    def with_large_size(self, size_mb: int = 200) -> "SlackFileBuilder":
        """Set file size to exceed processing limits"""
        self._size = size_mb * 1024 * 1024
        return self

    def build(self) -> dict[str, Any]:
        """Build the file attachment dictionary"""
        file_data = {
            "name": self._name,
            "mimetype": self._mimetype,
            "size": self._size,
            **self._additional_fields,
        }
        if self._url_private is not None:
            file_data["url_private"] = self._url_private
        return file_data

    @classmethod
    def pdf_file(cls, name: str = "test.pdf") -> "SlackFileBuilder":
        return cls().with_name(name).with_mimetype("application/pdf")

    @classmethod
    def word_file(cls, name: str = "test.docx") -> "SlackFileBuilder":
        return (
            cls()
            .with_name(name)
            .with_mimetype(
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
        )

    @classmethod
    def excel_file(cls, name: str = "test.xlsx") -> "SlackFileBuilder":
        return (
            cls()
            .with_name(name)
            .with_mimetype(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        )

    @classmethod
    def powerpoint_file(cls, name: str = "test.pptx") -> "SlackFileBuilder":
        return (
            cls()
            .with_name(name)
            .with_mimetype(
                "application/vnd.openxmlformats-officedocument.presentationml.presentation"
            )
        )

    @classmethod
    def text_file(
        cls, name: str = "test.txt", mimetype: str = "text/plain"
    ) -> "SlackFileBuilder":
        return cls().with_name(name).with_mimetype(mimetype)

    @classmethod
    def subtitle_file(
        cls, name: str = "captions.vtt", mimetype: str = "text/vtt"
    ) -> "SlackFileBuilder":
        return cls().with_name(name).with_mimetype(mimetype).with_size(500)

    @classmethod
    def srt_subtitle_file(cls, name: str = "subtitles.srt") -> "SlackFileBuilder":
        return (
            cls().with_name(name).with_mimetype("application/x-subrip").with_size(300)
        )

    @classmethod
    def large_file(
        cls, name: str = "huge.pdf", size_mb: int = 200
    ) -> "SlackFileBuilder":
        return cls().pdf_file(name).with_large_size(size_mb)

    @classmethod
    def file_without_url(cls, name: str = "no_url.pdf") -> "SlackFileBuilder":
        return cls().pdf_file(name).with_no_url()

    @classmethod
    def unsupported_file(cls, name: str = "test.unknown") -> "SlackFileBuilder":
        return cls().with_name(name).with_mimetype("application/unknown")


class HTTPResponseFactory:
    """Factory for creating HTTP response mocks"""

    @staticmethod
    def success_response(
        content: str = "test content", binary_content: bytes = None
    ) -> Mock:
        """Create successful HTTP response"""
        response = Mock()
        response.status_code = 200
        response.text = content
        response.content = binary_content or content.encode("utf-8")
        return response

    @staticmethod
    def error_response(status_code: int = 404) -> Mock:
        """Create error HTTP response"""
        response = Mock()
        response.status_code = status_code
        return response

    @staticmethod
    def subtitle_response(
        content: str = "00:00:01.000 --> 00:00:03.000\nHello world subtitle content",
    ) -> Mock:
        """Create response with subtitle content"""
        return HTTPResponseFactory.success_response(content)

    @staticmethod
    def pdf_response(content: bytes = b"fake pdf content") -> Mock:
        """Create response with PDF binary content"""
        response = Mock()
        response.status_code = 200
        response.content = content
        return response


class SlackServiceFactory:
    """Factory for creating Slack service mocks"""

    @staticmethod
    def create_service(bot_token: str = "test-token") -> Mock:
        """Create basic Slack service mock"""
        service = Mock()
        service.settings = Mock()
        service.settings.bot_token = bot_token
        return service


class FileProcessingTestDataFactory:
    """Factory for creating comprehensive test data sets"""

    @staticmethod
    def all_supported_file_types() -> list[tuple]:
        """Generate test data for all supported file types"""
        return [
            ("test.txt", "text/plain"),
            ("test.md", "text/markdown"),
            ("test.py", "text/x-python"),
            ("test.js", "application/javascript"),
            ("test.json", "application/json"),
            ("test.csv", "text/csv"),
            ("test.vtt", "text/vtt"),
            ("test.srt", "application/x-subrip"),
            ("subtitles.srt", "text/srt"),  # Alternative SRT MIME type
            ("test.pdf", "application/pdf"),
            (
                "test.docx",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ),
            (
                "test.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
            (
                "test.pptx",
                "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            ),
            ("test.unknown", "application/unknown"),
        ]

    @staticmethod
    def office_document_routing_test_data() -> dict[str, list[tuple]]:
        """Generate test data for office document routing"""
        return {
            "word": [
                (
                    "test.docx",
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ),
                ("test.docx", "application/wordprocessingml"),
            ],
            "excel": [
                (
                    "test.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ),
                ("test.xlsx", "application/spreadsheetml"),
            ],
            "powerpoint": [
                (
                    "test.pptx",
                    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                ),
                ("test.pptx", "application/presentationml"),
            ],
        }

    @staticmethod
    def invalid_pdf_test_cases() -> list[tuple]:
        """Generate test data for invalid PDF content scenarios"""
        return [
            (None, "none.pdf"),
            (b"", "empty.pdf"),
            (b"not a pdf", "invalid.pdf"),
        ]


class TestMessageHandlers:
    """Tests for message handler functions"""

    def test_default_system_message_exists(self):
        """Test that system prompt can be retrieved via PromptService"""
        prompt = get_user_system_prompt()
        assert prompt is not None
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        assert "Insight Mesh" in prompt

    def test_get_user_system_prompt(self):
        """Test get_user_system_prompt function"""
        prompt = get_user_system_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_handle_message_function_exists(self):
        """Test that handle_message function exists and is callable"""
        assert callable(handle_message)
        assert handle_message.__name__ == "handle_message"


class TestDocumentProcessingAvailability:
    """Tests for document processing library availability flags"""

    def test_library_availability_flags_exist(self):
        """Test that all library availability flags are defined"""
        assert isinstance(PYMUPDF_AVAILABLE, bool)
        assert isinstance(PYTHON_DOCX_AVAILABLE, bool)
        assert isinstance(OPENPYXL_AVAILABLE, bool)
        assert isinstance(PYTHON_PPTX_AVAILABLE, bool)


class TestPDFProcessing:
    """Tests for PDF text extraction functionality"""

    @pytest.mark.asyncio
    async def test_extract_pdf_text_library_unavailable(self):
        """Test PDF extraction when PyMuPDF is not available"""
        with patch("handlers.message_handlers.PYMUPDF_AVAILABLE", False):
            result = await extract_pdf_text(b"test", "test.pdf")
            assert "[PDF file: test.pdf - PyMuPDF library not available]" in result

    @pytest.mark.asyncio
    async def test_extract_pdf_text_empty_content(self):
        """Test PDF extraction with empty content"""
        if not PYMUPDF_AVAILABLE:
            pytest.skip("PyMuPDF not available in test environment")

        result = await extract_pdf_text(b"", "test.pdf")
        assert "test.pdf" in result
        assert "Error extracting text" in result

    @pytest.mark.asyncio
    async def test_extract_pdf_text_invalid_pdf(self):
        """Test PDF extraction with invalid PDF content"""
        if not PYMUPDF_AVAILABLE:
            pytest.skip("PyMuPDF not available in test environment")

        result = await extract_pdf_text(b"invalid pdf content", "test.pdf")
        assert "test.pdf" in result
        assert "Error extracting text" in result or "No extractable text" in result

    @pytest.mark.asyncio
    async def test_extract_pdf_text_handles_exceptions(self):
        """Test PDF extraction handles exceptions gracefully"""
        if not PYMUPDF_AVAILABLE:
            pytest.skip("PyMuPDF not available in test environment")

        test_cases = FileProcessingTestDataFactory.invalid_pdf_test_cases()

        for content, filename in test_cases:
            if content is not None:
                result = await extract_pdf_text(content, filename)
                assert filename in result
                assert isinstance(result, str)


class TestWordProcessing:
    """Tests for Word document text extraction"""

    @pytest.mark.asyncio
    async def test_extract_word_text_library_unavailable(self):
        """Test Word extraction when python-docx is not available"""
        with patch("handlers.message_handlers.PYTHON_DOCX_AVAILABLE", False):
            stream = io.BytesIO(b"test")
            result = await extract_word_text(stream, "test.docx")
            assert (
                "[Word document: test.docx - python-docx library not available]"
                in result
            )

    @pytest.mark.asyncio
    async def test_extract_word_text_empty_stream(self):
        """Test Word extraction with empty stream"""
        if not PYTHON_DOCX_AVAILABLE:
            pytest.skip("python-docx not available in test environment")

        stream = io.BytesIO(b"")
        result = await extract_word_text(stream, "test.docx")
        assert "test.docx" in result
        assert "Error extracting text" in result

    @pytest.mark.asyncio
    async def test_extract_word_text_invalid_content(self):
        """Test Word extraction with invalid content"""
        if not PYTHON_DOCX_AVAILABLE:
            pytest.skip("python-docx not available in test environment")

        stream = io.BytesIO(b"invalid docx content")
        result = await extract_word_text(stream, "test.docx")
        assert "test.docx" in result
        assert "Error extracting text" in result


class TestExcelProcessing:
    """Tests for Excel file text extraction"""

    @pytest.mark.asyncio
    async def test_extract_excel_text_library_unavailable(self):
        """Test Excel extraction when openpyxl is not available"""
        with patch("handlers.message_handlers.OPENPYXL_AVAILABLE", False):
            stream = io.BytesIO(b"test")
            result = await extract_excel_text(stream, "test.xlsx")
            assert "[Excel file: test.xlsx - openpyxl library not available]" in result

    @pytest.mark.asyncio
    async def test_extract_excel_text_empty_stream(self):
        """Test Excel extraction with empty stream"""
        if not OPENPYXL_AVAILABLE:
            pytest.skip("openpyxl not available in test environment")

        stream = io.BytesIO(b"")
        result = await extract_excel_text(stream, "test.xlsx")
        assert "test.xlsx" in result
        assert "Error extracting text" in result

    @pytest.mark.asyncio
    async def test_extract_excel_text_invalid_content(self):
        """Test Excel extraction with invalid content"""
        if not OPENPYXL_AVAILABLE:
            pytest.skip("openpyxl not available in test environment")

        stream = io.BytesIO(b"invalid xlsx content")
        result = await extract_excel_text(stream, "test.xlsx")
        assert "test.xlsx" in result
        assert "Error extracting text" in result


class TestPowerPointProcessing:
    """Tests for PowerPoint text extraction"""

    @pytest.mark.asyncio
    async def test_extract_powerpoint_text_library_unavailable(self):
        """Test PowerPoint extraction when python-pptx is not available"""
        with patch("handlers.message_handlers.PYTHON_PPTX_AVAILABLE", False):
            stream = io.BytesIO(b"test")
            result = await extract_powerpoint_text(stream, "test.pptx")
            assert (
                "[PowerPoint file: test.pptx - python-pptx library not available]"
                in result
            )

    @pytest.mark.asyncio
    async def test_extract_powerpoint_text_empty_stream(self):
        """Test PowerPoint extraction with empty stream"""
        if not PYTHON_PPTX_AVAILABLE:
            pytest.skip("python-pptx not available in test environment")

        stream = io.BytesIO(b"")
        result = await extract_powerpoint_text(stream, "test.pptx")
        assert "test.pptx" in result
        assert "Error extracting text" in result

    @pytest.mark.asyncio
    async def test_extract_powerpoint_text_invalid_content(self):
        """Test PowerPoint extraction with invalid content"""
        if not PYTHON_PPTX_AVAILABLE:
            pytest.skip("python-pptx not available in test environment")

        stream = io.BytesIO(b"invalid pptx content")
        result = await extract_powerpoint_text(stream, "test.pptx")
        assert "test.pptx" in result
        assert "Error extracting text" in result


class TestOfficeDocumentRouting:
    """Tests for office document type routing"""

    @pytest.mark.asyncio
    async def test_extract_office_text_word_routing(self):
        """Test that Word documents are routed correctly"""
        routing_data = FileProcessingTestDataFactory.office_document_routing_test_data()

        for filename, mimetype in routing_data["word"]:
            result = await extract_office_text(b"test", filename, mimetype)
            assert filename in result

    @pytest.mark.asyncio
    async def test_extract_office_text_excel_routing(self):
        """Test that Excel files are routed correctly"""
        routing_data = FileProcessingTestDataFactory.office_document_routing_test_data()

        for filename, mimetype in routing_data["excel"]:
            result = await extract_office_text(b"test", filename, mimetype)
            assert filename in result

    @pytest.mark.asyncio
    async def test_extract_office_text_powerpoint_routing(self):
        """Test that PowerPoint files are routed correctly"""
        routing_data = FileProcessingTestDataFactory.office_document_routing_test_data()

        for filename, mimetype in routing_data["powerpoint"]:
            result = await extract_office_text(b"test", filename, mimetype)
            assert filename in result

    @pytest.mark.asyncio
    async def test_extract_office_text_unsupported_format(self):
        """Test unsupported office format handling"""
        result = await extract_office_text(
            b"test", "test.unknown", "application/unknown"
        )
        assert "Unsupported Office format" in result


class TestFileAttachmentProcessing:
    """Tests for the main file attachment processing workflow"""

    @pytest.mark.asyncio
    async def test_process_file_attachments_empty_files(self):
        """Test processing with empty file list"""
        slack_service = SlackServiceFactory.create_service()
        result = await process_file_attachments([], slack_service)
        assert result == ""

    @pytest.mark.asyncio
    async def test_process_file_attachments_no_url(self):
        """Test processing file without private URL"""
        slack_service = SlackServiceFactory.create_service()
        files = [SlackFileBuilder.file_without_url().build()]

        result = await process_file_attachments(files, slack_service)
        assert result == ""  # Should skip files without URL

    @pytest.mark.asyncio
    async def test_process_file_attachments_large_file(self):
        """Test processing file that exceeds size limit"""
        slack_service = SlackServiceFactory.create_service()
        files = [SlackFileBuilder.large_file("huge.pdf", 200).build()]

        result = await process_file_attachments(files, slack_service)
        assert result == ""  # Should skip large files

    @pytest.mark.asyncio
    async def test_process_file_attachments_download_failure(self):
        """Test processing when file download fails"""
        slack_service = SlackServiceFactory.create_service("test-token")
        files = [SlackFileBuilder.pdf_file().build()]

        with patch("requests.get") as mock_get:
            mock_get.return_value = HTTPResponseFactory.error_response(404)
            result = await process_file_attachments(files, slack_service)
            assert result == ""  # Should handle download failures gracefully

    @pytest.mark.asyncio
    async def test_process_file_attachments_subtitle_files(self):
        """Test processing of subtitle files (VTT, SRT) as text"""
        slack_service = SlackServiceFactory.create_service("test-token")
        subtitle_files = [
            SlackFileBuilder.subtitle_file("captions.vtt", "text/vtt")
            .with_url("https://test.com/captions.vtt")
            .build(),
            SlackFileBuilder.srt_subtitle_file("subtitles.srt")
            .with_url("https://test.com/subtitles.srt")
            .build(),
        ]

        with patch("requests.get") as mock_get:
            mock_get.return_value = HTTPResponseFactory.subtitle_response()
            result = await process_file_attachments(subtitle_files, slack_service)

            assert "captions.vtt" in result
            assert "subtitles.srt" in result
            assert "Hello world subtitle content" in result

    @pytest.mark.asyncio
    async def test_process_file_attachments_text_file_success(self):
        """Test successful text file processing"""
        slack_service = SlackServiceFactory.create_service("test-token")
        files = [SlackFileBuilder.text_file().with_size(100).build()]

        with patch("requests.get") as mock_get:
            mock_get.return_value = HTTPResponseFactory.success_response(
                "This is test content"
            )
            result = await process_file_attachments(files, slack_service)

            assert "test.txt" in result
            assert "This is test content" in result

    @pytest.mark.asyncio
    async def test_process_file_attachments_pdf_success(self):
        """Test PDF file processing workflow"""
        slack_service = SlackServiceFactory.create_service("test-token")
        files = [SlackFileBuilder.pdf_file().build()]

        with patch("requests.get") as mock_get:
            mock_get.return_value = HTTPResponseFactory.pdf_response()
            result = await process_file_attachments(files, slack_service)

            assert "test.pdf" in result
            # Should contain either extracted text or error message
            assert len(result) > 0


class TestFileProcessingErrorHandling:
    """Tests for error handling in file processing"""

    @pytest.mark.asyncio
    async def test_process_file_attachments_request_exception(self):
        """Test handling of request exceptions"""
        slack_service = SlackServiceFactory.create_service("test-token")
        files = [SlackFileBuilder.pdf_file().build()]

        with patch("requests.get", side_effect=Exception("Network error")):
            result = await process_file_attachments(files, slack_service)
            assert result == ""  # Should handle exceptions gracefully

    @pytest.mark.asyncio
    async def test_extract_functions_handle_none_input(self):
        """Test that extraction functions handle None input gracefully"""
        if not PYMUPDF_AVAILABLE:
            pytest.skip("PyMuPDF not available in test environment")

        # Should handle None input gracefully - PyMuPDF creates empty document
        result = await extract_pdf_text(None, "test.pdf")
        assert "test.pdf" in result
        assert "No extractable text" in result or "Error extracting text" in result

    @pytest.mark.asyncio
    async def test_supported_file_types_coverage(self):
        """Test that all supported file types are handled"""
        slack_service = SlackServiceFactory.create_service("test-token")
        test_files = FileProcessingTestDataFactory.all_supported_file_types()

        for filename, mimetype in test_files:
            files = [
                SlackFileBuilder().with_name(filename).with_mimetype(mimetype).build()
            ]

            with patch("requests.get") as mock_get:
                mock_get.return_value = HTTPResponseFactory.success_response(
                    "test content", b"test content"
                )
                result = await process_file_attachments(files, slack_service)
                assert isinstance(result, str)  # Should always return a string
