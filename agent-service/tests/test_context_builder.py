"""Comprehensive tests for ContextBuilder service.

Tests cover:
- RAG prompt construction with context chunks
- Date context injection and current year handling
- Uploaded document vs retrieved chunk separation
- System message composition and formatting
- Conversation history integration
- Context quality validation
- Context summary formatting
- Error handling and edge cases
- Empty context scenarios
"""

import os
import sys
from datetime import datetime
from unittest.mock import MagicMock, patch

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.context_builder import ContextBuilder


class TestContextBuilderInitialization:
    """Test ContextBuilder initialization."""

    def test_initialization(self):
        """Test basic initialization."""
        # Arrange & Act
        builder = ContextBuilder()

        # Assert
        assert builder is not None
        assert isinstance(builder, ContextBuilder)


class TestBuildRAGPrompt:
    """Test build_rag_prompt method."""

    def test_build_prompt_with_no_context_no_system_message(self):
        """Test prompt building with no context and no system message."""
        # Arrange
        builder = ContextBuilder()
        query = "What is Python?"
        context_chunks = []
        conversation_history = []

        # Act
        system_message, messages = builder.build_rag_prompt(
            query, context_chunks, conversation_history
        )

        # Assert
        assert system_message is not None
        assert "Current Date Information" in system_message
        assert str(datetime.now().year) in system_message
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == query

    def test_build_prompt_with_system_message_no_context(self):
        """Test prompt building with custom system message but no context."""
        # Arrange
        builder = ContextBuilder()
        query = "What is Python?"
        context_chunks = []
        conversation_history = []
        custom_system_message = "You are a helpful assistant."

        # Act
        system_message, messages = builder.build_rag_prompt(
            query, context_chunks, conversation_history, custom_system_message
        )

        # Assert
        assert system_message is not None
        assert "You are a helpful assistant." in system_message
        assert "Current Date Information" in system_message
        assert str(datetime.now().year) in system_message
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == query

    def test_build_prompt_with_conversation_history(self):
        """Test prompt building with conversation history."""
        # Arrange
        builder = ContextBuilder()
        query = "What about JavaScript?"
        context_chunks = []
        conversation_history = [
            {"role": "user", "content": "Tell me about Python"},
            {"role": "assistant", "content": "Python is a programming language"},
        ]

        # Act
        system_message, messages = builder.build_rag_prompt(
            query, context_chunks, conversation_history
        )

        # Assert
        assert len(messages) == 3  # 2 history + 1 new query
        assert messages[0]["content"] == "Tell me about Python"
        assert messages[1]["content"] == "Python is a programming language"
        assert messages[2]["role"] == "user"
        assert messages[2]["content"] == query

    def test_build_prompt_preserves_conversation_history(self):
        """Test that original conversation history is not modified."""
        # Arrange
        builder = ContextBuilder()
        query = "New question"
        context_chunks = []
        original_history = [{"role": "user", "content": "Old question"}]
        conversation_history = original_history.copy()

        # Act
        _, messages = builder.build_rag_prompt(query, context_chunks, conversation_history)

        # Assert
        assert len(original_history) == 1  # Original not modified
        assert len(messages) == 2  # New messages list has original + new

    def test_build_prompt_with_retrieved_chunks(self):
        """Test prompt building with retrieved context chunks."""
        # Arrange
        builder = ContextBuilder()
        query = "What is Python?"
        context_chunks = [
            {
                "content": "Python is a high-level programming language",
                "similarity": 0.95,
                "metadata": {"file_name": "python_guide.pdf", "source": "knowledge_base"},
            },
            {
                "content": "Python was created by Guido van Rossum",
                "similarity": 0.87,
                "metadata": {"file_name": "python_history.pdf", "source": "knowledge_base"},
            },
        ]
        conversation_history = []

        # Act
        system_message, messages = builder.build_rag_prompt(
            query, context_chunks, conversation_history
        )

        # Assert
        assert system_message is not None
        assert "KNOWLEDGE BASE" in system_message
        assert "python_guide.pdf" in system_message
        assert "Score: 0.95" in system_message
        assert "Python is a high-level programming language" in system_message
        assert "python_history.pdf" in system_message
        assert "Score: 0.87" in system_message
        assert "Python was created by Guido van Rossum" in system_message
        assert "Use this context to answer the user's question" in system_message

    def test_build_prompt_with_uploaded_documents(self):
        """Test prompt building with uploaded document chunks."""
        # Arrange
        builder = ContextBuilder()
        query = "Analyze this document"
        context_chunks = [
            {
                "content": "This is the content of the uploaded PDF file.",
                "similarity": 1.0,
                "metadata": {"file_name": "report.pdf", "source": "uploaded_document"},
            }
        ]
        conversation_history = []

        # Act
        system_message, messages = builder.build_rag_prompt(
            query, context_chunks, conversation_history
        )

        # Assert
        assert system_message is not None
        assert "UPLOADED DOCUMENT" in system_message
        assert "Primary user content for analysis" in system_message
        assert "[Uploaded File: report.pdf]" in system_message
        assert "This is the content of the uploaded PDF file." in system_message

    def test_build_prompt_with_mixed_sources(self):
        """Test prompt building with both uploaded docs and retrieved chunks."""
        # Arrange
        builder = ContextBuilder()
        query = "Compare this document with knowledge base"
        context_chunks = [
            {
                "content": "Uploaded document content",
                "similarity": 1.0,
                "metadata": {"file_name": "upload.pdf", "source": "uploaded_document"},
            },
            {
                "content": "Knowledge base content",
                "similarity": 0.85,
                "metadata": {"file_name": "kb_doc.pdf", "source": "knowledge_base"},
            },
        ]
        conversation_history = []

        # Act
        system_message, messages = builder.build_rag_prompt(
            query, context_chunks, conversation_history
        )

        # Assert
        assert system_message is not None
        assert "UPLOADED DOCUMENT" in system_message
        assert "KNOWLEDGE BASE" in system_message
        # Uploaded should come before knowledge base
        uploaded_pos = system_message.index("UPLOADED DOCUMENT")
        kb_pos = system_message.index("KNOWLEDGE BASE")
        assert uploaded_pos < kb_pos

    def test_build_prompt_with_multiple_uploaded_documents(self):
        """Test prompt building with multiple uploaded documents."""
        # Arrange
        builder = ContextBuilder()
        query = "Summarize all documents"
        context_chunks = [
            {
                "content": "First document content",
                "similarity": 1.0,
                "metadata": {"file_name": "doc1.pdf", "source": "uploaded_document"},
            },
            {
                "content": "Second document content",
                "similarity": 1.0,
                "metadata": {"file_name": "doc2.pdf", "source": "uploaded_document"},
            },
        ]
        conversation_history = []

        # Act
        system_message, messages = builder.build_rag_prompt(
            query, context_chunks, conversation_history
        )

        # Assert
        assert "[Uploaded File: doc1.pdf]" in system_message
        assert "[Uploaded File: doc2.pdf]" in system_message
        assert "First document content" in system_message
        assert "Second document content" in system_message

    def test_build_prompt_date_context_format(self):
        """Test that date context is properly formatted."""
        # Arrange
        builder = ContextBuilder()
        query = "What's the news today?"
        context_chunks = []
        conversation_history = []

        # Act
        system_message, messages = builder.build_rag_prompt(
            query, context_chunks, conversation_history
        )

        # Assert
        current_date = datetime.now().strftime("%B %d, %Y")
        current_year = datetime.now().year
        assert f"Today's date: {current_date}" in system_message
        assert f"Current year: {current_year}" in system_message
        assert "web_search tool" in system_message
        assert "do NOT add years to search queries" in system_message

    def test_build_prompt_context_separation(self):
        """Test that context sections are properly separated."""
        # Arrange
        builder = ContextBuilder()
        query = "Test query"
        context_chunks = [
            {
                "content": "Uploaded content",
                "similarity": 1.0,
                "metadata": {"file_name": "upload.pdf", "source": "uploaded_document"},
            },
            {
                "content": "Retrieved content",
                "similarity": 0.8,
                "metadata": {"file_name": "kb.pdf", "source": "knowledge_base"},
            },
        ]
        conversation_history = []

        # Act
        system_message, messages = builder.build_rag_prompt(
            query, context_chunks, conversation_history
        )

        # Assert
        # Sections should be separated by ---
        assert "---" in system_message
        assert system_message.count("===") >= 2  # At least 2 section headers

    def test_build_prompt_source_citation_instruction(self):
        """Test that RAG instruction includes no inline citation guidance."""
        # Arrange
        builder = ContextBuilder()
        query = "Test query"
        context_chunks = [
            {
                "content": "Test content",
                "similarity": 0.9,
                "metadata": {"file_name": "test.pdf", "source": "knowledge_base"},
            }
        ]
        conversation_history = []

        # Act
        system_message, messages = builder.build_rag_prompt(
            query, context_chunks, conversation_history
        )

        # Assert
        assert "Do not add inline source citations like '[Source: ...]'" in system_message
        assert "complete source citations will be automatically added" in system_message

    def test_build_prompt_with_missing_metadata(self):
        """Test prompt building with chunks missing metadata."""
        # Arrange
        builder = ContextBuilder()
        query = "Test query"
        context_chunks = [
            {
                "content": "Content without metadata",
                "similarity": 0.9,
            }
        ]
        conversation_history = []

        # Act
        system_message, messages = builder.build_rag_prompt(
            query, context_chunks, conversation_history
        )

        # Assert
        assert system_message is not None
        assert "Content without metadata" in system_message
        # Should handle missing metadata gracefully
        assert "[Source: Unknown" in system_message or "KNOWLEDGE BASE" in system_message

    def test_build_prompt_with_missing_file_name(self):
        """Test prompt building with chunks missing file_name."""
        # Arrange
        builder = ContextBuilder()
        query = "Test query"
        context_chunks = [
            {
                "content": "Content without file name",
                "similarity": 0.85,
                "metadata": {"source": "knowledge_base"},
            }
        ]
        conversation_history = []

        # Act
        system_message, messages = builder.build_rag_prompt(
            query, context_chunks, conversation_history
        )

        # Assert
        assert system_message is not None
        assert "Content without file name" in system_message
        assert "[Source: Unknown" in system_message

    def test_build_prompt_empty_query(self):
        """Test prompt building with empty query string."""
        # Arrange
        builder = ContextBuilder()
        query = ""
        context_chunks = []
        conversation_history = []

        # Act
        system_message, messages = builder.build_rag_prompt(
            query, context_chunks, conversation_history
        )

        # Assert
        assert system_message is not None
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == ""

    @patch("services.context_builder.datetime")
    def test_build_prompt_date_context_mocked(self, mock_datetime):
        """Test date context with mocked datetime."""
        # Arrange
        mock_now = MagicMock()
        mock_now.strftime.return_value = "January 15, 2025"
        mock_now.year = 2025
        mock_datetime.now.return_value = mock_now

        builder = ContextBuilder()
        query = "What year is it?"
        context_chunks = []
        conversation_history = []

        # Act
        system_message, messages = builder.build_rag_prompt(
            query, context_chunks, conversation_history
        )

        # Assert
        assert "Today's date: January 15, 2025" in system_message
        assert "Current year: 2025" in system_message


class TestFormatContextSummary:
    """Test format_context_summary method."""

    def test_format_summary_empty_chunks(self):
        """Test summary formatting with empty chunks."""
        # Arrange
        builder = ContextBuilder()
        context_chunks = []

        # Act
        summary = builder.format_context_summary(context_chunks)

        # Assert
        assert summary == "No context retrieved"

    def test_format_summary_single_chunk(self):
        """Test summary formatting with single chunk."""
        # Arrange
        builder = ContextBuilder()
        context_chunks = [
            {
                "content": "Test content",
                "similarity": 0.95,
                "metadata": {"file_name": "test.pdf"},
            }
        ]

        # Act
        summary = builder.format_context_summary(context_chunks)

        # Assert
        assert "Retrieved from 1 documents:" in summary
        assert "test.pdf" in summary
        assert "1 chunks" in summary
        assert "max score: 0.95" in summary

    def test_format_summary_multiple_chunks_same_source(self):
        """Test summary formatting with multiple chunks from same document."""
        # Arrange
        builder = ContextBuilder()
        context_chunks = [
            {
                "content": "Content 1",
                "similarity": 0.95,
                "metadata": {"file_name": "doc.pdf"},
            },
            {
                "content": "Content 2",
                "similarity": 0.87,
                "metadata": {"file_name": "doc.pdf"},
            },
            {
                "content": "Content 3",
                "similarity": 0.82,
                "metadata": {"file_name": "doc.pdf"},
            },
        ]

        # Act
        summary = builder.format_context_summary(context_chunks)

        # Assert
        assert "Retrieved from 1 documents:" in summary
        assert "doc.pdf" in summary
        assert "3 chunks" in summary
        assert "max score: 0.95" in summary  # Should show highest similarity

    def test_format_summary_multiple_sources(self):
        """Test summary formatting with multiple source documents."""
        # Arrange
        builder = ContextBuilder()
        context_chunks = [
            {
                "content": "Content A",
                "similarity": 0.90,
                "metadata": {"file_name": "doc1.pdf"},
            },
            {
                "content": "Content B",
                "similarity": 0.85,
                "metadata": {"file_name": "doc2.pdf"},
            },
            {
                "content": "Content C",
                "similarity": 0.95,
                "metadata": {"file_name": "doc1.pdf"},
            },
        ]

        # Act
        summary = builder.format_context_summary(context_chunks)

        # Assert
        assert "Retrieved from 2 documents:" in summary
        assert "doc1.pdf" in summary
        assert "doc2.pdf" in summary
        assert "2 chunks" in summary  # doc1.pdf has 2 chunks
        assert "1 chunks" in summary  # doc2.pdf has 1 chunk
        assert "max score: 0.95" in summary
        assert "max score: 0.85" in summary

    def test_format_summary_missing_metadata(self):
        """Test summary formatting with missing metadata."""
        # Arrange
        builder = ContextBuilder()
        context_chunks = [
            {
                "content": "Content without metadata",
                "similarity": 0.8,
            }
        ]

        # Act
        summary = builder.format_context_summary(context_chunks)

        # Assert
        assert "Retrieved from 1 documents:" in summary
        assert "Unknown" in summary
        assert "1 chunks" in summary
        assert "max score: 0.80" in summary

    def test_format_summary_missing_file_name(self):
        """Test summary formatting with missing file_name."""
        # Arrange
        builder = ContextBuilder()
        context_chunks = [
            {
                "content": "Content",
                "similarity": 0.75,
                "metadata": {"source": "somewhere"},
            }
        ]

        # Act
        summary = builder.format_context_summary(context_chunks)

        # Assert
        assert "Unknown" in summary
        assert "max score: 0.75" in summary

    def test_format_summary_missing_similarity(self):
        """Test summary formatting with missing similarity score."""
        # Arrange
        builder = ContextBuilder()
        context_chunks = [
            {
                "content": "Content",
                "metadata": {"file_name": "test.pdf"},
            }
        ]

        # Act
        summary = builder.format_context_summary(context_chunks)

        # Assert
        assert "test.pdf" in summary
        assert "max score: 0.00" in summary  # Should default to 0


class TestValidateContextQuality:
    """Test validate_context_quality method."""

    def test_validate_quality_empty_chunks(self):
        """Test quality validation with empty chunks."""
        # Arrange
        builder = ContextBuilder()
        context_chunks = []

        # Act
        metrics = builder.validate_context_quality(context_chunks)

        # Assert
        assert metrics["quality_score"] == 0.0
        assert metrics["high_quality_chunks"] == 0
        assert metrics["avg_similarity"] == 0.0
        assert metrics["unique_sources"] == 0
        assert len(metrics["warnings"]) == 1
        assert "No context chunks provided" in metrics["warnings"]

    def test_validate_quality_high_quality_chunks(self):
        """Test quality validation with high-quality chunks."""
        # Arrange
        builder = ContextBuilder()
        context_chunks = [
            {
                "content": "High quality content 1",
                "similarity": 0.95,
                "metadata": {"file_name": "doc1.pdf"},
            },
            {
                "content": "High quality content 2",
                "similarity": 0.87,
                "metadata": {"file_name": "doc2.pdf"},
            },
            {
                "content": "High quality content 3",
                "similarity": 0.82,
                "metadata": {"file_name": "doc3.pdf"},
            },
        ]

        # Act
        metrics = builder.validate_context_quality(context_chunks)

        # Assert
        assert metrics["high_quality_chunks"] == 3  # All above 0.5 threshold
        assert metrics["avg_similarity"] == (0.95 + 0.87 + 0.82) / 3
        assert metrics["unique_sources"] == 3
        assert metrics["quality_score"] > 0  # Should be positive
        assert len(metrics["warnings"]) == 0  # No warnings for good quality

    def test_validate_quality_mixed_quality_chunks(self):
        """Test quality validation with mixed quality chunks."""
        # Arrange
        builder = ContextBuilder()
        context_chunks = [
            {
                "content": "High quality",
                "similarity": 0.85,
                "metadata": {"file_name": "doc1.pdf"},
            },
            {
                "content": "Medium quality",
                "similarity": 0.45,
                "metadata": {"file_name": "doc2.pdf"},
            },
            {
                "content": "Low quality",
                "similarity": 0.25,
                "metadata": {"file_name": "doc3.pdf"},
            },
        ]

        # Act
        metrics = builder.validate_context_quality(context_chunks, min_similarity=0.5)

        # Assert
        assert metrics["high_quality_chunks"] == 1  # Only first above 0.5
        assert metrics["unique_sources"] == 3
        assert 0 < metrics["quality_score"] < 1

    def test_validate_quality_all_low_quality(self):
        """Test quality validation with all low-quality chunks."""
        # Arrange
        builder = ContextBuilder()
        context_chunks = [
            {
                "content": "Low quality 1",
                "similarity": 0.4,
                "metadata": {"file_name": "doc1.pdf"},
            },
            {
                "content": "Low quality 2",
                "similarity": 0.3,
                "metadata": {"file_name": "doc2.pdf"},
            },
        ]

        # Act
        metrics = builder.validate_context_quality(context_chunks, min_similarity=0.5)

        # Assert
        assert metrics["high_quality_chunks"] == 0
        assert "No high-quality chunks found" in metrics["warnings"]

    def test_validate_quality_single_source_warning(self):
        """Test quality validation warns about single source with many chunks."""
        # Arrange
        builder = ContextBuilder()
        context_chunks = [
            {
                "content": f"Content {i}",
                "similarity": 0.8,
                "metadata": {"file_name": "doc.pdf"},
            }
            for i in range(5)
        ]

        # Act
        metrics = builder.validate_context_quality(context_chunks)

        # Assert
        assert metrics["unique_sources"] == 1
        assert "All chunks from single source" in metrics["warnings"][0]

    def test_validate_quality_low_avg_similarity_warning(self):
        """Test quality validation warns about low average similarity."""
        # Arrange
        builder = ContextBuilder()
        context_chunks = [
            {
                "content": "Content 1",
                "similarity": 0.25,
                "metadata": {"file_name": "doc1.pdf"},
            },
            {
                "content": "Content 2",
                "similarity": 0.20,
                "metadata": {"file_name": "doc2.pdf"},
            },
        ]

        # Act
        metrics = builder.validate_context_quality(context_chunks)

        # Assert
        assert metrics["avg_similarity"] < 0.3
        assert any("Low average similarity" in w for w in metrics["warnings"])

    def test_validate_quality_custom_threshold(self):
        """Test quality validation with custom similarity threshold."""
        # Arrange
        builder = ContextBuilder()
        context_chunks = [
            {
                "content": "Content",
                "similarity": 0.65,
                "metadata": {"file_name": "doc.pdf"},
            }
        ]

        # Act
        metrics_low_threshold = builder.validate_context_quality(
            context_chunks, min_similarity=0.5
        )
        metrics_high_threshold = builder.validate_context_quality(
            context_chunks, min_similarity=0.7
        )

        # Assert
        assert metrics_low_threshold["high_quality_chunks"] == 1
        assert metrics_high_threshold["high_quality_chunks"] == 0

    def test_validate_quality_missing_similarity(self):
        """Test quality validation with missing similarity scores."""
        # Arrange
        builder = ContextBuilder()
        context_chunks = [
            {
                "content": "Content without similarity",
                "metadata": {"file_name": "doc.pdf"},
            }
        ]

        # Act
        metrics = builder.validate_context_quality(context_chunks)

        # Assert
        assert metrics["avg_similarity"] == 0.0
        assert metrics["high_quality_chunks"] == 0

    def test_validate_quality_missing_metadata(self):
        """Test quality validation with missing metadata."""
        # Arrange
        builder = ContextBuilder()
        context_chunks = [
            {
                "content": "Content",
                "similarity": 0.8,
            }
        ]

        # Act
        metrics = builder.validate_context_quality(context_chunks)

        # Assert
        assert metrics["unique_sources"] == 1  # Should count "Unknown" as a source
        assert metrics["high_quality_chunks"] == 1

    def test_validate_quality_score_calculation(self):
        """Test quality score calculation formula."""
        # Arrange
        builder = ContextBuilder()
        context_chunks = [
            {
                "content": "High quality 1",
                "similarity": 0.9,
                "metadata": {"file_name": "doc1.pdf"},
            },
            {
                "content": "High quality 2",
                "similarity": 0.8,
                "metadata": {"file_name": "doc2.pdf"},
            },
        ]

        # Act
        metrics = builder.validate_context_quality(context_chunks, min_similarity=0.5)

        # Assert
        # Quality score = (high_quality_count / total_chunks) * avg_similarity
        expected_score = (2 / 2) * ((0.9 + 0.8) / 2)
        assert abs(metrics["quality_score"] - expected_score) < 0.01

    def test_validate_quality_multiple_warnings(self):
        """Test quality validation can return multiple warnings."""
        # Arrange
        builder = ContextBuilder()
        context_chunks = [
            {
                "content": f"Low quality content {i}",
                "similarity": 0.25,
                "metadata": {"file_name": "doc.pdf"},
            }
            for i in range(5)
        ]

        # Act
        metrics = builder.validate_context_quality(context_chunks, min_similarity=0.5)

        # Assert
        assert len(metrics["warnings"]) >= 2
        assert any("No high-quality chunks" in w for w in metrics["warnings"])
        assert any("single source" in w for w in metrics["warnings"])
        assert any("Low average similarity" in w for w in metrics["warnings"])
