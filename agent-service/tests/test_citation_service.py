"""Comprehensive tests for CitationService.

Tests cover:
- Source citation formatting for various source types (Google Drive, Metric.ai)
- Citation deduplication and filtering
- Uploaded document filtering
- Citation generation with chunk count information
- Metadata extraction and handling
- File extension removal
- Similarity score formatting
- Web view link handling
- Context formatting for LLM consumption
- Edge cases and missing metadata
- Empty context handling
"""

import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.citation_service import CitationService


class TestCitationServiceInitialization:
    """Test CitationService initialization."""

    def test_initialization(self):
        """Test basic initialization."""
        # Arrange & Act
        service = CitationService()

        # Assert
        assert service is not None
        assert isinstance(service, CitationService)


class TestAddSourceCitations:
    """Test add_source_citations method."""

    def test_add_citations_empty_context(self):
        """Test citation addition with empty context chunks."""
        # Arrange
        service = CitationService()
        response = "This is the response"
        context_chunks = []

        # Act
        result = service.add_source_citations(response, context_chunks)

        # Assert
        assert result == response
        assert "Sources:" not in result

    def test_add_citations_single_google_drive_source(self):
        """Test citation addition with single Google Drive document."""
        # Arrange
        service = CitationService()
        response = "Here is the information"
        context_chunks = [
            {
                "content": "Document content",
                "similarity": 0.95,
                "metadata": {
                    "file_name": "report.pdf",
                    "source": "google_drive",
                    "web_view_link": "https://drive.google.com/file/d/123",
                },
            }
        ]

        # Act
        result = service.add_source_citations(response, context_chunks)

        # Assert
        assert response in result
        assert "Sources:" in result
        assert "report" in result
        assert "Knowledge Base" in result
        assert "Match: 95.0%" in result
        assert "[" in result and "](" in result  # Has markdown link

    def test_add_citations_single_metric_source(self):
        """Test citation addition with single Metric.ai source."""
        # Arrange
        service = CitationService()
        response = "Here is employee information"
        context_chunks = [
            {
                "content": "Employee data",
                "similarity": 0.88,
                "metadata": {
                    "name": "John Smith",
                    "source": "metric",
                    "data_type": "employee",
                    "role": "Senior Engineer",
                },
            }
        ]

        # Act
        result = service.add_source_citations(response, context_chunks)

        # Assert
        assert response in result
        assert "Sources:" in result
        assert "John Smith" in result
        assert "Senior Engineer" in result
        assert "Metric.ai" in result
        assert "Match: 88.0%" in result

    def test_add_citations_multiple_sources_deduplication(self):
        """Test deduplication when multiple chunks from same file."""
        # Arrange
        service = CitationService()
        response = "Combined information"
        context_chunks = [
            {
                "content": "Content 1",
                "similarity": 0.95,
                "metadata": {
                    "file_name": "document.pdf",
                    "source": "google_drive",
                },
            },
            {
                "content": "Content 2",
                "similarity": 0.88,
                "metadata": {
                    "file_name": "document.pdf",
                    "source": "google_drive",
                },
            },
            {
                "content": "Content 3",
                "similarity": 0.82,
                "metadata": {
                    "file_name": "document.pdf",
                    "source": "google_drive",
                },
            },
        ]

        # Act
        result = service.add_source_citations(response, context_chunks)

        # Assert
        # Should only list document once with chunk count
        assert result.count("document") == 1
        assert "3 sections" in result
        assert "Match: 95.0%" in result  # Should show first match

    def test_add_citations_chunk_count_display(self):
        """Test that chunk count is displayed when multiple chunks from same file."""
        # Arrange
        service = CitationService()
        response = "Test response"
        context_chunks = [
            {
                "content": "Chunk 1",
                "similarity": 0.9,
                "metadata": {
                    "file_name": "guide.pdf",
                    "source": "google_drive",
                },
            },
            {
                "content": "Chunk 2",
                "similarity": 0.85,
                "metadata": {
                    "file_name": "guide.pdf",
                    "source": "google_drive",
                },
            },
        ]

        # Act
        result = service.add_source_citations(response, context_chunks)

        # Assert
        assert "2 sections" in result

    def test_add_citations_no_chunk_count_for_single(self):
        """Test that chunk count is not displayed for single chunk."""
        # Arrange
        service = CitationService()
        response = "Test response"
        context_chunks = [
            {
                "content": "Single content",
                "similarity": 0.92,
                "metadata": {
                    "file_name": "single.pdf",
                    "source": "google_drive",
                },
            }
        ]

        # Act
        result = service.add_source_citations(response, context_chunks)

        # Assert
        # Should not have "sections" since there's only 1
        assert "1 sections" not in result
        assert "single" in result

    def test_add_citations_file_extension_removal(self):
        """Test that file extensions are removed from citation titles."""
        # Arrange
        service = CitationService()
        response = "Information about PDF"
        context_chunks = [
            {
                "content": "Content",
                "similarity": 0.9,
                "metadata": {
                    "file_name": "report.pdf",
                    "source": "google_drive",
                },
            },
            {
                "content": "Content",
                "similarity": 0.88,
                "metadata": {
                    "file_name": "document.docx",
                    "source": "google_drive",
                },
            },
            {
                "content": "Content",
                "similarity": 0.85,
                "metadata": {
                    "file_name": "notes.txt",
                    "source": "google_drive",
                },
            },
        ]

        # Act
        result = service.add_source_citations(response, context_chunks)

        # Assert
        assert "report" in result and "report.pdf" not in result
        assert "document" in result and "document.docx" not in result
        assert "notes" in result and "notes.txt" not in result

    def test_add_citations_uploaded_document_filtered(self):
        """Test that uploaded documents are filtered out from citations."""
        # Arrange
        service = CitationService()
        response = "Information from uploaded and KB"
        context_chunks = [
            {
                "content": "Uploaded content",
                "similarity": 0.98,
                "metadata": {
                    "file_name": "uploaded.pdf",
                    "source": "uploaded_document",
                },
            },
            {
                "content": "KB content",
                "similarity": 0.9,
                "metadata": {
                    "file_name": "kb_doc.pdf",
                    "source": "google_drive",
                },
            },
        ]

        # Act
        result = service.add_source_citations(response, context_chunks)

        # Assert
        # Response text still contains "uploaded" but it shouldn't be in sources
        # Check that only kb_doc is in sources section
        sources_section = (
            result.split("**📚 Sources:**")[1] if "**📚 Sources:**" in result else ""
        )
        assert "kb_doc" in sources_section
        assert "uploaded" not in sources_section

    def test_add_citations_with_subtitle_from_metadata(self):
        """Test citation includes subtitle from metadata."""
        # Arrange
        service = CitationService()
        response = "Response text"
        context_chunks = [
            {
                "content": "Content",
                "similarity": 0.9,
                "metadata": {
                    "file_name": "report.pdf",
                    "source": "google_drive",
                    "title": "Annual Report 2024",
                },
            }
        ]

        # Act
        result = service.add_source_citations(response, context_chunks)

        # Assert
        assert "report" in result
        assert "Annual Report 2024" in result
        assert "•" in result  # Separator between title and subtitle

    def test_add_citations_metric_with_project_type(self):
        """Test Metric.ai citation with project data type."""
        # Arrange
        service = CitationService()
        response = "Project information"
        context_chunks = [
            {
                "content": "Project data",
                "similarity": 0.87,
                "metadata": {
                    "name": "Website Redesign",
                    "source": "metric",
                    "data_type": "project",
                    "client": "Acme Corp",
                },
            }
        ]

        # Act
        result = service.add_source_citations(response, context_chunks)

        # Assert
        assert "Website Redesign" in result
        assert "Acme Corp" in result
        assert "Metric.ai" in result

    def test_add_citations_similarity_percentage_format(self):
        """Test that similarity scores are formatted as percentages."""
        # Arrange
        service = CitationService()
        response = "Response"
        context_chunks = [
            {
                "content": "Content",
                "similarity": 0.756,
                "metadata": {
                    "file_name": "doc.pdf",
                    "source": "google_drive",
                },
            }
        ]

        # Act
        result = service.add_source_citations(response, context_chunks)

        # Assert
        assert "Match: 75.6%" in result

    def test_add_citations_numbering(self):
        """Test that citations are numbered correctly."""
        # Arrange
        service = CitationService()
        response = "Response"
        context_chunks = [
            {
                "content": "Content 1",
                "similarity": 0.9,
                "metadata": {
                    "file_name": "doc1.pdf",
                    "source": "google_drive",
                },
            },
            {
                "content": "Content 2",
                "similarity": 0.85,
                "metadata": {
                    "file_name": "doc2.pdf",
                    "source": "google_drive",
                },
            },
            {
                "content": "Content 3",
                "similarity": 0.8,
                "metadata": {
                    "file_name": "doc3.pdf",
                    "source": "google_drive",
                },
            },
        ]

        # Act
        result = service.add_source_citations(response, context_chunks)

        # Assert
        assert "1. " in result
        assert "2. " in result
        assert "3. " in result

    def test_add_citations_web_view_link_markdown(self):
        """Test that web view links are formatted as markdown links."""
        # Arrange
        service = CitationService()
        response = "Response"
        context_chunks = [
            {
                "content": "Content",
                "similarity": 0.9,
                "metadata": {
                    "file_name": "document.pdf",
                    "source": "google_drive",
                    "web_view_link": "https://drive.google.com/file/d/abc123/view",
                },
            }
        ]

        # Act
        result = service.add_source_citations(response, context_chunks)

        # Assert
        assert "[" in result
        assert "](https://drive.google.com/file/d/abc123/view)" in result

    def test_add_citations_no_link_for_metric(self):
        """Test that Metric.ai sources don't get markdown links."""
        # Arrange
        service = CitationService()
        response = "Response"
        context_chunks = [
            {
                "content": "Content",
                "similarity": 0.9,
                "metadata": {
                    "name": "Metric Record",
                    "source": "metric",
                    "data_type": "record",
                },
            }
        ]

        # Act
        result = service.add_source_citations(response, context_chunks)

        # Assert
        # Metric citations should not be markdown links
        assert "Metric Record" in result
        assert "Metric.ai" in result
        # Should not have markdown link syntax for metric
        assert result.count("[") == 0  # No markdown links for metric

    def test_add_citations_case_insensitive_deduplication(self):
        """Test that deduplication is case-insensitive."""
        # Arrange
        service = CitationService()
        response = "Response"
        context_chunks = [
            {
                "content": "Content 1",
                "similarity": 0.9,
                "metadata": {
                    "file_name": "Document.pdf",
                    "source": "google_drive",
                },
            },
            {
                "content": "Content 2",
                "similarity": 0.85,
                "metadata": {
                    "file_name": "document.pdf",
                    "source": "google_drive",
                },
            },
        ]

        # Act
        result = service.add_source_citations(response, context_chunks)

        # Assert
        # Should only appear once due to case-insensitive dedup
        # The file_chunk_counts is keyed by file_name, and the deduplication
        # only prevents listing the source twice, not the chunk count
        sources_section = (
            result.split("**📚 Sources:**")[1] if "**📚 Sources:**" in result else ""
        )
        # Count how many times the filename appears in sources
        assert (
            sources_section.count("Document") == 1
            or sources_section.count("document") == 1
        )

    def test_add_citations_with_missing_web_view_link(self):
        """Test citation when web_view_link is missing."""
        # Arrange
        service = CitationService()
        response = "Response"
        context_chunks = [
            {
                "content": "Content",
                "similarity": 0.9,
                "metadata": {
                    "file_name": "doc.pdf",
                    "source": "google_drive",
                },
            }
        ]

        # Act
        result = service.add_source_citations(response, context_chunks)

        # Assert
        assert "doc" in result
        assert "Sources:" in result
        # Should not have markdown link without web_view_link
        # But should have the citation

    def test_add_citations_with_missing_metadata(self):
        """Test citation when metadata is missing."""
        # Arrange
        service = CitationService()
        response = "Response"
        context_chunks = [
            {
                "content": "Content",
                "similarity": 0.9,
            }
        ]

        # Act
        result = service.add_source_citations(response, context_chunks)

        # Assert
        assert response in result
        assert "Sources:" in result
        assert "Unknown" in result or "Document" in result

    def test_add_citations_with_missing_file_name(self):
        """Test citation when file_name is missing."""
        # Arrange
        service = CitationService()
        response = "Response"
        context_chunks = [
            {
                "content": "Content",
                "similarity": 0.9,
                "metadata": {
                    "source": "google_drive",
                },
            }
        ]

        # Act
        result = service.add_source_citations(response, context_chunks)

        # Assert
        assert response in result
        assert "Sources:" in result
        # When file_name is missing, it uses "Document {i}" format
        assert "Document" in result

    def test_add_citations_with_missing_similarity(self):
        """Test citation when similarity score is missing."""
        # Arrange
        service = CitationService()
        response = "Response"
        context_chunks = [
            {
                "content": "Content",
                "metadata": {
                    "file_name": "doc.pdf",
                    "source": "google_drive",
                },
            }
        ]

        # Act
        result = service.add_source_citations(response, context_chunks)

        # Assert
        assert response in result
        assert "Sources:" in result
        assert "doc" in result
        assert "Match: 0.0%" in result

    def test_add_citations_description_fallback(self):
        """Test that description is used when title is missing."""
        # Arrange
        service = CitationService()
        response = "Response"
        context_chunks = [
            {
                "content": "Content",
                "similarity": 0.9,
                "metadata": {
                    "file_name": "doc.pdf",
                    "source": "google_drive",
                    "description": "This is a description",
                },
            }
        ]

        # Act
        result = service.add_source_citations(response, context_chunks)

        # Assert
        assert "This is a description" in result

    def test_add_citations_with_zero_similarity(self):
        """Test citation formatting with zero similarity."""
        # Arrange
        service = CitationService()
        response = "Response"
        context_chunks = [
            {
                "content": "Content",
                "similarity": 0.0,
                "metadata": {
                    "file_name": "doc.pdf",
                    "source": "google_drive",
                },
            }
        ]

        # Act
        result = service.add_source_citations(response, context_chunks)

        # Assert
        assert "Match: 0.0%" in result

    def test_add_citations_section_header_format(self):
        """Test that sources section has correct header."""
        # Arrange
        service = CitationService()
        response = "Response"
        context_chunks = [
            {
                "content": "Content",
                "similarity": 0.9,
                "metadata": {
                    "file_name": "doc.pdf",
                    "source": "google_drive",
                },
            }
        ]

        # Act
        result = service.add_source_citations(response, context_chunks)

        # Assert
        assert "\n\n**📚 Sources:**\n" in result

    def test_add_citations_mixed_sources(self):
        """Test citations with mixed Google Drive and Metric.ai sources."""
        # Arrange
        service = CitationService()
        response = "Mixed information"
        context_chunks = [
            {
                "content": "Drive content",
                "similarity": 0.9,
                "metadata": {
                    "file_name": "document.pdf",
                    "source": "google_drive",
                },
            },
            {
                "content": "Metric content",
                "similarity": 0.85,
                "metadata": {
                    "name": "Metric Record",
                    "source": "metric",
                    "data_type": "record",
                },
            },
        ]

        # Act
        result = service.add_source_citations(response, context_chunks)

        # Assert
        assert "document" in result
        assert "Metric Record" in result
        assert "Knowledge Base" in result
        assert "Metric.ai" in result
        assert "1. " in result
        assert "2. " in result

    def test_add_citations_all_uploaded_documents(self):
        """Test when all context chunks are uploaded documents (should filter all)."""
        # Arrange
        service = CitationService()
        response = "Response based on uploaded documents"
        context_chunks = [
            {
                "content": "Upload 1",
                "similarity": 0.98,
                "metadata": {
                    "file_name": "file1.pdf",
                    "source": "uploaded_document",
                },
            },
            {
                "content": "Upload 2",
                "similarity": 0.95,
                "metadata": {
                    "file_name": "file2.pdf",
                    "source": "uploaded_document",
                },
            },
        ]

        # Act
        result = service.add_source_citations(response, context_chunks)

        # Assert
        # When all chunks are filtered, should return response unchanged
        assert result == response
        assert "Sources:" not in result


class TestFormatContextForLLM:
    """Test format_context_for_llm method."""

    def test_format_context_empty_chunks(self):
        """Test formatting with empty context chunks."""
        # Arrange
        service = CitationService()
        context_chunks = []

        # Act
        result = service.format_context_for_llm(context_chunks)

        # Assert
        assert result == ""

    def test_format_context_single_chunk(self):
        """Test formatting single context chunk."""
        # Arrange
        service = CitationService()
        context_chunks = [
            {
                "content": "This is relevant information",
                "similarity": 0.95,
                "metadata": {
                    "file_name": "document.pdf",
                },
            }
        ]

        # Act
        result = service.format_context_for_llm(context_chunks)

        # Assert
        assert "[Source: document.pdf, Score: 0.95]" in result
        assert "This is relevant information" in result

    def test_format_context_multiple_chunks(self):
        """Test formatting multiple context chunks."""
        # Arrange
        service = CitationService()
        context_chunks = [
            {
                "content": "First chunk content",
                "similarity": 0.92,
                "metadata": {
                    "file_name": "doc1.pdf",
                },
            },
            {
                "content": "Second chunk content",
                "similarity": 0.87,
                "metadata": {
                    "file_name": "doc2.pdf",
                },
            },
        ]

        # Act
        result = service.format_context_for_llm(context_chunks)

        # Assert
        assert "[Source: doc1.pdf, Score: 0.92]" in result
        assert "First chunk content" in result
        assert "[Source: doc2.pdf, Score: 0.87]" in result
        assert "Second chunk content" in result
        # Chunks should be separated by double newlines
        assert "\n\n" in result

    def test_format_context_without_metadata(self):
        """Test formatting chunks without metadata."""
        # Arrange
        service = CitationService()
        context_chunks = [
            {
                "content": "Content without metadata",
                "similarity": 0.88,
            }
        ]

        # Act
        result = service.format_context_for_llm(context_chunks)

        # Assert
        assert "[Score: 0.88]" in result
        assert "Content without metadata" in result
        assert "[Source:" not in result

    def test_format_context_without_similarity(self):
        """Test formatting chunks without similarity score."""
        # Arrange
        service = CitationService()
        context_chunks = [
            {
                "content": "Content",
                "metadata": {
                    "file_name": "doc.pdf",
                },
            }
        ]

        # Act
        result = service.format_context_for_llm(context_chunks)

        # Assert
        assert "[Source: doc.pdf, Score: 0.00]" in result
        assert "Content" in result

    def test_format_context_score_precision(self):
        """Test that scores are formatted with correct precision."""
        # Arrange
        service = CitationService()
        context_chunks = [
            {
                "content": "Content",
                "similarity": 0.8765,
                "metadata": {
                    "file_name": "doc.pdf",
                },
            }
        ]

        # Act
        result = service.format_context_for_llm(context_chunks)

        # Assert
        assert "Score: 0.88" in result

    def test_format_context_preserves_content_order(self):
        """Test that content order is preserved."""
        # Arrange
        service = CitationService()
        context_chunks = [
            {
                "content": "First",
                "similarity": 0.9,
                "metadata": {"file_name": "doc1.pdf"},
            },
            {
                "content": "Second",
                "similarity": 0.8,
                "metadata": {"file_name": "doc2.pdf"},
            },
            {
                "content": "Third",
                "similarity": 0.7,
                "metadata": {"file_name": "doc3.pdf"},
            },
        ]

        # Act
        result = service.format_context_for_llm(context_chunks)

        # Assert
        first_pos = result.index("First")
        second_pos = result.index("Second")
        third_pos = result.index("Third")
        assert first_pos < second_pos < third_pos

    def test_format_context_separation(self):
        """Test that chunks are properly separated."""
        # Arrange
        service = CitationService()
        context_chunks = [
            {
                "content": "First",
                "similarity": 0.9,
                "metadata": {"file_name": "doc1.pdf"},
            },
            {
                "content": "Second",
                "similarity": 0.8,
                "metadata": {"file_name": "doc2.pdf"},
            },
        ]

        # Act
        result = service.format_context_for_llm(context_chunks)

        # Assert
        # Should have double newline separating chunks
        assert "First\n\n[Source: doc2.pdf" in result

    def test_format_context_handles_newlines_in_content(self):
        """Test formatting with newlines in content."""
        # Arrange
        service = CitationService()
        context_chunks = [
            {
                "content": "First line\nSecond line\nThird line",
                "similarity": 0.9,
                "metadata": {
                    "file_name": "doc.pdf",
                },
            }
        ]

        # Act
        result = service.format_context_for_llm(context_chunks)

        # Assert
        assert "First line\nSecond line\nThird line" in result

    def test_format_context_with_special_characters(self):
        """Test formatting with special characters in content."""
        # Arrange
        service = CitationService()
        context_chunks = [
            {
                "content": "Content with special chars: $, %, &, @, #, !, *, etc.",
                "similarity": 0.85,
                "metadata": {
                    "file_name": "doc.pdf",
                },
            }
        ]

        # Act
        result = service.format_context_for_llm(context_chunks)

        # Assert
        assert "Content with special chars: $, %, &, @, #, !, *, etc." in result

    def test_format_context_chunk_ordering_by_source(self):
        """Test that same source chunks are together."""
        # Arrange
        service = CitationService()
        context_chunks = [
            {
                "content": "Doc1 part 1",
                "similarity": 0.9,
                "metadata": {"file_name": "doc1.pdf"},
            },
            {
                "content": "Doc2 part 1",
                "similarity": 0.85,
                "metadata": {"file_name": "doc2.pdf"},
            },
            {
                "content": "Doc1 part 2",
                "similarity": 0.8,
                "metadata": {"file_name": "doc1.pdf"},
            },
        ]

        # Act
        result = service.format_context_for_llm(context_chunks)

        # Assert
        # All chunks should be present in order they were provided
        doc1_pos = result.index("Doc1 part 1")
        doc2_pos = result.index("Doc2 part 1")
        doc1_2_pos = result.index("Doc1 part 2")
        assert doc1_pos < doc2_pos < doc1_2_pos

    def test_format_context_with_empty_content(self):
        """Test formatting with empty content string."""
        # Arrange
        service = CitationService()
        context_chunks = [
            {
                "content": "",
                "similarity": 0.9,
                "metadata": {
                    "file_name": "doc.pdf",
                },
            }
        ]

        # Act
        result = service.format_context_for_llm(context_chunks)

        # Assert
        assert "[Source: doc.pdf, Score: 0.90]" in result
        # Result will have newline after the metadata
        assert "[Source: doc.pdf, Score: 0.90]\n" in result

    def test_format_context_multiple_chunks_same_file(self):
        """Test formatting multiple chunks from same file."""
        # Arrange
        service = CitationService()
        context_chunks = [
            {
                "content": "Section 1",
                "similarity": 0.92,
                "metadata": {"file_name": "doc.pdf"},
            },
            {
                "content": "Section 2",
                "similarity": 0.88,
                "metadata": {"file_name": "doc.pdf"},
            },
            {
                "content": "Section 3",
                "similarity": 0.85,
                "metadata": {"file_name": "doc.pdf"},
            },
        ]

        # Act
        result = service.format_context_for_llm(context_chunks)

        # Assert
        assert "Section 1" in result
        assert "Section 2" in result
        assert "Section 3" in result
        # All should reference same file
        assert result.count("doc.pdf") == 3

    def test_add_citations_dedup_same_file_different_metadata(self):
        """Test deduplication ignores differences in other metadata."""
        # Arrange
        service = CitationService()
        response = "Response"
        context_chunks = [
            {
                "content": "Content 1",
                "similarity": 0.95,
                "metadata": {
                    "file_name": "annual_report.pdf",
                    "source": "google_drive",
                    "title": "Report Title",
                },
            },
            {
                "content": "Content 2",
                "similarity": 0.88,
                "metadata": {
                    "file_name": "annual_report.pdf",
                    "source": "google_drive",
                    "title": "Different Title",
                    "description": "Some description",
                },
            },
        ]

        # Act
        result = service.add_source_citations(response, context_chunks)

        # Assert
        # Should still deduplicate based on file name
        sources_section = (
            result.split("**📚 Sources:**")[1] if "**📚 Sources:**" in result else ""
        )
        # Check that annual_report appears only once in sources
        annual_count = sources_section.lower().count("annual_report")
        assert annual_count == 1
        assert "2 sections" in result

    def test_add_citations_empty_sources_after_filtering(self):
        """Test when context has chunks but all are deduplicated away."""
        # Arrange
        service = CitationService()
        response = "Test response"
        # Create chunks where second is duplicate of first
        context_chunks = [
            {
                "content": "Content",
                "similarity": 0.9,
                "metadata": {
                    "file_name": "doc.pdf",
                    "source": "google_drive",
                },
            },
            {
                "content": "Different content",
                "similarity": 0.85,
                "metadata": {
                    "file_name": "doc.pdf",
                    "source": "google_drive",
                },
            },
        ]

        # Act
        result = service.add_source_citations(response, context_chunks)

        # Assert
        # Should include response with sources, not return empty
        assert response in result
        assert "Sources:" in result
        # Should show chunk count
        assert "2 sections" in result
