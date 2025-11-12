"""
Tests for uploaded document context delineation

These tests ensure that uploaded documents are properly separated from RAG-retrieved
chunks in the context builder, preventing regressions where the LLM might not
recognize uploaded document content.
"""

import os
import sys
from datetime import datetime

import pytest

# Add the parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.context_builder import ContextBuilder


class TestDataFactory:
    """Factory for creating test data"""

    @staticmethod
    def create_current_date_context() -> str:
        """Create current date context"""
        current_date = datetime.now().strftime("%B %d, %Y")
        current_year = datetime.now().year
        return f"**IMPORTANT - Current Date Information:**\n- Today's date: {current_date}\n- Current year: {current_year}\n- When using web_search tool, do NOT add years to search queries unless the user explicitly mentions a specific year. Use the current year ({current_year}) only if the user asks about 'this year' or 'current year'."


class TestUploadedDocumentDelineation:
    """Test that uploaded documents are properly delineated from RAG chunks"""

    def test_uploaded_document_section_created(self):
        """Test that uploaded documents get their own section in context"""
        builder = ContextBuilder()

        # Create mock chunks with uploaded document
        context_chunks = [
            {
                "content": "This is uploaded PDF content",
                "metadata": {
                    "file_name": "test.pdf",
                    "source": "uploaded_document",
                },
                "similarity": 1.0,
            }
        ]

        system_message, messages = builder.build_rag_prompt(
            query="What does the document say?",
            context_chunks=context_chunks,
            conversation_history=[],
            system_message="Base system message",
        )

        # Should contain UPLOADED DOCUMENT section marker
        assert "=== UPLOADED DOCUMENT" in system_message
        assert (
            "uploaded_document" not in system_message.lower()
            or "uploaded document" in system_message.lower()
        )
        assert "test.pdf" in system_message

    def test_uploaded_doc_and_rag_chunks_separated(self):
        """Test that uploaded docs and RAG chunks are clearly separated"""
        builder = ContextBuilder()

        context_chunks = [
            {
                "content": "Uploaded PDF content here",
                "metadata": {
                    "file_name": "user_upload.pdf",
                    "source": "uploaded_document",
                },
                "similarity": 1.0,
            },
            {
                "content": "Retrieved knowledge base content",
                "metadata": {
                    "file_name": "kb_doc.pdf",
                    "source": "google_drive",
                },
                "similarity": 0.85,
            },
        ]

        system_message, messages = builder.build_rag_prompt(
            query="What does this say?",
            context_chunks=context_chunks,
            conversation_history=[],
            system_message="Base system message",
        )

        # Should have both sections with clear separation
        assert "=== UPLOADED DOCUMENT" in system_message
        assert "=== KNOWLEDGE BASE" in system_message
        assert "---" in system_message  # Section divider
        assert "user_upload.pdf" in system_message
        assert "kb_doc.pdf" in system_message

        # Uploaded doc should come before knowledge base
        uploaded_pos = system_message.index("=== UPLOADED DOCUMENT")
        kb_pos = system_message.index("=== KNOWLEDGE BASE")
        assert uploaded_pos < kb_pos

    def test_only_rag_chunks_no_uploaded_section(self):
        """Test that when there's no uploaded doc, only knowledge base section appears"""
        builder = ContextBuilder()

        context_chunks = [
            {
                "content": "Knowledge base content",
                "metadata": {
                    "file_name": "doc1.pdf",
                    "source": "google_drive",
                },
                "similarity": 0.82,
            }
        ]

        system_message, messages = builder.build_rag_prompt(
            query="What is this about?",
            context_chunks=context_chunks,
            conversation_history=[],
            system_message="Base system message",
        )

        # Should NOT have uploaded document section
        assert "=== UPLOADED DOCUMENT" not in system_message
        # Should have knowledge base content
        assert "doc1.pdf" in system_message
        assert "Knowledge base content" in system_message

    def test_only_uploaded_doc_no_rag_section(self):
        """Test that when there's only uploaded doc, no knowledge base section appears"""
        builder = ContextBuilder()

        context_chunks = [
            {
                "content": "Only uploaded content here",
                "metadata": {
                    "file_name": "uploaded.pdf",
                    "source": "uploaded_document",
                },
                "similarity": 1.0,
            }
        ]

        system_message, messages = builder.build_rag_prompt(
            query="Analyze this",
            context_chunks=context_chunks,
            conversation_history=[],
            system_message="Base system message",
        )

        # Should have uploaded document section
        assert "=== UPLOADED DOCUMENT" in system_message
        # Should NOT have knowledge base section
        assert "=== KNOWLEDGE BASE" not in system_message
        assert "uploaded.pdf" in system_message

    def test_multiple_uploaded_doc_chunks(self):
        """Test handling multiple chunks from same uploaded document"""
        builder = ContextBuilder()

        context_chunks = [
            {
                "content": "First chunk of uploaded doc",
                "metadata": {
                    "file_name": "large_upload.pdf",
                    "source": "uploaded_document",
                    "chunk_id": "uploaded_doc_0",
                },
                "similarity": 1.0,
            },
            {
                "content": "Second chunk of uploaded doc",
                "metadata": {
                    "file_name": "large_upload.pdf",
                    "source": "uploaded_document",
                    "chunk_id": "uploaded_doc_1",
                },
                "similarity": 1.0,
            },
        ]

        system_message, messages = builder.build_rag_prompt(
            query="Summarize this document",
            context_chunks=context_chunks,
            conversation_history=[],
            system_message="Base system message",
        )

        # Should have uploaded document section
        assert "=== UPLOADED DOCUMENT" in system_message
        # Should contain both chunks
        assert "First chunk of uploaded doc" in system_message
        assert "Second chunk of uploaded doc" in system_message
        # Should mention the file name
        assert "large_upload.pdf" in system_message

    def test_uploaded_doc_context_is_primary(self):
        """Test that uploaded document is marked as primary content"""
        builder = ContextBuilder()

        context_chunks = [
            {
                "content": "User's uploaded document",
                "metadata": {
                    "file_name": "analysis.pdf",
                    "source": "uploaded_document",
                },
                "similarity": 1.0,
            }
        ]

        system_message, messages = builder.build_rag_prompt(
            query="What's in this?",
            context_chunks=context_chunks,
            conversation_history=[],
            system_message="Base system message",
        )

        # Should indicate it's primary content for analysis
        assert (
            "Primary user content" in system_message
            or "primary content" in system_message.lower()
        )

    def test_rag_instruction_without_uploaded_doc(self):
        """Test that RAG instruction is standard when no uploaded doc"""
        builder = ContextBuilder()

        context_chunks = [
            {
                "content": "Knowledge base content",
                "metadata": {"file_name": "kb_doc.pdf", "source": "google_drive"},
                "similarity": 0.8,
            }
        ]

        system_message, messages = builder.build_rag_prompt(
            query="Tell me about X",
            context_chunks=context_chunks,
            conversation_history=[],
            system_message="Base system message",
        )

        # Should contain standard RAG instruction
        assert "knowledge base" in system_message.lower()
        # Should reference the content
        assert "Knowledge base content" in system_message

    def test_empty_context_chunks(self):
        """Test behavior with no context chunks at all"""
        builder = ContextBuilder()

        system_message, messages = builder.build_rag_prompt(
            query="What is X?",
            context_chunks=[],
            conversation_history=[],
            system_message="Base system message",
        )
        current_date_context = TestDataFactory.create_current_date_context()

        # Should return base system message without RAG context
        assert system_message == f"Base system message\n\n{current_date_context}"
        # Should not have any section markers
        assert "=== UPLOADED DOCUMENT" not in system_message
        assert "=== KNOWLEDGE BASE" not in system_message

    def test_query_appended_to_messages(self):
        """Test that query is properly appended as user message"""
        builder = ContextBuilder()

        query = "What does the document say?"
        context_chunks = [
            {
                "content": "Doc content",
                "metadata": {"file_name": "test.pdf", "source": "uploaded_document"},
                "similarity": 1.0,
            }
        ]

        system_message, messages = builder.build_rag_prompt(
            query=query,
            context_chunks=context_chunks,
            conversation_history=[
                {"role": "user", "content": "Previous message"},
                {"role": "assistant", "content": "Previous response"},
            ],
            system_message="Base system message",
        )

        # Should have 3 messages: 2 history + 1 current query
        assert len(messages) == 3
        # Last message should be the current query
        assert messages[-1]["role"] == "user"
        assert messages[-1]["content"] == query

    def test_conversation_history_preserved(self):
        """Test that conversation history is preserved in messages"""
        builder = ContextBuilder()

        history = [
            {"role": "user", "content": "First question"},
            {"role": "assistant", "content": "First answer"},
            {"role": "user", "content": "Second question"},
            {"role": "assistant", "content": "Second answer"},
        ]

        system_message, messages = builder.build_rag_prompt(
            query="Third question",
            context_chunks=[],
            conversation_history=history,
            system_message="Base system message",
        )

        # Should have all history messages plus current query
        assert len(messages) == 5
        # First 4 should be history
        assert messages[:4] == history
        # Last should be current query
        assert messages[4] == {"role": "user", "content": "Third question"}


@pytest.mark.integration
class TestDocumentUploadIntegration:
    """Integration tests for end-to-end document upload flow"""

    def test_document_delineation_prevents_regression(self):
        """
        Regression test: Ensure uploaded documents are clearly marked
        so the LLM recognizes them as user-provided content.

        This test guards against the bug where uploaded documents were mixed
        with RAG chunks without clear delineation, causing the LLM to not
        recognize the uploaded content.
        """
        builder = ContextBuilder()

        # Simulate a user uploading a PDF with query "thoughts?"
        context_chunks = [
            {
                "content": "Feedback document content about Module 3",
                "metadata": {
                    "file_name": "Cohort 0 - Module 3 Feedback.pdf",
                    "source": "uploaded_document",
                },
                "similarity": 1.0,
            }
        ]

        system_message, messages = builder.build_rag_prompt(
            query="thoughts?",
            context_chunks=context_chunks,
            conversation_history=[],
            system_message="I'm an AI assistant.",
        )

        # Critical checks to prevent regression:
        # 1. Uploaded document must be clearly marked
        assert "=== UPLOADED DOCUMENT" in system_message

        # 2. Should indicate it's user-provided content
        assert (
            "Primary user content" in system_message
            or "user content" in system_message.lower()
        )

        # 3. Should contain the actual document name
        assert "Cohort 0 - Module 3 Feedback.pdf" in system_message

        # 4. Should contain the document content
        assert "Feedback document content" in system_message

        # 5. Should NOT be mixed with knowledge base section
        # (when only uploaded doc present)
        if "=== KNOWLEDGE BASE" in system_message:
            # If knowledge base section exists, uploaded doc should come first
            uploaded_pos = system_message.index("=== UPLOADED DOCUMENT")
            kb_pos = system_message.index("=== KNOWLEDGE BASE")
            assert uploaded_pos < kb_pos
