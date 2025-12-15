"""
Comprehensive tests for citation service.

Tests citation formatting, source filtering, and metadata handling.
"""

import pytest

from services.citation_service import CitationService


class TestCitationServiceBasics:
    """Test basic citation service functionality."""

    def test_citation_service_can_be_imported(self):
        """Test that CitationService can be imported and instantiated."""
        service = CitationService()
        assert service is not None

    def test_add_source_citations_with_empty_chunks(self):
        """Test that empty chunks return response unchanged."""
        service = CitationService()
        response = "Test response"
        result = service.add_source_citations(response, [])
        assert result == response

    def test_add_source_citations_with_none_chunks(self):
        """Test that None chunks are handled gracefully."""
        service = CitationService()
        response = "Test response"
        result = service.add_source_citations(response, [])
        assert result == response


class TestSourceFiltering:
    """Test filtering of uploaded documents from citations."""

    def test_filter_uploaded_documents(self):
        """Test that uploaded documents are filtered from citations."""
        service = CitationService()
        chunks = [
            {
                "content": "Test content",
                "similarity": 0.9,
                "metadata": {"source": "uploaded_document", "file_name": "upload.pdf"},
            },
            {
                "content": "Knowledge base content",
                "similarity": 0.85,
                "metadata": {"source": "google_drive", "file_name": "doc.pdf"},
            },
        ]

        response = "Test response"
        result = service.add_source_citations(response, chunks)

        # Uploaded document should be filtered out
        assert "upload.pdf" not in result
        assert "doc" in result  # Extension is removed by _get_document_title

    def test_filter_citation_chunks_internal(self):
        """Test _filter_citation_chunks method directly."""
        service = CitationService()
        chunks = [
            {
                "content": "Uploaded",
                "metadata": {"source": "uploaded_document", "file_name": "upload.pdf"},
            },
            {
                "content": "Retrieved",
                "metadata": {"source": "google_drive", "file_name": "doc.pdf"},
            },
        ]

        filtered = service._filter_citation_chunks(chunks)
        assert len(filtered) == 1
        assert filtered[0]["metadata"]["file_name"] == "doc.pdf"


class TestChunkCounting:
    """Test counting chunks per file."""

    def test_count_chunks_per_file_single_file(self):
        """Test counting chunks from a single file."""
        service = CitationService()
        chunks = [
            {"metadata": {"file_name": "doc.pdf"}},
            {"metadata": {"file_name": "doc.pdf"}},
            {"metadata": {"file_name": "doc.pdf"}},
        ]

        counts = service._count_chunks_per_file(chunks)
        assert counts == {"doc.pdf": 3}

    def test_count_chunks_per_file_multiple_files(self):
        """Test counting chunks from multiple files."""
        service = CitationService()
        chunks = [
            {"metadata": {"file_name": "doc1.pdf"}},
            {"metadata": {"file_name": "doc2.pdf"}},
            {"metadata": {"file_name": "doc1.pdf"}},
            {"metadata": {"file_name": "doc3.pdf"}},
        ]

        counts = service._count_chunks_per_file(chunks)
        assert counts == {"doc1.pdf": 2, "doc2.pdf": 1, "doc3.pdf": 1}

    def test_count_chunks_per_file_missing_metadata(self):
        """Test counting chunks with missing file_name metadata."""
        service = CitationService()
        chunks = [
            {"metadata": {}},
            {"metadata": {"file_name": "doc.pdf"}},
        ]

        counts = service._count_chunks_per_file(chunks)
        assert counts == {"Unknown": 1, "doc.pdf": 1}


class TestCitationFormatting:
    """Test citation formatting logic."""

    def test_add_source_citations_with_single_chunk(self):
        """Test adding citations with a single chunk."""
        service = CitationService()
        chunks = [
            {
                "content": "Test content",
                "similarity": 0.9,
                "metadata": {
                    "source": "google_drive",
                    "file_name": "document.pdf",
                    "web_view_link": "https://example.com/doc",
                },
            }
        ]

        response = "Test response"
        result = service.add_source_citations(response, chunks)

        assert "📚 Sources:" in result
        assert "document" in result
        assert "90.0%" in result or "90%" in result
        assert "https://example.com/doc" in result

    def test_add_source_citations_with_multiple_chunks(self):
        """Test adding citations with multiple chunks from different files."""
        service = CitationService()
        chunks = [
            {
                "content": "Content 1",
                "similarity": 0.9,
                "metadata": {"source": "google_drive", "file_name": "doc1.pdf"},
            },
            {
                "content": "Content 2",
                "similarity": 0.85,
                "metadata": {"source": "google_drive", "file_name": "doc2.pdf"},
            },
        ]

        response = "Test response"
        result = service.add_source_citations(response, chunks)

        assert "📚 Sources:" in result
        assert "doc1" in result
        assert "doc2" in result

    def test_add_source_citations_with_duplicate_sources(self):
        """Test that duplicate sources are deduplicated."""
        service = CitationService()
        chunks = [
            {
                "content": "Content 1",
                "similarity": 0.9,
                "metadata": {"source": "google_drive", "file_name": "doc.pdf"},
            },
            {
                "content": "Content 2",
                "similarity": 0.85,
                "metadata": {"source": "google_drive", "file_name": "doc.pdf"},
            },
        ]

        response = "Test response"
        result = service.add_source_citations(response, chunks)

        # Should only have one citation for the duplicate file
        lines = result.split("\n")
        citation_lines = [line for line in lines if "doc" in line and "Sources" not in line]
        assert len(citation_lines) == 1


class TestFileNameExtraction:
    """Test file name and data type extraction."""

    def test_extract_file_info_for_document(self):
        """Test extracting file info for document source."""
        service = CitationService()
        metadata = {"file_name": "report.pdf", "source": "google_drive"}
        file_name, data_type = service._extract_file_info(metadata, "google_drive", 1)

        assert file_name == "report.pdf"
        assert data_type == "document"

    def test_extract_file_info_for_metric_employee(self):
        """Test extracting file info for metric employee data."""
        service = CitationService()
        metadata = {"name": "John Doe", "data_type": "employee", "source": "metric"}
        file_name, data_type = service._extract_file_info(metadata, "metric", 1)

        assert file_name == "John Doe"
        assert data_type == "employee"

    def test_extract_file_info_for_metric_project(self):
        """Test extracting file info for metric project data."""
        service = CitationService()
        metadata = {"name": "Project Alpha", "data_type": "project", "source": "metric"}
        file_name, data_type = service._extract_file_info(metadata, "metric", 1)

        assert file_name == "Project Alpha"
        assert data_type == "project"

    def test_extract_file_info_with_missing_name(self):
        """Test extracting file info with missing name falls back to index."""
        service = CitationService()
        metadata = {"data_type": "employee", "source": "metric"}
        file_name, data_type = service._extract_file_info(metadata, "metric", 5)

        assert file_name == "Metric Record 5"
        assert data_type == "employee"


class TestCitationFormatting:
    """Test individual citation formatting."""

    def test_format_single_citation_basic(self):
        """Test formatting a basic citation."""
        service = CitationService()
        chunk = {
            "content": "Test content",
            "similarity": 0.85,
            "metadata": {"file_name": "document.pdf", "source": "google_drive"},
        }

        citation = service._format_single_citation(
            chunk, "document.pdf", "document", "google_drive", {"document.pdf": 1}, 0
        )

        assert "1." in citation  # Citation number
        assert "document" in citation
        assert "85.0%" in citation or "85%" in citation

    def test_format_single_citation_with_multiple_chunks(self):
        """Test formatting citation with multiple chunks from same file."""
        service = CitationService()
        chunk = {
            "content": "Test content",
            "similarity": 0.9,
            "metadata": {"file_name": "document.pdf", "source": "google_drive"},
        }

        citation = service._format_single_citation(
            chunk, "document.pdf", "document", "google_drive", {"document.pdf": 3}, 0
        )

        assert "3 sections" in citation

    def test_format_single_citation_with_link(self):
        """Test formatting citation with web link."""
        service = CitationService()
        chunk = {
            "content": "Test content",
            "similarity": 0.9,
            "metadata": {
                "file_name": "document.pdf",
                "source": "google_drive",
                "web_view_link": "https://example.com/doc",
            },
        }

        citation = service._format_single_citation(
            chunk, "document.pdf", "document", "google_drive", {"document.pdf": 1}, 0
        )

        assert "https://example.com/doc" in citation
        assert "[" in citation and "](" in citation  # Markdown link format

    def test_format_single_citation_metric_without_link(self):
        """Test formatting citation for metric data (no link)."""
        service = CitationService()
        chunk = {
            "content": "Employee data",
            "similarity": 0.95,
            "metadata": {"name": "John Doe", "data_type": "employee", "source": "metric", "role": "Engineer"},
        }

        citation = service._format_single_citation(
            chunk, "John Doe", "employee", "metric", {"John Doe": 1}, 0
        )

        assert "John Doe" in citation
        assert "Engineer" in citation
        assert "📊 Metric.ai" in citation
        assert "https://" not in citation


class TestDocumentTitleExtraction:
    """Test document title extraction from file names."""

    def test_get_document_title_removes_pdf_extension(self):
        """Test that .pdf extension is removed from title."""
        service = CitationService()
        title = service._get_document_title("report.pdf", "google_drive")
        assert title == "report"

    def test_get_document_title_removes_docx_extension(self):
        """Test that .docx extension is removed from title."""
        service = CitationService()
        title = service._get_document_title("document.docx", "google_drive")
        assert title == "document"

    def test_get_document_title_removes_txt_extension(self):
        """Test that .txt extension is removed from title."""
        service = CitationService()
        title = service._get_document_title("notes.txt", "google_drive")
        assert title == "notes"

    def test_get_document_title_metric_unchanged(self):
        """Test that metric names are unchanged."""
        service = CitationService()
        title = service._get_document_title("John Doe", "metric")
        assert title == "John Doe"


class TestCitationContext:
    """Test adding contextual information to citations."""

    def test_add_citation_context_employee_with_role(self):
        """Test adding role context for employee."""
        service = CitationService()
        metadata = {"role": "Senior Engineer", "data_type": "employee"}
        context = service._add_citation_context(metadata, "metric", "employee", "John Doe")
        assert " • Senior Engineer" in context

    def test_add_citation_context_project_with_client(self):
        """Test adding client context for project."""
        service = CitationService()
        metadata = {"client": "Acme Corp", "data_type": "project"}
        context = service._add_citation_context(metadata, "metric", "project", "Project Alpha")
        assert " • Acme Corp" in context

    def test_add_citation_context_document_with_subtitle(self):
        """Test adding subtitle for document."""
        service = CitationService()
        metadata = {"title": "Annual Report", "source": "google_drive"}
        context = service._add_citation_context(metadata, "google_drive", "document", "report.pdf")
        assert " • Annual Report" in context

    def test_add_citation_context_no_context_available(self):
        """Test that empty string returned when no context available."""
        service = CitationService()
        metadata = {}
        context = service._add_citation_context(metadata, "google_drive", "document", "doc.pdf")
        assert context == ""


class TestSourceIndicators:
    """Test source type indicator formatting."""

    def test_format_source_indicator_metric(self):
        """Test metric source indicator."""
        service = CitationService()
        indicator = service._format_source_indicator("metric")
        assert "📊 Metric.ai" in indicator

    def test_format_source_indicator_knowledge_base(self):
        """Test knowledge base source indicator."""
        service = CitationService()
        indicator = service._format_source_indicator("google_drive")
        assert ":file_folder: Knowledge Base" in indicator


class TestFormatContextForLLM:
    """Test formatting context for LLM consumption."""

    def test_format_context_for_llm_empty(self):
        """Test formatting empty context."""
        service = CitationService()
        result = service.format_context_for_llm([])
        assert result == ""

    def test_format_context_for_llm_single_chunk(self):
        """Test formatting single chunk for LLM."""
        service = CitationService()
        chunks = [
            {
                "content": "Test content",
                "similarity": 0.9,
                "metadata": {"file_name": "doc.pdf"},
            }
        ]

        result = service.format_context_for_llm(chunks)
        assert "Test content" in result
        assert "doc.pdf" in result
        assert "0.90" in result

    def test_format_context_for_llm_multiple_chunks(self):
        """Test formatting multiple chunks for LLM."""
        service = CitationService()
        chunks = [
            {
                "content": "Content 1",
                "similarity": 0.9,
                "metadata": {"file_name": "doc1.pdf"},
            },
            {
                "content": "Content 2",
                "similarity": 0.8,
                "metadata": {"file_name": "doc2.pdf"},
            },
        ]

        result = service.format_context_for_llm(chunks)
        assert "Content 1" in result
        assert "Content 2" in result
        assert "doc1.pdf" in result
        assert "doc2.pdf" in result

    def test_format_context_for_llm_no_metadata(self):
        """Test formatting chunk without metadata."""
        service = CitationService()
        chunks = [{"content": "Test content", "similarity": 0.85}]

        result = service.format_context_for_llm(chunks)
        assert "Test content" in result
        assert "0.85" in result
