"""
Tests for DocumentProcessor service.
"""

import io
import pytest
from unittest.mock import Mock, patch, mock_open
from services.document_processor import DocumentProcessor


class TestDocumentProcessor:
    """Test cases for DocumentProcessor service."""

    @pytest.fixture
    def processor(self):
        """Create DocumentProcessor instance for testing."""
        return DocumentProcessor()

    def test_extract_text_unsupported_mime_type(self, processor):
        """Test handling of unsupported MIME types."""
        content = b"test content"
        result = processor.extract_text(content, "application/unsupported")
        assert result is None

    def test_extract_text_content_utf8(self, processor):
        """Test text extraction from UTF-8 content."""
        content = "Hello, world! 🌍".encode('utf-8')
        result = processor.extract_text(content, "text/plain")
        assert result == "Hello, world! 🌍"

    def test_extract_text_content_latin1_fallback(self, processor):
        """Test fallback to latin-1 for non-UTF-8 content."""
        content = b'\xe9\xe8\xe7'  # Non-UTF-8 bytes
        result = processor.extract_text(content, "text/plain")
        assert result is not None  # Should decode with latin-1

    @patch('services.document_processor.fitz')
    def test_extract_pdf_text_success(self, mock_fitz, processor):
        """Test successful PDF text extraction."""
        # Mock PDF document
        mock_doc = Mock()
        mock_doc.page_count = 2

        mock_page1 = Mock()
        mock_page1.get_text.return_value = "Page 1 content"

        mock_page2 = Mock()
        mock_page2.get_text.return_value = "Page 2 content"

        mock_doc.load_page.side_effect = [mock_page1, mock_page2]
        mock_fitz.open.return_value = mock_doc

        content = b"fake pdf content"
        result = processor.extract_text(content, "application/pdf")

        assert result == "Page 1 content\n\nPage 2 content"
        mock_doc.close.assert_called_once()

    @patch('services.document_processor.fitz')
    def test_extract_pdf_text_empty_pages(self, mock_fitz, processor):
        """Test PDF extraction with empty pages."""
        mock_doc = Mock()
        mock_doc.page_count = 2

        mock_page1 = Mock()
        mock_page1.get_text.return_value = "   "  # Whitespace only

        mock_page2 = Mock()
        mock_page2.get_text.return_value = ""  # Empty

        mock_doc.load_page.side_effect = [mock_page1, mock_page2]
        mock_fitz.open.return_value = mock_doc

        content = b"fake pdf content"
        result = processor.extract_text(content, "application/pdf")

        assert result is None

    @patch('services.document_processor.fitz')
    def test_extract_pdf_text_error(self, mock_fitz, processor):
        """Test PDF extraction error handling."""
        mock_fitz.open.side_effect = Exception("PDF error")

        content = b"fake pdf content"
        result = processor.extract_text(content, "application/pdf")

        assert result is None

    @patch('services.document_processor.Document')
    def test_extract_docx_text_success(self, mock_document, processor):
        """Test successful Word document text extraction."""
        # Mock document with paragraphs and table
        mock_doc = Mock()

        # Mock paragraphs
        mock_para1 = Mock()
        mock_para1.text = "Paragraph 1"
        mock_para2 = Mock()
        mock_para2.text = "Paragraph 2"

        mock_doc.paragraphs = [mock_para1, mock_para2]

        # Mock table
        mock_cell1 = Mock()
        mock_cell1.text = "Cell 1"
        mock_cell2 = Mock()
        mock_cell2.text = "Cell 2"

        mock_row = Mock()
        mock_row.cells = [mock_cell1, mock_cell2]

        mock_table = Mock()
        mock_table.rows = [mock_row]

        mock_doc.tables = [mock_table]
        mock_document.return_value = mock_doc

        content = b"fake docx content"
        result = processor.extract_text(content,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document")

        assert "Paragraph 1" in result
        assert "Paragraph 2" in result
        assert "Cell 1 | Cell 2" in result

    @patch('services.document_processor.Document')
    def test_extract_docx_text_error(self, mock_document, processor):
        """Test Word document extraction error handling."""
        mock_document.side_effect = Exception("DOCX error")

        content = b"fake docx content"
        result = processor.extract_text(content,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document")

        assert result is None

    @patch('services.document_processor.load_workbook')
    def test_extract_xlsx_text_success(self, mock_load_workbook, processor):
        """Test successful Excel spreadsheet text extraction."""
        # Mock workbook with multiple sheets
        mock_workbook = Mock()
        mock_workbook.sheetnames = ["Sheet1", "Sheet2"]

        # Mock Sheet1
        mock_sheet1 = Mock()
        mock_sheet1.iter_rows.return_value = [
            ("Header1", "Header2"),
            ("Value1", "Value2"),
            (None, "Value3")  # Test None handling
        ]

        # Mock Sheet2 - empty
        mock_sheet2 = Mock()
        mock_sheet2.iter_rows.return_value = [(None, None)]

        # Use proper dict access mocking
        def getitem_side_effect(name):
            if name == "Sheet1":
                return mock_sheet1
            elif name == "Sheet2":
                return mock_sheet2
            raise KeyError(name)

        mock_workbook.__getitem__ = Mock(side_effect=getitem_side_effect)
        mock_load_workbook.return_value = mock_workbook

        content = b"fake xlsx content"
        result = processor.extract_text(content,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        assert "Sheet: Sheet1" in result
        assert "Header1 | Header2" in result
        assert "Value1 | Value2" in result
        assert "Value3" in result
        mock_workbook.close.assert_called_once()

    @patch('services.document_processor.load_workbook')
    def test_extract_xlsx_text_error(self, mock_load_workbook, processor):
        """Test Excel spreadsheet extraction error handling."""
        mock_load_workbook.side_effect = Exception("XLSX error")

        content = b"fake xlsx content"
        result = processor.extract_text(content,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        assert result is None

    @patch('services.document_processor.Presentation')
    def test_extract_pptx_text_success(self, mock_presentation, processor):
        """Test successful PowerPoint presentation text extraction."""
        # Mock presentation with slides
        mock_pres = Mock()

        # Mock slide 1 with text shapes
        mock_shape1 = Mock(spec=['text'])
        mock_shape1.text = "Slide 1 Title"

        mock_shape2 = Mock(spec=['text'])
        mock_shape2.text = "Slide 1 Content"

        mock_slide1 = Mock()
        mock_slide1.shapes = [mock_shape1, mock_shape2]

        # Mock slide 2 with table only (no text)
        mock_table_cell1 = Mock()
        mock_table_cell1.text = "Table Cell 1"
        mock_table_cell2 = Mock()
        mock_table_cell2.text = "Table Cell 2"

        mock_table_row = Mock()
        mock_table_row.cells = [mock_table_cell1, mock_table_cell2]

        mock_table = Mock()
        mock_table.rows = [mock_table_row]

        # Create shape with table but no text attribute
        mock_shape_with_table = Mock(spec=['table'])
        mock_shape_with_table.table = mock_table

        mock_slide2 = Mock()
        mock_slide2.shapes = [mock_shape_with_table]

        mock_pres.slides = [mock_slide1, mock_slide2]
        mock_presentation.return_value = mock_pres

        content = b"fake pptx content"
        result = processor.extract_text(content,
            "application/vnd.openxmlformats-officedocument.presentationml.presentation")

        assert "Slide 1" in result
        assert "Slide 1 Title" in result
        assert "Slide 1 Content" in result
        assert "Slide 2" in result
        assert "Table Cell 1 | Table Cell 2" in result

    @patch('services.document_processor.Presentation')
    def test_extract_pptx_text_error(self, mock_presentation, processor):
        """Test PowerPoint presentation extraction error handling."""
        mock_presentation.side_effect = Exception("PPTX error")

        content = b"fake pptx content"
        result = processor.extract_text(content,
            "application/vnd.openxmlformats-officedocument.presentationml.presentation")

        assert result is None

    def test_extract_pptx_text_shape_without_text(self, processor):
        """Test PowerPoint shape handling when shape has no text attribute."""
        with patch('services.document_processor.Presentation') as mock_presentation:
            mock_shape_no_text = Mock()
            # Shape without text attribute
            del mock_shape_no_text.text

            mock_slide = Mock()
            mock_slide.shapes = [mock_shape_no_text]

            mock_pres = Mock()
            mock_pres.slides = [mock_slide]
            mock_presentation.return_value = mock_pres

            content = b"fake pptx content"
            result = processor.extract_text(content,
                "application/vnd.openxmlformats-officedocument.presentationml.presentation")

            # Should handle gracefully and return None for empty content
            assert result is None

    def test_extract_pptx_text_shape_without_table(self, processor):
        """Test PowerPoint shape handling when shape has no table attribute."""
        with patch('services.document_processor.Presentation') as mock_presentation:
            mock_shape_no_table = Mock()
            # Shape without table attribute
            del mock_shape_no_table.table

            mock_slide = Mock()
            mock_slide.shapes = [mock_shape_no_table]

            mock_pres = Mock()
            mock_pres.slides = [mock_slide]
            mock_presentation.return_value = mock_pres

            content = b"fake pptx content"
            result = processor.extract_text(content,
                "application/vnd.openxmlformats-officedocument.presentationml.presentation")

            # Should handle gracefully
            assert result is None
