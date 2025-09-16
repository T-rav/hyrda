"""
Tests for ContextualRetrievalService
"""

from unittest.mock import AsyncMock

import pytest

from services.contextual_retrieval_service import ContextualRetrievalService


class TestContextualRetrievalService:
    """Test suite for ContextualRetrievalService"""

    @pytest.fixture
    def mock_llm_service(self):
        """Mock LLM service fixture"""
        service = AsyncMock()
        service.get_response.return_value = (
            "This chunk discusses user authentication in the login system."
        )
        return service

    @pytest.fixture
    def contextual_service(self, mock_llm_service):
        """ContextualRetrievalService fixture"""
        return ContextualRetrievalService(mock_llm_service)

    @pytest.fixture
    def sample_metadata(self):
        """Sample document metadata fixture"""
        return {
            "file_name": "authentication.md",
            "full_path": "docs/security/authentication.md",
            "mimeType": "text/markdown",
            "createdTime": "2024-01-01T12:00:00.000Z",
            "owners": [{"displayName": "John Doe"}],
        }

    @pytest.mark.asyncio
    async def test_add_context_to_chunks_success(
        self, contextual_service, mock_llm_service, sample_metadata
    ):
        """Test successful context addition to chunks"""
        chunks = [
            "Users can log in using their email and password.",
            "The system supports two-factor authentication.",
        ]

        result = await contextual_service.add_context_to_chunks(chunks, sample_metadata)

        assert len(result) == 2
        assert all(
            chunk.startswith("This chunk discusses user authentication")
            for chunk in result
        )
        assert mock_llm_service.get_response.call_count == 2

    @pytest.mark.asyncio
    async def test_add_context_to_chunks_empty_list(
        self, contextual_service, sample_metadata
    ):
        """Test handling of empty chunks list"""
        result = await contextual_service.add_context_to_chunks([], sample_metadata)
        assert result == []

    @pytest.mark.asyncio
    async def test_add_context_to_chunks_with_batch_size(
        self, contextual_service, mock_llm_service, sample_metadata
    ):
        """Test batch processing of chunks"""
        chunks = ["chunk1", "chunk2", "chunk3", "chunk4", "chunk5"]

        result = await contextual_service.add_context_to_chunks(
            chunks, sample_metadata, batch_size=2
        )

        assert len(result) == 5
        # Should have made 5 calls (one per chunk)
        assert mock_llm_service.get_response.call_count == 5

    @pytest.mark.asyncio
    async def test_generate_chunk_context_error_handling(
        self, contextual_service, sample_metadata
    ):
        """Test error handling in context generation"""
        # Mock LLM service to raise an exception
        contextual_service.llm_service.get_response.side_effect = Exception("API Error")

        chunk = "Test chunk content"
        result = await contextual_service._generate_chunk_context(
            chunk, sample_metadata
        )

        # Should return empty string on error
        assert result == ""

    @pytest.mark.asyncio
    async def test_process_chunk_batch_with_errors(
        self, contextual_service, mock_llm_service, sample_metadata
    ):
        """Test batch processing with some errors"""
        chunks = ["chunk1", "chunk2"]

        # Make the second call fail
        mock_llm_service.get_response.side_effect = [
            "Context for chunk1",
            Exception("API Error"),
        ]

        result = await contextual_service._process_chunk_batch(chunks, sample_metadata)

        assert len(result) == 2
        assert result[0] == "Context for chunk1 chunk1"  # Success case
        assert result[1] == "chunk2"  # Fallback case

    def test_build_document_context(self, contextual_service, sample_metadata):
        """Test document context building"""
        result = contextual_service._build_document_context(sample_metadata)

        expected_parts = [
            "File: authentication.md",
            "Path: docs/security/authentication.md",
            "Type: Markdown document",
            "Created: 2024-01-01",
            "Authors: John Doe",
        ]

        for part in expected_parts:
            assert part in result

        assert result.startswith(
            "This chunk is from a document with the following context:"
        )
        assert result.endswith(".")

    def test_build_document_context_minimal(self, contextual_service):
        """Test document context building with minimal metadata"""
        minimal_metadata = {"file_name": "test.txt"}

        result = contextual_service._build_document_context(minimal_metadata)

        assert "File: test.txt" in result
        assert result.startswith(
            "This chunk is from a document with the following context:"
        )

    def test_mime_to_document_type(self, contextual_service):
        """Test MIME type to document type conversion"""
        test_cases = [
            ("application/pdf", "PDF document"),
            ("application/vnd.google-apps.document", "Google Doc"),
            ("text/markdown", "Markdown document"),
            ("application/unknown", ""),
        ]

        for mime_type, expected in test_cases:
            result = contextual_service._mime_to_document_type(mime_type)
            assert result == expected

    @pytest.mark.asyncio
    async def test_context_length_limiting(self, contextual_service, sample_metadata):
        """Test that context is limited to reasonable length"""
        # Mock a very long response
        long_response = "Very long context " * 20  # > 200 chars
        contextual_service.llm_service.get_response.return_value = long_response

        chunk = "Test chunk"
        result = await contextual_service._generate_chunk_context(
            chunk, sample_metadata
        )

        # Should be truncated
        assert len(result) <= 203  # 200 + "..."
        assert result.endswith("...")
