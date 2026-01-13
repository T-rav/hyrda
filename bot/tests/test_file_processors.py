"""Unit tests for file processor modules.

Tests the refactored file processing functionality in isolation.
"""

import io
from unittest.mock import Mock, patch

import pytest

from handlers.file_processors.office_processor import (
    extract_excel_text,
    extract_office_text,
    extract_powerpoint_text,
    extract_word_text,
)
from handlers.file_processors.pdf_processor import extract_pdf_text


class TestPDFProcessor:
    """Unit tests for PDF processor module"""

    @pytest.mark.asyncio
    async def test_extract_pdf_unavailable(self):
        """Test PDF extraction when library unavailable"""
        with patch("handlers.file_processors.pdf_processor.PYMUPDF_AVAILABLE", False):
            result = await extract_pdf_text(b"content", "test.pdf")
            assert "PyMuPDF not installed" in result
            assert "test.pdf" in result

    @pytest.mark.asyncio
    async def test_extract_pdf_empty_content(self):
        """Test PDF extraction with empty content"""
        result = await extract_pdf_text(b"", "empty.pdf")
        assert "empty.pdf" in result
        assert "Error extracting text:" in result or "Error:" in result

    @pytest.mark.asyncio
    async def test_extract_pdf_invalid_content(self):
        """Test PDF extraction with invalid PDF data"""
        result = await extract_pdf_text(b"not a pdf", "invalid.pdf")
        assert "invalid.pdf" in result
        assert "Error extracting text:" in result or "Error:" in result


class TestOfficeProcessor:
    """Unit tests for Office document processor module"""

    @pytest.mark.asyncio
    async def test_extract_word_unavailable(self):
        """Test Word extraction when library unavailable"""
        with patch(
            "handlers.file_processors.office_processor.PYTHON_DOCX_AVAILABLE",
            False,
        ):
            result = await extract_word_text(io.BytesIO(b"content"), "test.docx")
            assert "python-docx not installed" in result
            assert "test.docx" in result

    @pytest.mark.asyncio
    async def test_extract_excel_unavailable(self):
        """Test Excel extraction when library unavailable"""
        with patch(
            "handlers.file_processors.office_processor.OPENPYXL_AVAILABLE", False
        ):
            result = await extract_excel_text(io.BytesIO(b"content"), "test.xlsx")
            assert "openpyxl not installed" in result
            assert "test.xlsx" in result

    @pytest.mark.asyncio
    async def test_extract_powerpoint_unavailable(self):
        """Test PowerPoint extraction when library unavailable"""
        with patch(
            "handlers.file_processors.office_processor.PYTHON_PPTX_AVAILABLE",
            False,
        ):
            result = await extract_powerpoint_text(io.BytesIO(b"content"), "test.pptx")
            assert "python-pptx not installed" in result
            assert "test.pptx" in result

    @pytest.mark.asyncio
    async def test_extract_office_word_mimetype(self):
        """Test office text extraction with Word mimetype"""
        mimetype = (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        result = await extract_office_text(b"content", "doc.docx", mimetype)
        # Should route to Word processor (which will fail with invalid content)
        assert "doc.docx" in result

    @pytest.mark.asyncio
    async def test_extract_office_excel_mimetype(self):
        """Test office text extraction with Excel mimetype"""
        mimetype = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        result = await extract_office_text(b"content", "sheet.xlsx", mimetype)
        # Should route to Excel processor
        assert "sheet.xlsx" in result

    @pytest.mark.asyncio
    async def test_extract_office_powerpoint_mimetype(self):
        """Test office text extraction with PowerPoint mimetype"""
        mimetype = (
            "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        )
        result = await extract_office_text(b"content", "slides.pptx", mimetype)
        # Should route to PowerPoint processor
        assert "slides.pptx" in result

    @pytest.mark.asyncio
    async def test_extract_office_simple_type(self):
        """Test office text extraction with simple file type"""
        result = await extract_office_text(b"content", "doc.docx", "docx")
        assert "doc.docx" in result

        result = await extract_office_text(b"content", "sheet.xlsx", "xlsx")
        assert "sheet.xlsx" in result

        result = await extract_office_text(b"content", "slides.pptx", "pptx")
        assert "slides.pptx" in result

    @pytest.mark.asyncio
    async def test_extract_office_unsupported_type(self):
        """Test office text extraction with unsupported file type"""
        result = await extract_office_text(b"content", "unknown.xyz", "xyz")
        assert "Unsupported Office file type" in result
        assert "xyz" in result


class TestFileProcessorIntegration:
    """Integration tests for file processor module"""

    @pytest.mark.asyncio
    async def test_process_multiple_file_types(self):
        """Test processing multiple different file types"""
        from handlers.file_processors import process_file_attachments

        # Mock Slack service
        slack_service = Mock()
        slack_service.bot_token = "test-token"

        # Create mock files
        files = [
            {
                "name": "test.txt",
                "mimetype": "text/plain",
                "url_private": "https://test.com/test.txt",
            },
            {
                "name": "captions.vtt",
                "mimetype": "text/vtt",
                "url_private": "https://test.com/captions.vtt",
            },
            {
                "name": "subs.srt",
                "mimetype": "application/x-subrip",
                "url_private": "https://test.com/subs.srt",
            },
        ]

        # Mock requests to return text content
        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.content = b"test content"
            mock_get.return_value = mock_response

            result = await process_file_attachments(files, slack_service)

            # All files should be processed
            assert "test.txt" in result
            assert "captions.vtt" in result
            assert "subs.srt" in result
            assert "test content" in result

    @pytest.mark.asyncio
    async def test_process_files_with_errors(self):
        """Test that error messages are included in output"""
        from handlers.file_processors import process_file_attachments

        slack_service = Mock()
        slack_service.bot_token = "test-token"

        files = [
            {
                "name": "bad.pdf",
                "mimetype": "application/pdf",
                "url_private": "https://test.com/bad.pdf",
            },
        ]

        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.content = b"not a pdf"
            mock_get.return_value = mock_response

            result = await process_file_attachments(files, slack_service)

            # Error message should be included
            assert len(result) > 0
            assert "bad.pdf" in result
