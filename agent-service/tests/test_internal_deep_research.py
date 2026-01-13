"""Comprehensive tests for InternalDeepResearchService.

Tests cover:
- Service initialization
- Deep research execution with different effort levels
- Query decomposition and sub-query generation
- Context retrieval and chunk deduplication
- Chunk ranking and limiting
- Finding synthesis and summary generation
- Error handling and edge cases
- Factory functions
"""

import os
import sys
from unittest.mock import AsyncMock, Mock

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.internal_deep_research import (
    InternalDeepResearchService,
    create_internal_deep_research_service,
)


class TestInternalDeepResearchServiceInitialization:
    """Test InternalDeepResearchService initialization."""

    def test_initialization_with_all_services(self):
        """Test initialization with all required services."""
        # Arrange
        llm_service = Mock()
        retrieval_service = Mock()
        vector_service = Mock()
        embedding_service = Mock()

        # Act
        service = InternalDeepResearchService(
            llm_service=llm_service,
            retrieval_service=retrieval_service,
            vector_service=vector_service,
            embedding_service=embedding_service,
            enable_query_rewriting=True,
        )

        # Assert
        assert service.llm_service == llm_service
        assert service.retrieval_service == retrieval_service
        assert service.vector_service == vector_service
        assert service.embedding_service == embedding_service
        assert service.enable_query_rewriting is True

    def test_initialization_with_query_rewriting_disabled(self):
        """Test initialization with query rewriting disabled."""
        # Arrange
        services = {
            "llm_service": Mock(),
            "retrieval_service": Mock(),
            "vector_service": Mock(),
            "embedding_service": Mock(),
        }

        # Act
        service = InternalDeepResearchService(
            **services, enable_query_rewriting=False
        )

        # Assert
        assert service.enable_query_rewriting is False


class TestDeepResearch:
    """Test deep_research method."""

    @pytest.mark.asyncio
    async def test_deep_research_no_vector_service(self):
        """Test that error is returned when vector service is None."""
        # Arrange
        service = InternalDeepResearchService(
            llm_service=Mock(),
            retrieval_service=Mock(),
            vector_service=None,
            embedding_service=Mock(),
        )

        # Act
        result = await service.deep_research(query="test query")

        # Assert
        assert result["success"] is False
        assert "Vector database not configured" in result["error"]
        assert result["query"] == "test query"

    @pytest.mark.asyncio
    async def test_deep_research_empty_query(self):
        """Test that error is returned for empty query."""
        # Arrange
        service = InternalDeepResearchService(
            llm_service=Mock(),
            retrieval_service=Mock(),
            vector_service=Mock(),
            embedding_service=Mock(),
        )

        # Act
        result = await service.deep_research(query="")

        # Assert
        assert result["success"] is False
        assert "Empty query provided" in result["error"]

    @pytest.mark.asyncio
    async def test_deep_research_whitespace_query(self):
        """Test that error is returned for whitespace-only query."""
        # Arrange
        service = InternalDeepResearchService(
            llm_service=Mock(),
            retrieval_service=Mock(),
            vector_service=Mock(),
            embedding_service=Mock(),
        )

        # Act
        result = await service.deep_research(query="   ")

        # Assert
        assert result["success"] is False
        assert "Empty query provided" in result["error"]

    @pytest.mark.asyncio
    async def test_deep_research_medium_effort_success(self):
        """Test successful deep research with medium effort."""
        # Arrange
        llm_service = AsyncMock()
        llm_service.get_response = AsyncMock(
            side_effect=[
                '["sub-query 1", "sub-query 2"]',  # Query decomposition
                "Comprehensive findings summary",  # Synthesis
            ]
        )

        retrieval_service = AsyncMock()
        retrieval_service.retrieve_context = AsyncMock(
            side_effect=[
                [
                    {
                        "content": "Chunk 1 content",
                        "similarity": 0.9,
                        "metadata": {"file_name": "doc1.pdf"},
                    },
                    {
                        "content": "Chunk 2 content",
                        "similarity": 0.85,
                        "metadata": {"file_name": "doc2.pdf"},
                    },
                ],
                [
                    {
                        "content": "Chunk 3 content",
                        "similarity": 0.8,
                        "metadata": {"file_name": "doc1.pdf"},
                    },
                ],
            ]
        )

        vector_service = Mock()
        embedding_service = Mock()

        service = InternalDeepResearchService(
            llm_service=llm_service,
            retrieval_service=retrieval_service,
            vector_service=vector_service,
            embedding_service=embedding_service,
        )

        # Act
        result = await service.deep_research(
            query="What is Python programming?", effort="medium"
        )

        # Assert
        assert result["success"] is True
        assert result["query"] == "What is Python programming?"
        assert result["effort"] == "medium"
        assert len(result["sub_queries"]) == 2
        assert len(result["chunks"]) == 3
        assert result["unique_documents"] == 2
        assert result["total_chunks"] == 3
        assert "summary" in result
        assert result["summary"] == "Comprehensive findings summary"

    @pytest.mark.asyncio
    async def test_deep_research_low_effort_generates_3_queries(self):
        """Test that low effort generates 3 sub-queries."""
        # Arrange
        llm_service = AsyncMock()
        llm_service.get_response = AsyncMock(
            side_effect=[
                '["query 1", "query 2", "query 3"]',
                "Summary",
            ]
        )

        retrieval_service = AsyncMock()
        retrieval_service.retrieve_context = AsyncMock(return_value=[])

        service = InternalDeepResearchService(
            llm_service=llm_service,
            retrieval_service=retrieval_service,
            vector_service=Mock(),
            embedding_service=Mock(),
        )

        # Act
        result = await service.deep_research(query="test query", effort="low")

        # Assert
        assert result["success"] is True
        assert len(result["sub_queries"]) == 3

    @pytest.mark.asyncio
    async def test_deep_research_high_effort_generates_1_query(self):
        """Test that high effort generates 1 sub-query."""
        # Arrange
        llm_service = AsyncMock()
        llm_service.get_response = AsyncMock(
            side_effect=[
                '["single focused query"]',
                "Summary",
            ]
        )

        retrieval_service = AsyncMock()
        retrieval_service.retrieve_context = AsyncMock(return_value=[])

        service = InternalDeepResearchService(
            llm_service=llm_service,
            retrieval_service=retrieval_service,
            vector_service=Mock(),
            embedding_service=Mock(),
        )

        # Act
        result = await service.deep_research(query="test query", effort="high")

        # Assert
        assert result["success"] is True
        assert len(result["sub_queries"]) == 1

    @pytest.mark.asyncio
    async def test_deep_research_deduplicates_chunks(self):
        """Test that duplicate chunks are removed."""
        # Arrange
        llm_service = AsyncMock()
        llm_service.get_response = AsyncMock(
            side_effect=[
                '["query 1", "query 2"]',
                "Summary",
            ]
        )

        duplicate_chunk = {
            "content": "Same content for deduplication test",
            "similarity": 0.9,
            "metadata": {"file_name": "doc.pdf"},
        }

        retrieval_service = AsyncMock()
        retrieval_service.retrieve_context = AsyncMock(
            side_effect=[
                [duplicate_chunk],
                [duplicate_chunk],  # Same chunk returned again
            ]
        )

        service = InternalDeepResearchService(
            llm_service=llm_service,
            retrieval_service=retrieval_service,
            vector_service=Mock(),
            embedding_service=Mock(),
        )

        # Act
        result = await service.deep_research(query="test query")

        # Assert
        assert result["success"] is True
        # Should only have 1 chunk, not 2 (deduplication)
        assert len(result["chunks"]) == 1

    @pytest.mark.asyncio
    async def test_deep_research_adds_sub_query_metadata(self):
        """Test that sub-query is added to chunk metadata."""
        # Arrange
        llm_service = AsyncMock()
        llm_service.get_response = AsyncMock(
            side_effect=[
                '["specific sub-query"]',
                "Summary",
            ]
        )

        chunk = {
            "content": "Test content",
            "similarity": 0.9,
            "metadata": {"file_name": "doc.pdf"},
        }

        retrieval_service = AsyncMock()
        retrieval_service.retrieve_context = AsyncMock(return_value=[chunk])

        service = InternalDeepResearchService(
            llm_service=llm_service,
            retrieval_service=retrieval_service,
            vector_service=Mock(),
            embedding_service=Mock(),
        )

        # Act
        result = await service.deep_research(query="test query")

        # Assert
        assert result["success"] is True
        assert result["chunks"][0]["metadata"]["sub_query"] == "specific sub-query"

    @pytest.mark.asyncio
    async def test_deep_research_limits_chunks_by_effort(self):
        """Test that chunks are limited based on effort level."""
        # Arrange
        llm_service = AsyncMock()
        llm_service.get_response = AsyncMock(
            side_effect=[
                '["query"]',
                "Summary",
            ]
        )

        # Create 30 unique chunks
        many_chunks = [
            {
                "content": f"Chunk {i} unique content",
                "similarity": 0.9 - (i * 0.01),
                "metadata": {"file_name": f"doc{i}.pdf"},
            }
            for i in range(30)
        ]

        retrieval_service = AsyncMock()
        retrieval_service.retrieve_context = AsyncMock(return_value=many_chunks)

        service = InternalDeepResearchService(
            llm_service=llm_service,
            retrieval_service=retrieval_service,
            vector_service=Mock(),
            embedding_service=Mock(),
        )

        # Act - low effort should limit to 10 chunks
        result = await service.deep_research(query="test query", effort="low")

        # Assert
        assert result["success"] is True
        assert len(result["chunks"]) == 10

    @pytest.mark.asyncio
    async def test_deep_research_handles_llm_error(self):
        """Test error handling when LLM service fails."""
        # Arrange
        llm_service = AsyncMock()
        llm_service.get_response = AsyncMock(
            side_effect=Exception("LLM service error")
        )

        service = InternalDeepResearchService(
            llm_service=llm_service,
            retrieval_service=Mock(),
            vector_service=Mock(),
            embedding_service=Mock(),
        )

        # Act
        result = await service.deep_research(query="test query")

        # Assert
        assert result["success"] is False
        assert "LLM service error" in result["error"]

    @pytest.mark.asyncio
    async def test_deep_research_handles_retrieval_error(self):
        """Test error handling when retrieval service fails."""
        # Arrange
        llm_service = AsyncMock()
        llm_service.get_response = AsyncMock(return_value='["query"]')

        retrieval_service = AsyncMock()
        retrieval_service.retrieve_context = AsyncMock(
            side_effect=Exception("Retrieval failed")
        )

        service = InternalDeepResearchService(
            llm_service=llm_service,
            retrieval_service=retrieval_service,
            vector_service=Mock(),
            embedding_service=Mock(),
        )

        # Act
        result = await service.deep_research(query="test query")

        # Assert
        assert result["success"] is False
        assert "Retrieval failed" in result["error"]

    @pytest.mark.asyncio
    async def test_deep_research_with_conversation_history(self):
        """Test deep research with conversation history context."""
        # Arrange
        llm_service = AsyncMock()
        llm_service.get_response = AsyncMock(
            side_effect=[
                '["contextual query"]',
                "Summary",
            ]
        )

        retrieval_service = AsyncMock()
        retrieval_service.retrieve_context = AsyncMock(return_value=[])

        service = InternalDeepResearchService(
            llm_service=llm_service,
            retrieval_service=retrieval_service,
            vector_service=Mock(),
            embedding_service=Mock(),
        )

        conversation_history = [
            {"role": "user", "content": "previous message"},
            {"role": "assistant", "content": "previous response"},
        ]

        # Act
        result = await service.deep_research(
            query="follow up query",
            conversation_history=conversation_history,
            user_id="U123",
        )

        # Assert
        assert result["success"] is True
        # Verify conversation history was passed to retrieval
        retrieval_service.retrieve_context.assert_called()
        call_kwargs = retrieval_service.retrieve_context.call_args.kwargs
        assert call_kwargs["conversation_history"] == conversation_history
        assert call_kwargs["user_id"] == "U123"


class TestDecomposeQuery:
    """Test _decompose_query method."""

    @pytest.mark.asyncio
    async def test_decompose_query_success(self):
        """Test successful query decomposition."""
        # Arrange
        llm_service = AsyncMock()
        llm_service.get_response = AsyncMock(
            return_value='["What is Python?", "Python use cases", "Python vs other languages"]'
        )

        service = InternalDeepResearchService(
            llm_service=llm_service,
            retrieval_service=Mock(),
            vector_service=Mock(),
            embedding_service=Mock(),
        )

        # Act
        sub_queries = await service._decompose_query(
            query="Tell me about Python programming", num_queries=3
        )

        # Assert
        assert len(sub_queries) == 3
        assert "What is Python?" in sub_queries
        assert "Python use cases" in sub_queries

    @pytest.mark.asyncio
    async def test_decompose_query_invalid_json_fallback(self):
        """Test fallback to original query when JSON parsing fails."""
        # Arrange
        llm_service = AsyncMock()
        llm_service.get_response = AsyncMock(
            return_value="This is not valid JSON"
        )

        service = InternalDeepResearchService(
            llm_service=llm_service,
            retrieval_service=Mock(),
            vector_service=Mock(),
            embedding_service=Mock(),
        )

        # Act
        sub_queries = await service._decompose_query(
            query="test query", num_queries=2
        )

        # Assert
        assert len(sub_queries) == 1
        assert sub_queries[0] == "test query"

    @pytest.mark.asyncio
    async def test_decompose_query_empty_list_fallback(self):
        """Test fallback when LLM returns empty list."""
        # Arrange
        llm_service = AsyncMock()
        llm_service.get_response = AsyncMock(return_value="[]")

        service = InternalDeepResearchService(
            llm_service=llm_service,
            retrieval_service=Mock(),
            vector_service=Mock(),
            embedding_service=Mock(),
        )

        # Act
        sub_queries = await service._decompose_query(
            query="test query", num_queries=2
        )

        # Assert
        assert len(sub_queries) == 1
        assert sub_queries[0] == "test query"

    @pytest.mark.asyncio
    async def test_decompose_query_non_list_response_fallback(self):
        """Test fallback when LLM returns non-list JSON."""
        # Arrange
        llm_service = AsyncMock()
        llm_service.get_response = AsyncMock(return_value='{"key": "value"}')

        service = InternalDeepResearchService(
            llm_service=llm_service,
            retrieval_service=Mock(),
            vector_service=Mock(),
            embedding_service=Mock(),
        )

        # Act
        sub_queries = await service._decompose_query(
            query="test query", num_queries=2
        )

        # Assert
        assert len(sub_queries) == 1
        assert sub_queries[0] == "test query"

    @pytest.mark.asyncio
    async def test_decompose_query_includes_num_queries_in_prompt(self):
        """Test that num_queries is correctly included in prompt."""
        # Arrange
        llm_service = AsyncMock()
        llm_service.get_response = AsyncMock(
            return_value='["query1", "query2", "query3", "query4", "query5"]'
        )

        service = InternalDeepResearchService(
            llm_service=llm_service,
            retrieval_service=Mock(),
            vector_service=Mock(),
            embedding_service=Mock(),
        )

        # Act
        await service._decompose_query(query="test query", num_queries=5)

        # Assert
        llm_service.get_response.assert_called_once()
        prompt = llm_service.get_response.call_args[1]["messages"][0]["content"]
        assert "5 DIVERSE sub-queries" in prompt
        assert "5 DISTINCT sub-queries" in prompt


class TestGetChunkId:
    """Test _get_chunk_id method."""

    def test_get_chunk_id_creates_unique_id(self):
        """Test that chunk ID is created from file name and content."""
        # Arrange
        service = InternalDeepResearchService(
            llm_service=Mock(),
            retrieval_service=Mock(),
            vector_service=Mock(),
            embedding_service=Mock(),
        )

        chunk = {
            "content": "This is a long piece of content that should be truncated at 100 characters for the chunk ID generation process",
            "metadata": {"file_name": "document.pdf"},
        }

        # Act
        chunk_id = service._get_chunk_id(chunk)

        # Assert
        assert "document.pdf:" in chunk_id
        assert len(chunk_id.split(":", 1)[1]) == 100

    def test_get_chunk_id_handles_missing_metadata(self):
        """Test chunk ID generation with missing metadata."""
        # Arrange
        service = InternalDeepResearchService(
            llm_service=Mock(),
            retrieval_service=Mock(),
            vector_service=Mock(),
            embedding_service=Mock(),
        )

        chunk = {"content": "Test content"}

        # Act
        chunk_id = service._get_chunk_id(chunk)

        # Assert
        assert chunk_id == ":Test content"

    def test_get_chunk_id_handles_short_content(self):
        """Test chunk ID with content shorter than 100 chars."""
        # Arrange
        service = InternalDeepResearchService(
            llm_service=Mock(),
            retrieval_service=Mock(),
            vector_service=Mock(),
            embedding_service=Mock(),
        )

        chunk = {
            "content": "Short",
            "metadata": {"file_name": "doc.pdf"},
        }

        # Act
        chunk_id = service._get_chunk_id(chunk)

        # Assert
        assert chunk_id == "doc.pdf:Short"


class TestRankChunks:
    """Test _rank_chunks method."""

    def test_rank_chunks_sorts_by_similarity(self):
        """Test that chunks are sorted by similarity score."""
        # Arrange
        service = InternalDeepResearchService(
            llm_service=Mock(),
            retrieval_service=Mock(),
            vector_service=Mock(),
            embedding_service=Mock(),
        )

        chunks = [
            {"content": "Low", "similarity": 0.5, "metadata": {}},
            {"content": "High", "similarity": 0.9, "metadata": {}},
            {"content": "Medium", "similarity": 0.7, "metadata": {}},
        ]

        # Act
        ranked = service._rank_chunks(chunks, "test query")

        # Assert
        assert len(ranked) == 3
        assert ranked[0]["similarity"] == 0.9
        assert ranked[1]["similarity"] == 0.7
        assert ranked[2]["similarity"] == 0.5

    def test_rank_chunks_handles_missing_similarity(self):
        """Test ranking with chunks missing similarity scores."""
        # Arrange
        service = InternalDeepResearchService(
            llm_service=Mock(),
            retrieval_service=Mock(),
            vector_service=Mock(),
            embedding_service=Mock(),
        )

        chunks = [
            {"content": "Has score", "similarity": 0.8, "metadata": {}},
            {"content": "No score", "metadata": {}},
        ]

        # Act
        ranked = service._rank_chunks(chunks, "test query")

        # Assert
        assert len(ranked) == 2
        assert ranked[0]["similarity"] == 0.8
        assert ranked[1].get("similarity", 0) == 0

    def test_rank_chunks_empty_list(self):
        """Test ranking with empty chunk list."""
        # Arrange
        service = InternalDeepResearchService(
            llm_service=Mock(),
            retrieval_service=Mock(),
            vector_service=Mock(),
            embedding_service=Mock(),
        )

        # Act
        ranked = service._rank_chunks([], "test query")

        # Assert
        assert ranked == []


class TestSynthesizeFindings:
    """Test _synthesize_findings method."""

    @pytest.mark.asyncio
    async def test_synthesize_findings_success(self):
        """Test successful findings synthesis."""
        # Arrange
        llm_service = AsyncMock()
        llm_service.get_response = AsyncMock(
            return_value="Synthesized summary of all findings"
        )

        service = InternalDeepResearchService(
            llm_service=llm_service,
            retrieval_service=Mock(),
            vector_service=Mock(),
            embedding_service=Mock(),
        )

        chunks = [
            {
                "content": "Finding 1",
                "similarity": 0.9,
                "metadata": {"file_name": "doc1.pdf"},
            },
            {
                "content": "Finding 2",
                "similarity": 0.85,
                "metadata": {"file_name": "doc2.pdf"},
            },
        ]

        sub_queries = ["query 1", "query 2"]

        # Act
        summary = await service._synthesize_findings(
            query="What is Python?", chunks=chunks, sub_queries=sub_queries
        )

        # Assert
        assert summary == "Synthesized summary of all findings"
        llm_service.get_response.assert_called_once()

    @pytest.mark.asyncio
    async def test_synthesize_findings_no_chunks(self):
        """Test synthesis with no chunks returns default message."""
        # Arrange
        service = InternalDeepResearchService(
            llm_service=Mock(),
            retrieval_service=Mock(),
            vector_service=Mock(),
            embedding_service=Mock(),
        )

        # Act
        summary = await service._synthesize_findings(
            query="test", chunks=[], sub_queries=[]
        )

        # Assert
        assert summary == "No relevant information found in internal knowledge base."

    @pytest.mark.asyncio
    async def test_synthesize_findings_limits_to_10_chunks(self):
        """Test that synthesis only uses top 10 chunks."""
        # Arrange
        llm_service = AsyncMock()
        llm_service.get_response = AsyncMock(return_value="Summary")

        service = InternalDeepResearchService(
            llm_service=llm_service,
            retrieval_service=Mock(),
            vector_service=Mock(),
            embedding_service=Mock(),
        )

        # Create 20 chunks
        chunks = [
            {
                "content": f"Content {i}",
                "similarity": 0.9,
                "metadata": {"file_name": f"doc{i}.pdf"},
            }
            for i in range(20)
        ]

        # Act
        await service._synthesize_findings(
            query="test", chunks=chunks, sub_queries=["query"]
        )

        # Assert
        llm_service.get_response.assert_called_once()
        prompt = llm_service.get_response.call_args[1]["messages"][0]["content"]
        # Should only have 10 sources in context
        assert "[Source 10:" in prompt
        assert "[Source 11:" not in prompt

    @pytest.mark.asyncio
    async def test_synthesize_findings_truncates_long_content(self):
        """Test that long chunk content is truncated."""
        # Arrange
        llm_service = AsyncMock()
        llm_service.get_response = AsyncMock(return_value="Summary")

        service = InternalDeepResearchService(
            llm_service=llm_service,
            retrieval_service=Mock(),
            vector_service=Mock(),
            embedding_service=Mock(),
        )

        long_content = "a" * 1000
        chunks = [
            {
                "content": long_content,
                "similarity": 0.9,
                "metadata": {"file_name": "doc.pdf"},
            }
        ]

        # Act
        await service._synthesize_findings(
            query="test", chunks=chunks, sub_queries=["query"]
        )

        # Assert
        llm_service.get_response.assert_called_once()
        prompt = llm_service.get_response.call_args[1]["messages"][0]["content"]
        # Content should be truncated to 500 chars
        assert "aaa" in prompt
        # Verify truncation happened (total prompt should be less than original content)
        assert len(prompt) < 1000 + 500  # Original content + prompt overhead

    @pytest.mark.asyncio
    async def test_synthesize_findings_handles_llm_error(self):
        """Test fallback when LLM fails during synthesis."""
        # Arrange
        llm_service = AsyncMock()
        llm_service.get_response = AsyncMock(
            side_effect=Exception("LLM synthesis failed")
        )

        service = InternalDeepResearchService(
            llm_service=llm_service,
            retrieval_service=Mock(),
            vector_service=Mock(),
            embedding_service=Mock(),
        )

        chunks = [
            {
                "content": "test",
                "similarity": 0.9,
                "metadata": {"file_name": "doc.pdf"},
            }
        ]

        # Act
        # When LLM fails, the exception is raised, not caught in _synthesize_findings
        with pytest.raises(Exception, match="LLM synthesis failed"):
            await service._synthesize_findings(
                query="test", chunks=chunks, sub_queries=["query"]
            )

    @pytest.mark.asyncio
    async def test_synthesize_findings_handles_empty_response(self):
        """Test fallback when LLM returns empty response."""
        # Arrange
        llm_service = AsyncMock()
        llm_service.get_response = AsyncMock(return_value="")

        service = InternalDeepResearchService(
            llm_service=llm_service,
            retrieval_service=Mock(),
            vector_service=Mock(),
            embedding_service=Mock(),
        )

        chunks = [{"content": "test", "metadata": {"file_name": "doc.pdf"}}]

        # Act
        summary = await service._synthesize_findings(
            query="test", chunks=chunks, sub_queries=["query"]
        )

        # Assert
        assert summary == "Unable to synthesize findings."


class TestFactoryFunction:
    """Test create_internal_deep_research_service factory function."""

    def test_factory_creates_service(self):
        """Test that factory function creates service with provided dependencies."""
        # Arrange
        llm_service = Mock()
        retrieval_service = Mock()
        vector_service = Mock()
        embedding_service = Mock()

        # Act
        service = create_internal_deep_research_service(
            llm_service=llm_service,
            retrieval_service=retrieval_service,
            vector_service=vector_service,
            embedding_service=embedding_service,
        )

        # Assert
        assert isinstance(service, InternalDeepResearchService)
        assert service.llm_service == llm_service
        assert service.retrieval_service == retrieval_service
        assert service.vector_service == vector_service
        assert service.embedding_service == embedding_service
        assert service.enable_query_rewriting is True


class TestChunkDeduplication:
    """Test chunk deduplication logic in deep research."""

    @pytest.mark.asyncio
    async def test_chunks_with_same_content_and_file_deduped(self):
        """Test that chunks with identical content and file are deduped."""
        # Arrange
        llm_service = AsyncMock()
        llm_service.get_response = AsyncMock(
            side_effect=[
                '["query 1", "query 2"]',
                "Summary",
            ]
        )

        same_chunk = {
            "content": "Identical content for both queries",
            "similarity": 0.9,
            "metadata": {"file_name": "doc.pdf"},
        }

        retrieval_service = AsyncMock()
        retrieval_service.retrieve_context = AsyncMock(
            side_effect=[
                [same_chunk.copy()],
                [same_chunk.copy()],
            ]
        )

        service = InternalDeepResearchService(
            llm_service=llm_service,
            retrieval_service=retrieval_service,
            vector_service=Mock(),
            embedding_service=Mock(),
        )

        # Act
        result = await service.deep_research(query="test")

        # Assert
        assert result["success"] is True
        assert len(result["chunks"]) == 1

    @pytest.mark.asyncio
    async def test_chunks_with_different_content_not_deduped(self):
        """Test that chunks with different content are not deduped."""
        # Arrange
        llm_service = AsyncMock()
        llm_service.get_response = AsyncMock(
            side_effect=[
                '["query 1", "query 2"]',
                "Summary",
            ]
        )

        retrieval_service = AsyncMock()
        retrieval_service.retrieve_context = AsyncMock(
            side_effect=[
                [
                    {
                        "content": "Content A",
                        "similarity": 0.9,
                        "metadata": {"file_name": "doc.pdf"},
                    }
                ],
                [
                    {
                        "content": "Content B",
                        "similarity": 0.85,
                        "metadata": {"file_name": "doc.pdf"},
                    }
                ],
            ]
        )

        service = InternalDeepResearchService(
            llm_service=llm_service,
            retrieval_service=retrieval_service,
            vector_service=Mock(),
            embedding_service=Mock(),
        )

        # Act
        result = await service.deep_research(query="test")

        # Assert
        assert result["success"] is True
        assert len(result["chunks"]) == 2


class TestResultStatistics:
    """Test statistics calculation in deep research results."""

    @pytest.mark.asyncio
    async def test_unique_documents_count_correct(self):
        """Test that unique documents are counted correctly."""
        # Arrange
        llm_service = AsyncMock()
        llm_service.get_response = AsyncMock(
            side_effect=[
                '["query"]',
                "Summary",
            ]
        )

        retrieval_service = AsyncMock()
        retrieval_service.retrieve_context = AsyncMock(
            return_value=[
                {
                    "content": "Chunk 1",
                    "similarity": 0.9,
                    "metadata": {"file_name": "doc1.pdf"},
                },
                {
                    "content": "Chunk 2",
                    "similarity": 0.85,
                    "metadata": {"file_name": "doc1.pdf"},
                },
                {
                    "content": "Chunk 3",
                    "similarity": 0.8,
                    "metadata": {"file_name": "doc2.pdf"},
                },
            ]
        )

        service = InternalDeepResearchService(
            llm_service=llm_service,
            retrieval_service=retrieval_service,
            vector_service=Mock(),
            embedding_service=Mock(),
        )

        # Act
        result = await service.deep_research(query="test")

        # Assert
        assert result["success"] is True
        assert result["unique_documents"] == 2
        assert result["total_chunks"] == 3


class TestEffortLevels:
    """Test different effort levels and their configurations."""

    @pytest.mark.asyncio
    async def test_invalid_effort_defaults_to_medium(self):
        """Test that invalid effort level defaults to medium (2 queries)."""
        # Arrange
        llm_service = AsyncMock()
        llm_service.get_response = AsyncMock(
            side_effect=[
                '["query 1", "query 2"]',
                "Summary",
            ]
        )

        retrieval_service = AsyncMock()
        retrieval_service.retrieve_context = AsyncMock(return_value=[])

        service = InternalDeepResearchService(
            llm_service=llm_service,
            retrieval_service=retrieval_service,
            vector_service=Mock(),
            embedding_service=Mock(),
        )

        # Act
        result = await service.deep_research(query="test", effort="invalid")

        # Assert
        assert result["success"] is True
        assert len(result["sub_queries"]) == 2

    @pytest.mark.asyncio
    async def test_high_effort_limits_to_20_chunks(self):
        """Test that high effort limits to 20 chunks."""
        # Arrange
        llm_service = AsyncMock()
        llm_service.get_response = AsyncMock(
            side_effect=[
                '["query"]',
                "Summary",
            ]
        )

        # Create 30 unique chunks
        many_chunks = [
            {
                "content": f"Unique content {i}",
                "similarity": 0.9 - (i * 0.01),
                "metadata": {"file_name": f"doc{i}.pdf"},
            }
            for i in range(30)
        ]

        retrieval_service = AsyncMock()
        retrieval_service.retrieve_context = AsyncMock(return_value=many_chunks)

        service = InternalDeepResearchService(
            llm_service=llm_service,
            retrieval_service=retrieval_service,
            vector_service=Mock(),
            embedding_service=Mock(),
        )

        # Act
        result = await service.deep_research(query="test", effort="high")

        # Assert
        assert result["success"] is True
        assert len(result["chunks"]) == 20


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_deep_research_with_empty_chunks_from_retrieval(self):
        """Test deep research when retrieval returns no chunks."""
        # Arrange
        llm_service = AsyncMock()
        llm_service.get_response = AsyncMock(
            side_effect=[
                '["query 1", "query 2"]',
                "No relevant information found in internal knowledge base.",
            ]
        )

        retrieval_service = AsyncMock()
        retrieval_service.retrieve_context = AsyncMock(return_value=[])

        service = InternalDeepResearchService(
            llm_service=llm_service,
            retrieval_service=retrieval_service,
            vector_service=Mock(),
            embedding_service=Mock(),
        )

        # Act
        result = await service.deep_research(query="obscure query")

        # Assert
        assert result["success"] is True
        assert len(result["chunks"]) == 0
        assert result["unique_documents"] == 0
        assert result["total_chunks"] == 0
        assert "No relevant information" in result["summary"]

    @pytest.mark.asyncio
    async def test_deep_research_with_missing_file_name_in_metadata(self):
        """Test deep research with chunks missing file_name metadata."""
        # Arrange
        llm_service = AsyncMock()
        llm_service.get_response = AsyncMock(
            side_effect=[
                '["query"]',
                "Summary",
            ]
        )

        retrieval_service = AsyncMock()
        retrieval_service.retrieve_context = AsyncMock(
            return_value=[
                {
                    "content": "Chunk without file name",
                    "similarity": 0.9,
                    "metadata": {},
                }
            ]
        )

        service = InternalDeepResearchService(
            llm_service=llm_service,
            retrieval_service=retrieval_service,
            vector_service=Mock(),
            embedding_service=Mock(),
        )

        # Act
        result = await service.deep_research(query="test")

        # Assert
        assert result["success"] is True
        assert len(result["chunks"]) == 1
        assert result["unique_documents"] == 1  # Should count "unknown"

    @pytest.mark.asyncio
    async def test_synthesis_with_chunks_missing_metadata(self):
        """Test synthesis with chunks that have incomplete metadata."""
        # Arrange
        llm_service = AsyncMock()
        llm_service.get_response = AsyncMock(return_value="Summary")

        service = InternalDeepResearchService(
            llm_service=llm_service,
            retrieval_service=Mock(),
            vector_service=Mock(),
            embedding_service=Mock(),
        )

        chunks = [
            {"content": "Content without metadata", "similarity": 0.9}
        ]

        # Act
        summary = await service._synthesize_findings(
            query="test", chunks=chunks, sub_queries=["query"]
        )

        # Assert
        assert summary == "Summary"
        llm_service.get_response.assert_called_once()
        prompt = llm_service.get_response.call_args[1]["messages"][0]["content"]
        assert "unknown" in prompt

    def test_get_chunk_id_with_empty_content(self):
        """Test chunk ID generation with empty content."""
        # Arrange
        service = InternalDeepResearchService(
            llm_service=Mock(),
            retrieval_service=Mock(),
            vector_service=Mock(),
            embedding_service=Mock(),
        )

        chunk = {
            "content": "",
            "metadata": {"file_name": "doc.pdf"},
        }

        # Act
        chunk_id = service._get_chunk_id(chunk)

        # Assert
        assert chunk_id == "doc.pdf:"
