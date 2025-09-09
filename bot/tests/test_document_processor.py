"""
Tests for Document Processor Service

Comprehensive tests for document processing and chunking functionality.
"""

import json

from services.document_processor import DocumentProcessor


class TestDocumentProcessor:
    """Test document processor functionality"""

    def setup_method(self):
        """Set up test fixtures"""
        self.processor = DocumentProcessor()

    def test_init(self):
        """Test DocumentProcessor initialization"""
        processor = DocumentProcessor()
        assert isinstance(processor, DocumentProcessor)

    def test_process_text_file_basic(self):
        """Test basic text file processing"""
        content = "First paragraph.\n\nSecond paragraph with more content to meet minimum length."
        metadata = {"file_name": "test.txt"}

        result = self.processor.process_text_file(content, metadata)

        assert len(result) == 1  # Only second paragraph meets 50 char minimum
        assert (
            result[0]["content"]
            == "Second paragraph with more content to meet minimum length."
        )

        # Check metadata
        for chunk in result:
            assert chunk["metadata"]["file_name"] == "test.txt"
            assert chunk["metadata"]["content_type"] == "text"
            assert "chunk_id" in chunk["metadata"]

    def test_process_text_file_empty_content(self):
        """Test processing empty text content"""
        result = self.processor.process_text_file("")
        assert result == []

        result = self.processor.process_text_file("   \n\n   ")
        assert result == []

    def test_process_text_file_single_paragraph(self):
        """Test processing single paragraph"""
        content = (
            "This is a single paragraph with enough content to be processed as a chunk."
        )
        result = self.processor.process_text_file(content)

        assert len(result) == 1
        assert result[0]["content"] == content
        assert result[0]["metadata"]["chunk_id"] == 0

    def test_process_text_file_short_paragraphs_filtered(self):
        """Test that short paragraphs are filtered out"""
        content = (
            "Short.\n\nThis is a longer paragraph with sufficient content.\n\nTiny"
        )
        result = self.processor.process_text_file(content)

        # Only the longer paragraph should be included
        assert len(result) == 1
        assert "longer paragraph" in result[0]["content"]

    def test_process_text_file_no_double_newlines(self):
        """Test processing text without paragraph breaks"""
        content = "This is all one long paragraph without any double newline breaks in it whatsoever."
        result = self.processor.process_text_file(content)

        # Should treat entire content as single chunk
        assert len(result) == 1
        assert result[0]["content"] == content

    def test_process_text_file_without_metadata(self):
        """Test processing without metadata"""
        content = (
            "Test paragraph with enough content to be processed as a proper chunk."
        )
        result = self.processor.process_text_file(content, None)

        assert len(result) == 1
        assert result[0]["metadata"]["content_type"] == "text"
        assert result[0]["metadata"]["chunk_id"] == 0

    def test_process_markdown_file_basic(self):
        """Test basic Markdown file processing"""
        content = """# Title

## Section 1
Content for section 1 with enough text to be meaningful and exceed the minimum character requirements for processing.

## Section 2
Content for section 2 with additional information that also meets the minimum length requirements for chunk creation."""

        metadata = {"file_name": "test.md"}
        result = self.processor.process_markdown_file(content, metadata)

        assert len(result) == 2  # Both sections meet 100 char minimum
        assert any("Section 1" in chunk["content"] for chunk in result)
        assert all(chunk["metadata"]["content_type"] == "markdown" for chunk in result)

    def test_process_markdown_file_with_code_blocks(self):
        """Test Markdown processing with code blocks"""
        content = """# Documentation

Here is some code:

```python
def hello_world():
    print("Hello, world!")
```

End of document with sufficient content."""

        result = self.processor.process_markdown_file(content)

        # Should handle code blocks
        assert len(result) >= 1
        code_chunk = next(
            (chunk for chunk in result if "```python" in chunk["content"]), None
        )
        assert code_chunk is not None

    def test_process_markdown_file_empty_content(self):
        """Test Markdown processing with empty content"""
        result = self.processor.process_markdown_file("")
        assert result == []

    def test_process_json_file_basic(self):
        """Test JSON file processing"""
        data = {
            "title": "Test Document",
            "description": "This is a test document with various fields and content.",
            "items": ["item1", "item2", "item3"],
            "metadata": {"author": "Test Author"},
        }
        content = json.dumps(data, indent=2)

        result = self.processor.process_json_file(content, {"file_name": "test.json"})

        assert len(result) == 1
        # Should include structured content (JSON processor includes descriptions > 20 chars)
        assert any(
            "test document with various fields" in chunk["content"] for chunk in result
        )
        assert all(chunk["metadata"]["content_type"] == "json" for chunk in result)

    def test_process_json_file_invalid_json(self):
        """Test JSON processing with invalid JSON"""
        invalid_json = '{"invalid": json content}'

        result = self.processor.process_json_file(invalid_json)

        # Should handle gracefully and return empty
        assert result == []

    def test_process_json_file_empty_object(self):
        """Test JSON processing with empty object"""
        result = self.processor.process_json_file("{}")
        assert result == []

    def test_chunk_large_text_basic(self):
        """Test chunking large text into manageable pieces"""
        # Create a large text document
        large_text = "This is a sentence. " * 1000  # Very large text

        chunks = self.processor.chunk_large_text(large_text, chunk_size=500, overlap=50)

        assert len(chunks) > 1
        assert all(len(chunk) <= 550 for chunk in chunks)  # chunk_size + overlap

        # Check overlap between chunks
        if len(chunks) > 1:
            # First chunk end should appear in second chunk start
            assert chunks[0][-30:] in chunks[1]

    def test_chunk_large_text_small_content(self):
        """Test chunking text smaller than chunk size"""
        small_text = "This is a small text."
        chunks = self.processor.chunk_large_text(small_text, chunk_size=1000)

        assert len(chunks) == 1
        assert chunks[0] == small_text

    def test_chunk_large_text_custom_parameters(self):
        """Test chunking with custom parameters"""
        text = "Word " * 100  # 100 words
        chunks = self.processor.chunk_large_text(text, chunk_size=50, overlap=10)

        assert len(chunks) > 1
        assert all(
            len(chunk) <= 60 for chunk in chunks
        )  # Some tolerance for word boundaries

    def test_extract_metadata_from_content_text(self):
        """Test metadata extraction from text content"""
        content = """Title: Important Document
Author: John Doe
Date: 2023-01-01

This is the main content of the document with important information."""

        metadata = self.processor.extract_metadata_from_content(content, "text")

        assert "extracted_title" in metadata
        assert metadata["extracted_title"] == "Important Document"
        assert metadata["content_type"] == "text"

    def test_extract_metadata_from_content_markdown(self):
        """Test metadata extraction from Markdown content"""
        content = """# Main Title

This document contains important information about various topics."""

        metadata = self.processor.extract_metadata_from_content(content, "markdown")

        assert "extracted_title" in metadata
        assert metadata["extracted_title"] == "Main Title"

    def test_extract_metadata_from_content_no_title(self):
        """Test metadata extraction when no title is found"""
        content = "Just some regular content without any title markers."

        metadata = self.processor.extract_metadata_from_content(content, "text")

        assert metadata["content_type"] == "text"
        assert "extracted_title" not in metadata

    def test_clean_text_content_basic(self):
        """Test basic text cleaning"""
        dirty_text = (
            "   This is text with    extra spaces   and\n\nmultiple\n\nlines.   "
        )

        clean_text = self.processor.clean_text_content(dirty_text)

        assert clean_text == "This is text with extra spaces and\n\nmultiple\n\nlines."
        assert not clean_text.startswith(" ")
        assert not clean_text.endswith(" ")

    def test_clean_text_content_special_characters(self):
        """Test cleaning text with special characters"""
        text_with_special = "Text with\ttabs and\r\ncarriage returns and\x00null chars."

        clean_text = self.processor.clean_text_content(text_with_special)

        # Should normalize whitespace
        assert "\t" not in clean_text
        assert "\r" not in clean_text
        assert "\x00" not in clean_text

    def test_clean_text_content_unicode(self):
        """Test cleaning text with Unicode characters"""
        unicode_text = "Text with émojis 🚀 and ünïcödé characters."

        clean_text = self.processor.clean_text_content(unicode_text)

        # Should preserve Unicode content
        assert "émojis" in clean_text
        assert "🚀" in clean_text
        assert "ünïcödé" in clean_text

    def test_get_content_summary_basic(self):
        """Test content summarization"""
        content = "This is a longer piece of content " * 50  # 200+ words

        summary = self.processor.get_content_summary(content, max_length=100)

        assert len(summary) <= 120  # Some tolerance
        assert "..." in summary or len(summary) < len(content)

    def test_get_content_summary_short_content(self):
        """Test summarization of short content"""
        short_content = "This is short content."

        summary = self.processor.get_content_summary(short_content, max_length=100)

        assert summary == short_content

    def test_validate_document_structure_valid(self):
        """Test validation of valid document structure"""
        doc = {
            "content": "Valid content with sufficient length to be meaningful.",
            "metadata": {"file_name": "test.txt", "content_type": "text"},
        }

        is_valid = self.processor.validate_document_structure(doc)
        assert is_valid is True

    def test_validate_document_structure_missing_content(self):
        """Test validation with missing content"""
        doc = {"metadata": {"file_name": "test.txt"}}

        is_valid = self.processor.validate_document_structure(doc)
        assert is_valid is False

    def test_validate_document_structure_empty_content(self):
        """Test validation with empty content"""
        doc = {"content": "", "metadata": {"file_name": "test.txt"}}

        is_valid = self.processor.validate_document_structure(doc)
        assert is_valid is False

    def test_validate_document_structure_short_content(self):
        """Test validation with too short content"""
        doc = {
            "content": "Short",  # Too short
            "metadata": {"file_name": "test.txt"},
        }

        is_valid = self.processor.validate_document_structure(doc)
        assert is_valid is False


class TestDocumentProcessorIntegration:
    """Integration tests for document processor"""

    def setup_method(self):
        """Set up test fixtures"""
        self.processor = DocumentProcessor()

    def test_full_text_processing_pipeline(self):
        """Test complete text processing pipeline"""
        raw_content = """Title: Sample Document
Author: Test User

This is the first section with substantial content that should be processed.

This is the second section with additional information and details.

Short."""  # This should be filtered out

        # Process through complete pipeline
        chunks = self.processor.process_text_file(
            raw_content, {"file_name": "sample.txt"}
        )

        # Should have 2 chunks (short one filtered)
        assert len(chunks) == 2

        # Verify metadata extraction and structure
        for chunk in chunks:
            assert self.processor.validate_document_structure(chunk)
            assert chunk["metadata"]["content_type"] == "text"

    def test_multiple_format_processing(self):
        """Test processing multiple document formats"""
        # Text content
        text_content = (
            "This is plain text content with sufficient length for processing."
        )
        text_result = self.processor.process_text_file(text_content)

        # Markdown content
        md_content = "# Title\n\nThis is markdown content with sufficient length for processing and meeting the minimum character requirements needed to create a valid chunk."
        md_result = self.processor.process_markdown_file(md_content)

        # JSON content
        json_content = '{"title": "Test", "content": "This is JSON content with sufficient length."}'
        json_result = self.processor.process_json_file(json_content)

        # All should produce valid results
        assert len(text_result) >= 1
        assert len(md_result) >= 1
        assert len(json_result) >= 1

        # Different content types
        assert text_result[0]["metadata"]["content_type"] == "text"
        assert md_result[0]["metadata"]["content_type"] == "markdown"
        assert json_result[0]["metadata"]["content_type"] == "json"

    def test_large_document_processing(self):
        """Test processing very large documents"""
        # Create large content
        large_content = "This is a paragraph with substantial content. " * 1000

        # Process as text
        result = self.processor.process_text_file(large_content)

        # Should handle large content
        assert len(result) >= 1

        # Test chunking if content is very large
        if len(large_content) > 2000:
            chunks = self.processor.chunk_large_text(
                large_content, chunk_size=1000, overlap=100
            )
            assert len(chunks) > 1


class TestDocumentProcessorEdgeCases:
    """Test edge cases and error conditions"""

    def setup_method(self):
        """Set up test fixtures"""
        self.processor = DocumentProcessor()

    def test_malformed_content_handling(self):
        """Test handling of malformed content"""
        malformed_inputs = [
            None,
            123,  # Not a string
            [],  # Wrong type
            {"not": "text"},  # Wrong type
        ]

        for bad_input in malformed_inputs:
            try:
                result = self.processor.process_text_file(bad_input)
                # If no exception, should return empty list
                assert result == []
            except (TypeError, AttributeError):
                # Expected for some inputs
                pass

    def test_very_long_lines(self):
        """Test handling of very long lines"""
        very_long_line = "This is an extremely long line " * 1000  # No line breaks

        result = self.processor.process_text_file(very_long_line)

        # Should handle gracefully
        assert len(result) >= 1

    def test_special_unicode_content(self):
        """Test handling of special Unicode content"""
        unicode_content = """
        Título con acentos: Documentación Técnica con contenido suficiente para superar el mínimo de caracteres requerido para el procesamiento.

        Content with émojis and sufficient text length: 🚀 🎉 📄 This paragraph has enough content to be processed.

        Chinese characters with extra content: 你好世界 - Hello world with additional text to meet minimum requirements.

        Arabic text with additional content: مرحبا بالعالم - Hello world with more text for processing requirements.

        Mathematical symbols with explanation: ∑∀∃∈∉∅∞ These symbols represent various mathematical concepts and operations.
        """

        result = self.processor.process_text_file(unicode_content)

        # Should preserve Unicode content
        assert len(result) >= 1
        content_str = " ".join(chunk["content"] for chunk in result)
        assert "émojis" in content_str
        assert "🚀" in content_str

    def test_extremely_small_chunks(self):
        """Test behavior with content that produces very small chunks"""
        tiny_content = "A.\n\nB.\n\nC.\n\nD."  # All chunks too small

        result = self.processor.process_text_file(tiny_content)

        # Should filter out tiny chunks
        assert result == []

    def test_mixed_line_endings(self):
        """Test handling of mixed line endings"""
        mixed_endings = "Line 1 with Windows ending\r\n\r\nLine 2 with Unix ending\n\nLine 3 with Mac ending\r\r"

        result = self.processor.process_text_file(mixed_endings)

        # Should normalize line endings
        assert len(result) >= 1

    def test_json_processing_edge_cases(self):
        """Test JSON processing with edge cases"""
        edge_cases = [
            "null",  # Valid JSON but null
            "[]",  # Empty array
            '""',  # Empty string
            "123",  # Just a number
            '{"nested": {"very": {"deep": {"object": "value"}}}}',  # Deep nesting
        ]

        for case in edge_cases:
            result = self.processor.process_json_file(case)
            # Should handle gracefully (may return empty for some cases)
            assert isinstance(result, list)

    def test_chunking_edge_cases(self):
        """Test chunking with edge cases"""
        # Empty content
        assert self.processor.chunk_large_text("") == [""]

        # Single character
        assert self.processor.chunk_large_text("A") == ["A"]

        # Exact chunk size
        text = "A" * 100
        chunks = self.processor.chunk_large_text(text, chunk_size=100, overlap=0)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_metadata_extraction_edge_cases(self):
        """Test metadata extraction with edge cases"""
        edge_cases = [
            "",  # Empty content
            "No title here",  # No title patterns
            "Title:\n",  # Empty title
            "# \n\nEmpty markdown title",  # Empty markdown title
        ]

        for content in edge_cases:
            metadata = self.processor.extract_metadata_from_content(content, "text")
            assert isinstance(metadata, dict)
            assert metadata["content_type"] == "text"
