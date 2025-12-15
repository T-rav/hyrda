"""
Comprehensive tests for context builder service.

Tests context formatting, RAG prompt building, and quality validation.
"""

import pytest
from datetime import datetime
from unittest.mock import patch

from services.context_builder import ContextBuilder


class TestContextBuilderBasics:
    """Test basic context builder functionality."""

    def test_context_builder_can_be_imported(self):
        """Test that ContextBuilder can be imported and instantiated."""
        builder = ContextBuilder()
        assert builder is not None


class TestDateContext:
    """Test adding date context to system messages."""

    def test_add_date_context_to_existing_message(self):
        """Test adding date context to existing system message."""
        builder = ContextBuilder()
        system_msg = "You are a helpful assistant."
        result = builder._add_date_context(system_msg)

        assert "You are a helpful assistant." in result
        assert "Current Date Information" in result
        assert "Today's date:" in result
        assert "Current year:" in result
        assert str(datetime.now().year) in result

    def test_add_date_context_to_none_message(self):
        """Test adding date context when no system message exists."""
        builder = ContextBuilder()
        result = builder._add_date_context(None)

        assert "Current Date Information" in result
        assert "Today's date:" in result
        assert str(datetime.now().year) in result

    @patch("services.context_builder.datetime")
    def test_add_date_context_with_specific_date(self, mock_datetime):
        """Test date context with specific mocked date."""
        builder = ContextBuilder()
        mock_now = datetime(2024, 6, 15, 10, 30)
        mock_datetime.now.return_value = mock_now

        result = builder._add_date_context(None)

        assert "June 15, 2024" in result
        assert "2024" in result


class TestSeparateChunks:
    """Test separating uploaded documents from retrieved chunks."""

    def test_separate_chunks_all_uploaded(self):
        """Test separating when all chunks are uploaded documents."""
        builder = ContextBuilder()
        chunks = [
            {
                "content": "Upload 1",
                "metadata": {"source": "uploaded_document", "file_name": "doc1.pdf"},
            },
            {
                "content": "Upload 2",
                "metadata": {"source": "uploaded_document", "file_name": "doc2.pdf"},
            },
        ]

        uploaded, retrieved = builder._separate_chunks(chunks)
        assert len(uploaded) == 2
        assert len(retrieved) == 0

    def test_separate_chunks_all_retrieved(self):
        """Test separating when all chunks are from knowledge base."""
        builder = ContextBuilder()
        chunks = [
            {
                "content": "Retrieved 1",
                "metadata": {"source": "google_drive", "file_name": "doc1.pdf"},
            },
            {
                "content": "Retrieved 2",
                "metadata": {"source": "vector_db", "file_name": "doc2.pdf"},
            },
        ]

        uploaded, retrieved = builder._separate_chunks(chunks)
        assert len(uploaded) == 0
        assert len(retrieved) == 2

    def test_separate_chunks_mixed(self):
        """Test separating mixed uploaded and retrieved chunks."""
        builder = ContextBuilder()
        chunks = [
            {
                "content": "Upload",
                "metadata": {"source": "uploaded_document", "file_name": "upload.pdf"},
            },
            {
                "content": "Retrieved",
                "metadata": {"source": "google_drive", "file_name": "retrieved.pdf"},
            },
        ]

        uploaded, retrieved = builder._separate_chunks(chunks)
        assert len(uploaded) == 1
        assert len(retrieved) == 1
        assert uploaded[0]["metadata"]["file_name"] == "upload.pdf"
        assert retrieved[0]["metadata"]["file_name"] == "retrieved.pdf"

    def test_separate_chunks_empty(self):
        """Test separating empty chunk list."""
        builder = ContextBuilder()
        uploaded, retrieved = builder._separate_chunks([])
        assert len(uploaded) == 0
        assert len(retrieved) == 0


class TestFormatUploadedDocs:
    """Test formatting uploaded document chunks."""

    def test_format_uploaded_docs_single(self):
        """Test formatting a single uploaded document."""
        builder = ContextBuilder()
        chunks = [
            {
                "content": "Uploaded content",
                "metadata": {"file_name": "upload.pdf"},
            }
        ]

        result = builder._format_uploaded_docs(chunks)
        assert "[Uploaded File: upload.pdf]" in result
        assert "Uploaded content" in result

    def test_format_uploaded_docs_multiple(self):
        """Test formatting multiple uploaded documents."""
        builder = ContextBuilder()
        chunks = [
            {"content": "Content 1", "metadata": {"file_name": "doc1.pdf"}},
            {"content": "Content 2", "metadata": {"file_name": "doc2.pdf"}},
        ]

        result = builder._format_uploaded_docs(chunks)
        assert "[Uploaded File: doc1.pdf]" in result
        assert "[Uploaded File: doc2.pdf]" in result
        assert "Content 1" in result
        assert "Content 2" in result

    def test_format_uploaded_docs_missing_filename(self):
        """Test formatting uploaded doc with missing filename."""
        builder = ContextBuilder()
        chunks = [{"content": "Content", "metadata": {}}]

        result = builder._format_uploaded_docs(chunks)
        assert "[Uploaded File: uploaded_document]" in result
        assert "Content" in result


class TestFormatRetrievedChunks:
    """Test formatting RAG-retrieved chunks."""

    def test_format_retrieved_chunks_single(self):
        """Test formatting a single retrieved chunk."""
        builder = ContextBuilder()
        chunks = [
            {
                "content": "Retrieved content",
                "similarity": 0.85,
                "metadata": {"file_name": "doc.pdf"},
            }
        ]

        result = builder._format_retrieved_chunks(chunks)
        assert "[Source: doc.pdf, Score: 0.85]" in result
        assert "Retrieved content" in result

    def test_format_retrieved_chunks_multiple(self):
        """Test formatting multiple retrieved chunks."""
        builder = ContextBuilder()
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

        result = builder._format_retrieved_chunks(chunks)
        assert "[Source: doc1.pdf, Score: 0.90]" in result
        assert "[Source: doc2.pdf, Score: 0.80]" in result
        assert "Content 1" in result
        assert "Content 2" in result

    def test_format_retrieved_chunks_missing_metadata(self):
        """Test formatting chunk with missing metadata."""
        builder = ContextBuilder()
        chunks = [{"content": "Content", "similarity": 0.75}]

        result = builder._format_retrieved_chunks(chunks)
        assert "[Source: Unknown, Score: 0.75]" in result
        assert "Content" in result


class TestBuildContextSections:
    """Test building formatted context sections."""

    def test_build_context_sections_only_uploaded(self):
        """Test building context with only uploaded documents."""
        builder = ContextBuilder()
        chunks = [
            {
                "content": "Upload content",
                "metadata": {"source": "uploaded_document", "file_name": "doc.pdf"},
            }
        ]

        result = builder._build_context_sections(chunks)
        assert "UPLOADED DOCUMENT" in result
        assert "Primary user content for analysis" in result
        assert "Upload content" in result

    def test_build_context_sections_only_retrieved(self):
        """Test building context with only retrieved chunks."""
        builder = ContextBuilder()
        chunks = [
            {
                "content": "Retrieved content",
                "similarity": 0.85,
                "metadata": {"source": "google_drive", "file_name": "doc.pdf"},
            }
        ]

        result = builder._build_context_sections(chunks)
        assert "KNOWLEDGE BASE" in result
        assert "Retrieved relevant information" in result
        assert "Retrieved content" in result

    def test_build_context_sections_mixed(self):
        """Test building context with both uploaded and retrieved."""
        builder = ContextBuilder()
        chunks = [
            {
                "content": "Upload",
                "metadata": {"source": "uploaded_document", "file_name": "upload.pdf"},
            },
            {
                "content": "Retrieved",
                "similarity": 0.85,
                "metadata": {"source": "google_drive", "file_name": "kb.pdf"},
            },
        ]

        result = builder._build_context_sections(chunks)
        assert "UPLOADED DOCUMENT" in result
        assert "KNOWLEDGE BASE" in result
        assert "Upload" in result
        assert "Retrieved" in result


class TestBuildRAGInstruction:
    """Test building RAG instruction text."""

    def test_build_rag_instruction(self):
        """Test building RAG instruction with context."""
        builder = ContextBuilder()
        context = "[Source: doc.pdf]\nTest content"

        result = builder._build_rag_instruction(context)
        assert "You have access to relevant information" in result
        assert "Use this context to answer" in result
        assert "Test content" in result
        assert "Do not add inline source citations" in result


class TestBuildRAGPrompt:
    """Test building complete RAG prompts."""

    def test_build_rag_prompt_with_context(self):
        """Test building prompt with context chunks."""
        builder = ContextBuilder()
        query = "What is the company's revenue?"
        chunks = [
            {
                "content": "Revenue: $1M",
                "similarity": 0.9,
                "metadata": {"source": "google_drive", "file_name": "report.pdf"},
            }
        ]
        history = [{"role": "user", "content": "Hello"}]
        system_msg = "You are an assistant."

        system_result, messages = builder.build_rag_prompt(query, chunks, history, system_msg)

        assert "You are an assistant." in system_result
        assert "Current Date Information" in system_result
        assert "KNOWLEDGE BASE" in system_result
        assert "Revenue: $1M" in system_result
        assert len(messages) == 2  # History + new query
        assert messages[-1]["role"] == "user"
        assert messages[-1]["content"] == query

    def test_build_rag_prompt_without_context(self):
        """Test building prompt without context chunks."""
        builder = ContextBuilder()
        query = "What is 2+2?"
        history = []
        system_msg = "You are a math tutor."

        system_result, messages = builder.build_rag_prompt(query, [], history, system_msg)

        assert "You are a math tutor." in system_result
        assert "Current Date Information" in system_result
        assert "KNOWLEDGE BASE" not in system_result
        assert len(messages) == 1
        assert messages[0]["content"] == query

    def test_build_rag_prompt_without_system_message(self):
        """Test building prompt without system message."""
        builder = ContextBuilder()
        query = "Test query"
        chunks = []
        history = []

        system_result, messages = builder.build_rag_prompt(query, chunks, history, None)

        assert "Current Date Information" in system_result
        assert len(messages) == 1


class TestFormatContextSummary:
    """Test creating context summaries for logging."""

    def test_format_context_summary_empty(self):
        """Test formatting summary with no chunks."""
        builder = ContextBuilder()
        result = builder.format_context_summary([])
        assert result == "No context retrieved"

    def test_format_context_summary_single_file(self):
        """Test formatting summary with chunks from one file."""
        builder = ContextBuilder()
        chunks = [
            {
                "content": "Chunk 1",
                "similarity": 0.9,
                "metadata": {"file_name": "doc.pdf"},
            },
            {
                "content": "Chunk 2",
                "similarity": 0.85,
                "metadata": {"file_name": "doc.pdf"},
            },
        ]

        result = builder.format_context_summary(chunks)
        assert "Retrieved from 1 documents" in result
        assert "doc.pdf" in result
        assert "2 chunks" in result
        assert "0.90" in result  # Max similarity

    def test_format_context_summary_multiple_files(self):
        """Test formatting summary with chunks from multiple files."""
        builder = ContextBuilder()
        chunks = [
            {
                "content": "Chunk 1",
                "similarity": 0.9,
                "metadata": {"file_name": "doc1.pdf"},
            },
            {
                "content": "Chunk 2",
                "similarity": 0.85,
                "metadata": {"file_name": "doc2.pdf"},
            },
            {
                "content": "Chunk 3",
                "similarity": 0.8,
                "metadata": {"file_name": "doc1.pdf"},
            },
        ]

        result = builder.format_context_summary(chunks)
        assert "Retrieved from 2 documents" in result
        assert "doc1.pdf" in result
        assert "doc2.pdf" in result
        assert "2 chunks" in result  # doc1.pdf has 2 chunks

    def test_format_context_summary_missing_metadata(self):
        """Test formatting summary with missing file_name."""
        builder = ContextBuilder()
        chunks = [
            {"content": "Chunk", "similarity": 0.8, "metadata": {}},
        ]

        result = builder.format_context_summary(chunks)
        assert "Unknown" in result


class TestValidateContextQuality:
    """Test context quality validation."""

    def test_validate_context_quality_empty(self):
        """Test validating empty context."""
        builder = ContextBuilder()
        quality = builder.validate_context_quality([])

        assert quality["quality_score"] == 0.0
        assert quality["high_quality_chunks"] == 0
        assert quality["avg_similarity"] == 0.0
        assert quality["unique_sources"] == 0
        assert len(quality["warnings"]) > 0

    def test_validate_context_quality_high_quality(self):
        """Test validating high-quality context."""
        builder = ContextBuilder()
        chunks = [
            {
                "content": "Chunk 1",
                "similarity": 0.9,
                "metadata": {"file_name": "doc1.pdf"},
            },
            {
                "content": "Chunk 2",
                "similarity": 0.85,
                "metadata": {"file_name": "doc2.pdf"},
            },
        ]

        quality = builder.validate_context_quality(chunks, min_similarity=0.5)

        assert quality["quality_score"] > 0
        assert quality["high_quality_chunks"] == 2
        assert quality["avg_similarity"] > 0.8
        assert quality["unique_sources"] == 2
        assert len(quality["warnings"]) == 0

    def test_validate_context_quality_low_quality(self):
        """Test validating low-quality context."""
        builder = ContextBuilder()
        chunks = [
            {"content": "Chunk 1", "similarity": 0.2, "metadata": {"file_name": "doc.pdf"}},
            {"content": "Chunk 2", "similarity": 0.25, "metadata": {"file_name": "doc.pdf"}},
        ]

        quality = builder.validate_context_quality(chunks, min_similarity=0.5)

        assert quality["high_quality_chunks"] == 0
        assert quality["avg_similarity"] < 0.3
        assert "No high-quality chunks found" in quality["warnings"]
        assert any("Low average similarity" in w for w in quality["warnings"])

    def test_validate_context_quality_single_source(self):
        """Test validating context from single source."""
        builder = ContextBuilder()
        chunks = [
            {
                "content": f"Chunk {i}",
                "similarity": 0.8,
                "metadata": {"file_name": "doc.pdf"},
            }
            for i in range(5)
        ]

        quality = builder.validate_context_quality(chunks)

        assert quality["unique_sources"] == 1
        assert any("single source" in w for w in quality["warnings"])

    def test_validate_context_quality_custom_threshold(self):
        """Test validating with custom similarity threshold."""
        builder = ContextBuilder()
        chunks = [
            {"content": "Chunk 1", "similarity": 0.6, "metadata": {"file_name": "doc.pdf"}},
            {"content": "Chunk 2", "similarity": 0.4, "metadata": {"file_name": "doc.pdf"}},
        ]

        # With threshold 0.5
        quality = builder.validate_context_quality(chunks, min_similarity=0.5)
        assert quality["high_quality_chunks"] == 1

        # With threshold 0.7
        quality = builder.validate_context_quality(chunks, min_similarity=0.7)
        assert quality["high_quality_chunks"] == 0
