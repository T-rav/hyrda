import io
import os
import sys
from unittest.mock import Mock, patch

import pytest

# Add the parent directory to sys.path to allow importing the module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from handlers.message_handlers import (
    DEFAULT_SYSTEM_MESSAGE,
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


class TestMessageHandlers:
    """Tests for message handler functions"""

    def test_default_system_message_exists(self):
        """Test that DEFAULT_SYSTEM_MESSAGE is defined"""
        assert DEFAULT_SYSTEM_MESSAGE is not None
        assert isinstance(DEFAULT_SYSTEM_MESSAGE, str)
        assert len(DEFAULT_SYSTEM_MESSAGE) > 0
        assert "Insight Mesh" in DEFAULT_SYSTEM_MESSAGE

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

        # Test with various invalid inputs
        test_cases = [
            (None, "none.pdf"),
            (b"", "empty.pdf"),
            (b"not a pdf", "invalid.pdf"),
        ]

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
        test_cases = [
            (
                "test.docx",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ),
            ("test.docx", "application/wordprocessingml"),
        ]

        for filename, mimetype in test_cases:
            result = await extract_office_text(b"test", filename, mimetype)
            assert filename in result

    @pytest.mark.asyncio
    async def test_extract_office_text_excel_routing(self):
        """Test that Excel files are routed correctly"""
        test_cases = [
            (
                "test.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
            ("test.xlsx", "application/spreadsheetml"),
        ]

        for filename, mimetype in test_cases:
            result = await extract_office_text(b"test", filename, mimetype)
            assert filename in result

    @pytest.mark.asyncio
    async def test_extract_office_text_powerpoint_routing(self):
        """Test that PowerPoint files are routed correctly"""
        test_cases = [
            (
                "test.pptx",
                "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            ),
            ("test.pptx", "application/presentationml"),
        ]

        for filename, mimetype in test_cases:
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
        mock_slack_service = Mock()
        result = await process_file_attachments([], mock_slack_service)
        assert result == ""

    @pytest.mark.asyncio
    async def test_process_file_attachments_no_url(self):
        """Test processing file without private URL"""
        mock_slack_service = Mock()
        files = [{"name": "test.pdf", "mimetype": "application/pdf", "size": 1000}]

        result = await process_file_attachments(files, mock_slack_service)
        assert result == ""  # Should skip files without URL

    @pytest.mark.asyncio
    async def test_process_file_attachments_large_file(self):
        """Test processing file that exceeds size limit"""
        mock_slack_service = Mock()
        files = [
            {
                "name": "huge.pdf",
                "mimetype": "application/pdf",
                "size": 200 * 1024 * 1024,  # 200MB, exceeds 100MB limit
                "url_private": "https://test.com/file",
            }
        ]

        result = await process_file_attachments(files, mock_slack_service)
        assert result == ""  # Should skip large files

    @pytest.mark.asyncio
    async def test_process_file_attachments_download_failure(self):
        """Test processing when file download fails"""
        mock_slack_service = Mock()
        mock_slack_service.settings.bot_token = "test-token"

        files = [
            {
                "name": "test.pdf",
                "mimetype": "application/pdf",
                "size": 1000,
                "url_private": "https://test.com/file",
            }
        ]

        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 404
            mock_get.return_value = mock_response

            result = await process_file_attachments(files, mock_slack_service)
            assert result == ""  # Should handle download failures gracefully

    @pytest.mark.asyncio
    async def test_process_file_attachments_subtitle_files(self):
        """Test processing of subtitle files (VTT, SRT) as text"""
        mock_slack_service = Mock()
        mock_slack_service.settings.bot_token = "test-token"

        subtitle_files = [
            {
                "name": "captions.vtt",
                "mimetype": "text/vtt",
                "size": 500,
                "url_private": "https://test.com/captions.vtt",
            },
            {
                "name": "subtitles.srt",
                "mimetype": "application/x-subrip",
                "size": 300,
                "url_private": "https://test.com/subtitles.srt",
            },
        ]

        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = (
                "00:00:01.000 --> 00:00:03.000\nHello world subtitle content"
            )
            mock_get.return_value = mock_response

            result = await process_file_attachments(subtitle_files, mock_slack_service)

            assert "captions.vtt" in result
            assert "subtitles.srt" in result
            assert "Hello world subtitle content" in result

    @pytest.mark.asyncio
    async def test_process_file_attachments_text_file_success(self):
        """Test successful text file processing"""
        mock_slack_service = Mock()
        mock_slack_service.settings.bot_token = "test-token"

        files = [
            {
                "name": "test.txt",
                "mimetype": "text/plain",
                "size": 100,
                "url_private": "https://test.com/file",
            }
        ]

        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = "This is test content"
            mock_get.return_value = mock_response

            result = await process_file_attachments(files, mock_slack_service)

            assert "test.txt" in result
            assert "This is test content" in result

    @pytest.mark.asyncio
    async def test_process_file_attachments_pdf_success(self):
        """Test PDF file processing workflow"""
        mock_slack_service = Mock()
        mock_slack_service.settings.bot_token = "test-token"

        files = [
            {
                "name": "test.pdf",
                "mimetype": "application/pdf",
                "size": 1000,
                "url_private": "https://test.com/file",
            }
        ]

        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.content = b"fake pdf content"
            mock_get.return_value = mock_response

            result = await process_file_attachments(files, mock_slack_service)

            assert "test.pdf" in result
            # Should contain either extracted text or error message
            assert len(result) > 0


class TestFileProcessingErrorHandling:
    """Tests for error handling in file processing"""

    @pytest.mark.asyncio
    async def test_process_file_attachments_request_exception(self):
        """Test handling of request exceptions"""
        mock_slack_service = Mock()
        mock_slack_service.settings.bot_token = "test-token"

        files = [
            {
                "name": "test.pdf",
                "mimetype": "application/pdf",
                "size": 1000,
                "url_private": "https://test.com/file",
            }
        ]

        with patch("requests.get", side_effect=Exception("Network error")):
            result = await process_file_attachments(files, mock_slack_service)
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
        mock_slack_service = Mock()
        mock_slack_service.settings.bot_token = "test-token"

        # Test various file types
        test_files = [
            ("test.txt", "text/plain"),
            ("test.md", "text/markdown"),
            ("test.py", "text/x-python"),
            ("test.js", "application/javascript"),
            ("test.json", "application/json"),
            ("test.csv", "text/csv"),
            ("test.vtt", "text/vtt"),
            ("test.srt", "application/x-subrip"),
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

        for filename, mimetype in test_files:
            files = [
                {
                    "name": filename,
                    "mimetype": mimetype,
                    "size": 1000,
                    "url_private": "https://test.com/file",
                }
            ]

            with patch("requests.get") as mock_get:
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.text = "test content"
                mock_response.content = b"test content"
                mock_get.return_value = mock_response

                result = await process_file_attachments(files, mock_slack_service)
                assert isinstance(result, str)  # Should always return a string
