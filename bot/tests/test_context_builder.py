"""
Tests for ContextBuilder service.

Tests context building, prompt engineering, and context formatting functionality.
"""

from unittest.mock import patch

import pytest

from bot.services.context_builder import ContextBuilder


class TestContextBuilder:
    """Test cases for ContextBuilder service"""

    @pytest.fixture
    def context_builder(self):
        """Create a ContextBuilder instance for testing"""
        return ContextBuilder()

    @pytest.fixture
    def sample_context_chunks(self):
        """Sample context chunks for testing"""
        return [
            {
                "content": "This is chunk 1 content",
                "similarity": 0.85,
                "metadata": {"file_name": "doc1.pdf", "page": 1},
            },
            {
                "content": "This is chunk 2 content",
                "similarity": 0.75,
                "metadata": {"file_name": "doc2.pdf", "page": 2},
            },
            {
                "content": "This is chunk 3 content",
                "similarity": 0.65,
                "metadata": {"file_name": "doc1.pdf", "page": 3},
            },
        ]

    @pytest.fixture
    def conversation_history(self):
        """Sample conversation history for testing"""
        return [
            {"role": "user", "content": "Previous question"},
            {"role": "assistant", "content": "Previous answer"},
        ]

    def test_build_rag_prompt_with_context(
        self, context_builder, sample_context_chunks, conversation_history
    ):
        """Test building RAG prompt with context chunks"""
        query = "What is the main topic?"
        system_message = "You are a helpful assistant."

        system_msg, messages = context_builder.build_rag_prompt(
            query, sample_context_chunks, conversation_history, system_message
        )

        # Check system message contains context
        assert "Use the following context to answer" in system_msg
        assert "You are a helpful assistant." in system_msg
        assert "doc1.pdf" in system_msg
        assert "doc2.pdf" in system_msg
        assert "Score: 0.85" in system_msg

        # Check messages structure
        assert len(messages) == 3  # history + new query
        assert messages[-1]["role"] == "user"
        assert messages[-1]["content"] == query

    def test_build_rag_prompt_without_context(
        self, context_builder, conversation_history
    ):
        """Test building prompt without context chunks"""
        query = "What is the main topic?"
        system_message = "You are a helpful assistant."

        system_msg, messages = context_builder.build_rag_prompt(
            query, [], conversation_history, system_message
        )

        # Check system message is unchanged
        assert system_msg == system_message
        assert "Use the following context" not in system_msg

        # Check messages structure
        assert len(messages) == 3
        assert messages[-1]["role"] == "user"
        assert messages[-1]["content"] == query

    def test_build_rag_prompt_no_system_message(
        self, context_builder, sample_context_chunks, conversation_history
    ):
        """Test building RAG prompt without initial system message"""
        query = "What is the main topic?"

        system_msg, messages = context_builder.build_rag_prompt(
            query, sample_context_chunks, conversation_history, None
        )

        # Check system message is just the RAG instruction
        assert system_msg.startswith("Use the following context to answer")
        assert "doc1.pdf" in system_msg

        # Check messages structure
        assert len(messages) == 3
        assert messages[-1]["role"] == "user"
        assert messages[-1]["content"] == query

    def test_build_rag_prompt_chunks_without_metadata(
        self, context_builder, conversation_history
    ):
        """Test building prompt with chunks that have no metadata"""
        chunks = [
            {"content": "Content without metadata", "similarity": 0.8},
            {"content": "Another content", "similarity": 0.7, "metadata": {}},
        ]
        query = "Test query"

        system_msg, messages = context_builder.build_rag_prompt(
            query, chunks, conversation_history, None
        )

        # Check that chunks without metadata are handled gracefully
        assert "Score: 0.80" in system_msg
        assert "Score: 0.70" in system_msg
        # The content should not have actual source citations (only scores)
        content_section = (
            system_msg.split("Context:\n")[1] if "Context:\n" in system_msg else ""
        )
        assert "[Source: Unknown" in content_section or "Score:" in content_section

    def test_format_context_summary_with_context(
        self, context_builder, sample_context_chunks
    ):
        """Test formatting context summary with chunks"""
        summary = context_builder.format_context_summary(sample_context_chunks)

        assert "Retrieved from 2 documents:" in summary
        assert "doc1.pdf" in summary
        assert "doc2.pdf" in summary
        assert "2 chunks" in summary  # doc1.pdf has 2 chunks
        assert "1 chunks" in summary  # doc2.pdf has 1 chunk
        assert "max score: 0.85" in summary

    def test_format_context_summary_empty(self, context_builder):
        """Test formatting context summary with no chunks"""
        summary = context_builder.format_context_summary([])
        assert summary == "No context retrieved"

    def test_format_context_summary_no_metadata(self, context_builder):
        """Test formatting context summary with chunks without metadata"""
        chunks = [
            {"content": "Content 1", "similarity": 0.8},
            {"content": "Content 2", "similarity": 0.7, "metadata": {}},
        ]

        summary = context_builder.format_context_summary(chunks)
        assert "Unknown" in summary
        assert "2 chunks" in summary

    def test_validate_context_quality_high_quality(
        self, context_builder, sample_context_chunks
    ):
        """Test context quality validation with high-quality chunks"""
        metrics = context_builder.validate_context_quality(
            sample_context_chunks, min_similarity=0.6
        )

        assert metrics["quality_score"] > 0.5
        assert metrics["high_quality_chunks"] == 3  # All chunks above 0.6
        assert metrics["avg_similarity"] == pytest.approx(0.75, rel=1e-2)
        assert metrics["unique_sources"] == 2
        assert len(metrics["warnings"]) == 0

    def test_validate_context_quality_low_quality(self, context_builder):
        """Test context quality validation with low-quality chunks"""
        low_quality_chunks = [
            {
                "content": "Content 1",
                "similarity": 0.2,
                "metadata": {"file_name": "doc1.pdf"},
            },
            {
                "content": "Content 2",
                "similarity": 0.3,
                "metadata": {"file_name": "doc1.pdf"},
            },
        ]

        metrics = context_builder.validate_context_quality(
            low_quality_chunks, min_similarity=0.5
        )

        assert metrics["quality_score"] < 0.3
        assert metrics["high_quality_chunks"] == 0
        assert metrics["avg_similarity"] == pytest.approx(0.25, rel=1e-2)
        assert metrics["unique_sources"] == 1
        assert "No high-quality chunks found" in metrics["warnings"]
        assert any(
            "Low average similarity" in warning for warning in metrics["warnings"]
        )

    def test_validate_context_quality_single_source_many_chunks(self, context_builder):
        """Test validation warning for many chunks from single source"""
        single_source_chunks = [
            {
                "content": f"Content {i}",
                "similarity": 0.7,
                "metadata": {"file_name": "doc1.pdf"},
            }
            for i in range(5)
        ]

        metrics = context_builder.validate_context_quality(
            single_source_chunks, min_similarity=0.5
        )

        assert metrics["unique_sources"] == 1
        assert any(
            "All chunks from single source" in warning
            for warning in metrics["warnings"]
        )

    def test_validate_context_quality_empty(self, context_builder):
        """Test context quality validation with no chunks"""
        metrics = context_builder.validate_context_quality([])

        assert metrics["quality_score"] == 0.0
        assert metrics["high_quality_chunks"] == 0
        assert metrics["avg_similarity"] == 0.0
        assert metrics["unique_sources"] == 0
        assert "No context chunks provided" in metrics["warnings"]

    def test_validate_context_quality_missing_similarity(self, context_builder):
        """Test validation with chunks missing similarity scores"""
        chunks = [
            {"content": "Content 1", "metadata": {"file_name": "doc1.pdf"}},
            {
                "content": "Content 2",
                "similarity": 0.8,
                "metadata": {"file_name": "doc2.pdf"},
            },
        ]

        metrics = context_builder.validate_context_quality(chunks, min_similarity=0.5)

        # Should handle missing similarity gracefully (defaults to 0)
        assert metrics["avg_similarity"] == pytest.approx(0.4, rel=1e-2)
        assert metrics["high_quality_chunks"] == 1

    @patch("bot.services.context_builder.logger")
    def test_logging_with_context(
        self, mock_logger, context_builder, sample_context_chunks, conversation_history
    ):
        """Test that appropriate logging occurs when using context"""
        query = "Test query"

        context_builder.build_rag_prompt(
            query, sample_context_chunks, conversation_history, None
        )

        mock_logger.info.assert_called_with("🔍 Using RAG with 3 context chunks")

    @patch("bot.services.context_builder.logger")
    def test_logging_without_context(
        self, mock_logger, context_builder, conversation_history
    ):
        """Test that appropriate logging occurs when not using context"""
        query = "Test query"

        context_builder.build_rag_prompt(query, [], conversation_history, None)

        mock_logger.info.assert_called_with(
            "🤖 No relevant context found, using LLM knowledge only"
        )
