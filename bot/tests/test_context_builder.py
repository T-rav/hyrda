"""
Tests for ContextBuilder service using factory patterns.

Tests context building, prompt engineering, and context formatting functionality.
"""

from unittest.mock import patch

import pytest

from bot.services.context_builder import ContextBuilder


# TDD Factory Patterns for ContextBuilder Testing
class ContextBuilderFactory:
    """Factory for creating ContextBuilder instances"""

    @staticmethod
    def create_context_builder() -> ContextBuilder:
        """Create a ContextBuilder instance"""
        return ContextBuilder()


class ContextChunksFactory:
    """Factory for creating context chunks with different configurations"""

    @staticmethod
    def create_sample_chunks() -> list[dict]:
        """Create sample context chunks for testing"""
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

    @staticmethod
    def create_chunks_without_metadata() -> list[dict]:
        """Create chunks that have no metadata"""
        return [
            {"content": "Content without metadata", "similarity": 0.8},
            {"content": "Another content", "similarity": 0.7, "metadata": {}},
        ]

    @staticmethod
    def create_low_quality_chunks() -> list[dict]:
        """Create low-quality chunks for testing"""
        return [
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

    @staticmethod
    def create_single_source_chunks(count: int = 5) -> list[dict]:
        """Create multiple chunks from single source"""
        return [
            {
                "content": f"Content {i}",
                "similarity": 0.7,
                "metadata": {"file_name": "doc1.pdf"},
            }
            for i in range(count)
        ]

    @staticmethod
    def create_chunks_missing_similarity() -> list[dict]:
        """Create chunks with missing similarity scores"""
        return [
            {"content": "Content 1", "metadata": {"file_name": "doc1.pdf"}},
            {
                "content": "Content 2",
                "similarity": 0.8,
                "metadata": {"file_name": "doc2.pdf"},
            },
        ]

    @staticmethod
    def create_high_quality_chunks() -> list[dict]:
        """Create high-quality chunks for testing"""
        return [
            {
                "content": "High quality content 1",
                "similarity": 0.9,
                "metadata": {"file_name": "doc1.pdf", "page": 1},
            },
            {
                "content": "High quality content 2",
                "similarity": 0.85,
                "metadata": {"file_name": "doc2.pdf", "page": 1},
            },
            {
                "content": "High quality content 3",
                "similarity": 0.8,
                "metadata": {"file_name": "doc3.pdf", "page": 1},
            },
        ]


class ConversationHistoryFactory:
    """Factory for creating conversation history"""

    @staticmethod
    def create_sample_history() -> list[dict]:
        """Create sample conversation history"""
        return [
            {"role": "user", "content": "Previous question"},
            {"role": "assistant", "content": "Previous answer"},
        ]

    @staticmethod
    def create_long_history() -> list[dict]:
        """Create longer conversation history"""
        return [
            {"role": "user", "content": "First question"},
            {"role": "assistant", "content": "First answer"},
            {"role": "user", "content": "Second question"},
            {"role": "assistant", "content": "Second answer"},
            {"role": "user", "content": "Third question"},
            {"role": "assistant", "content": "Third answer"},
        ]

    @staticmethod
    def create_empty_history() -> list[dict]:
        """Create empty conversation history"""
        return []


class TestDataFactory:
    """Factory for creating test queries and system messages"""

    @staticmethod
    def create_query(query: str = "What is the main topic?") -> str:
        """Create test query"""
        return query

    @staticmethod
    def create_system_message(message: str = "You are a helpful assistant.") -> str:
        """Create system message"""
        return message

    @staticmethod
    def create_queries() -> list[str]:
        """Create multiple test queries"""
        return [
            "What is the main topic?",
            "How does this work?",
            "Can you explain the process?",
            "What are the key benefits?",
        ]


class TestContextBuilder:
    """Test cases for ContextBuilder service using factory patterns"""

    def test_build_rag_prompt_with_context(self):
        """Test building RAG prompt with context chunks"""
        context_builder = ContextBuilderFactory.create_context_builder()
        sample_context_chunks = ContextChunksFactory.create_sample_chunks()
        conversation_history = ConversationHistoryFactory.create_sample_history()
        query = TestDataFactory.create_query()
        system_message = TestDataFactory.create_system_message()

        system_msg, messages = context_builder.build_rag_prompt(
            query, sample_context_chunks, conversation_history, system_message
        )

        # Check system message contains context
        assert (
            "IMPORTANT: The user has uploaded a document for you to analyze"
            in system_msg
        )
        assert "You are a helpful assistant." in system_msg
        assert "doc1.pdf" in system_msg
        assert "doc2.pdf" in system_msg
        assert "Score: 0.85" in system_msg

        # Check messages structure
        assert len(messages) == 3  # history + new query
        assert messages[-1]["role"] == "user"
        assert messages[-1]["content"] == query

    def test_build_rag_prompt_without_context(self):
        """Test building prompt without context chunks"""
        context_builder = ContextBuilderFactory.create_context_builder()
        conversation_history = ConversationHistoryFactory.create_sample_history()
        query = TestDataFactory.create_query()
        system_message = TestDataFactory.create_system_message()

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

    def test_build_rag_prompt_no_system_message(self):
        """Test building RAG prompt without initial system message"""
        context_builder = ContextBuilderFactory.create_context_builder()
        sample_context_chunks = ContextChunksFactory.create_sample_chunks()
        conversation_history = ConversationHistoryFactory.create_sample_history()
        query = TestDataFactory.create_query()

        system_msg, messages = context_builder.build_rag_prompt(
            query, sample_context_chunks, conversation_history, None
        )

        # Check system message is just the RAG instruction
        assert system_msg.startswith(
            "IMPORTANT: The user has uploaded a document for you to analyze"
        )
        assert "doc1.pdf" in system_msg

        # Check messages structure
        assert len(messages) == 3
        assert messages[-1]["role"] == "user"
        assert messages[-1]["content"] == query

    def test_build_rag_prompt_chunks_without_metadata(self):
        """Test building prompt with chunks that have no metadata"""
        context_builder = ContextBuilderFactory.create_context_builder()
        chunks = ContextChunksFactory.create_chunks_without_metadata()
        conversation_history = ConversationHistoryFactory.create_sample_history()
        query = TestDataFactory.create_query("Test query")

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

    def test_build_rag_prompt_with_different_queries(self):
        """Test building RAG prompt with different queries"""
        context_builder = ContextBuilderFactory.create_context_builder()
        sample_context_chunks = ContextChunksFactory.create_sample_chunks()
        conversation_history = ConversationHistoryFactory.create_sample_history()
        queries = TestDataFactory.create_queries()
        system_message = TestDataFactory.create_system_message()

        for query in queries:
            system_msg, messages = context_builder.build_rag_prompt(
                query, sample_context_chunks, conversation_history, system_message
            )

            assert (
                "IMPORTANT: The user has uploaded a document for you to analyze"
                in system_msg
            )
            assert messages[-1]["content"] == query

    def test_format_context_summary_with_context(self):
        """Test formatting context summary with chunks"""
        context_builder = ContextBuilderFactory.create_context_builder()
        sample_context_chunks = ContextChunksFactory.create_sample_chunks()

        summary = context_builder.format_context_summary(sample_context_chunks)

        assert "Retrieved from 2 documents:" in summary
        assert "doc1.pdf" in summary
        assert "doc2.pdf" in summary
        assert "2 chunks" in summary  # doc1.pdf has 2 chunks
        assert "1 chunks" in summary  # doc2.pdf has 1 chunk
        assert "max score: 0.85" in summary

    def test_format_context_summary_empty(self):
        """Test formatting context summary with no chunks"""
        context_builder = ContextBuilderFactory.create_context_builder()
        summary = context_builder.format_context_summary([])
        assert summary == "No context retrieved"

    def test_format_context_summary_no_metadata(self):
        """Test formatting context summary with chunks without metadata"""
        context_builder = ContextBuilderFactory.create_context_builder()
        chunks = ContextChunksFactory.create_chunks_without_metadata()

        summary = context_builder.format_context_summary(chunks)
        assert "Unknown" in summary
        assert "2 chunks" in summary

    def test_format_context_summary_high_quality(self):
        """Test formatting context summary with high quality chunks"""
        context_builder = ContextBuilderFactory.create_context_builder()
        chunks = ContextChunksFactory.create_high_quality_chunks()

        summary = context_builder.format_context_summary(chunks)
        assert "Retrieved from 3 documents:" in summary
        assert "max score: 0.90" in summary

    def test_validate_context_quality_high_quality(self):
        """Test context quality validation with high-quality chunks"""
        context_builder = ContextBuilderFactory.create_context_builder()
        sample_context_chunks = ContextChunksFactory.create_sample_chunks()

        metrics = context_builder.validate_context_quality(
            sample_context_chunks, min_similarity=0.6
        )

        assert metrics["quality_score"] > 0.5
        assert metrics["high_quality_chunks"] == 3  # All chunks above 0.6
        assert metrics["avg_similarity"] == pytest.approx(0.75, rel=1e-2)
        assert metrics["unique_sources"] == 2
        assert len(metrics["warnings"]) == 0

    def test_validate_context_quality_low_quality(self):
        """Test context quality validation with low-quality chunks"""
        context_builder = ContextBuilderFactory.create_context_builder()
        low_quality_chunks = ContextChunksFactory.create_low_quality_chunks()

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

    def test_validate_context_quality_single_source_many_chunks(self):
        """Test validation warning for many chunks from single source"""
        context_builder = ContextBuilderFactory.create_context_builder()
        single_source_chunks = ContextChunksFactory.create_single_source_chunks()

        metrics = context_builder.validate_context_quality(
            single_source_chunks, min_similarity=0.5
        )

        assert metrics["unique_sources"] == 1
        assert any(
            "All chunks from single source" in warning
            for warning in metrics["warnings"]
        )

    def test_validate_context_quality_empty(self):
        """Test context quality validation with no chunks"""
        context_builder = ContextBuilderFactory.create_context_builder()
        metrics = context_builder.validate_context_quality([])

        assert metrics["quality_score"] == 0.0
        assert metrics["high_quality_chunks"] == 0
        assert metrics["avg_similarity"] == 0.0
        assert metrics["unique_sources"] == 0
        assert "No context chunks provided" in metrics["warnings"]

    def test_validate_context_quality_missing_similarity(self):
        """Test validation with chunks missing similarity scores"""
        context_builder = ContextBuilderFactory.create_context_builder()
        chunks = ContextChunksFactory.create_chunks_missing_similarity()

        metrics = context_builder.validate_context_quality(chunks, min_similarity=0.5)

        # Should handle missing similarity gracefully (defaults to 0)
        assert metrics["avg_similarity"] == pytest.approx(0.4, rel=1e-2)
        assert metrics["high_quality_chunks"] == 1

    def test_validate_context_quality_very_high_quality(self):
        """Test validation with very high quality chunks"""
        context_builder = ContextBuilderFactory.create_context_builder()
        chunks = ContextChunksFactory.create_high_quality_chunks()

        metrics = context_builder.validate_context_quality(chunks, min_similarity=0.7)

        assert metrics["quality_score"] > 0.8
        assert metrics["high_quality_chunks"] == 3
        assert metrics["unique_sources"] == 3
        assert len(metrics["warnings"]) == 0

    @patch("bot.services.context_builder.logger")
    def test_logging_with_context(self, mock_logger):
        """Test that appropriate logging occurs when using context"""
        context_builder = ContextBuilderFactory.create_context_builder()
        sample_context_chunks = ContextChunksFactory.create_sample_chunks()
        conversation_history = ConversationHistoryFactory.create_sample_history()
        query = TestDataFactory.create_query("Test query")

        context_builder.build_rag_prompt(
            query, sample_context_chunks, conversation_history, None
        )

        mock_logger.info.assert_called_with("🔍 Using RAG with 3 context chunks")

    @patch("bot.services.context_builder.logger")
    def test_logging_without_context(self, mock_logger):
        """Test that appropriate logging occurs when not using context"""
        context_builder = ContextBuilderFactory.create_context_builder()
        conversation_history = ConversationHistoryFactory.create_sample_history()
        query = TestDataFactory.create_query("Test query")

        context_builder.build_rag_prompt(query, [], conversation_history, None)

        mock_logger.info.assert_called_with(
            "🤖 No relevant context found, using LLM knowledge only"
        )

    def test_factories_create_consistent_data(self):
        """Test that factories create consistent test data"""
        # Test ContextChunksFactory
        sample_chunks = ContextChunksFactory.create_sample_chunks()
        assert len(sample_chunks) == 3
        assert all("content" in chunk for chunk in sample_chunks)
        assert all("similarity" in chunk for chunk in sample_chunks)

        # Test ConversationHistoryFactory
        history = ConversationHistoryFactory.create_sample_history()
        assert len(history) == 2
        assert all("role" in msg for msg in history)
        assert all("content" in msg for msg in history)

        # Test TestDataFactory
        query = TestDataFactory.create_query()
        assert isinstance(query, str)
        assert len(query) > 0

        queries = TestDataFactory.create_queries()
        assert len(queries) == 4
        assert all(isinstance(q, str) for q in queries)
