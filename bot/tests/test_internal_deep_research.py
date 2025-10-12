"""
Tests for Internal Deep Research Service

Comprehensive tests for internal knowledge base deep research functionality.
"""

from unittest.mock import AsyncMock

import pytest

from services.internal_deep_research import (
    InternalDeepResearchService,
    create_internal_deep_research_service,
)


class TestInternalDeepResearchService:
    """Test internal deep research service functionality"""

    def setup_method(self):
        """Set up test fixtures"""
        self.mock_llm_service = AsyncMock()
        self.mock_retrieval_service = AsyncMock()
        self.mock_vector_service = AsyncMock()
        self.mock_embedding_service = AsyncMock()

        self.service = InternalDeepResearchService(
            llm_service=self.mock_llm_service,
            retrieval_service=self.mock_retrieval_service,
            vector_service=self.mock_vector_service,
            embedding_service=self.mock_embedding_service,
            enable_query_rewriting=True,
        )

    @pytest.mark.asyncio
    async def test_initialization(self):
        """Test service initialization"""
        assert self.service.llm_service == self.mock_llm_service
        assert self.service.retrieval_service == self.mock_retrieval_service
        assert self.service.vector_service == self.mock_vector_service
        assert self.service.embedding_service == self.mock_embedding_service
        assert self.service.enable_query_rewriting is True

    @pytest.mark.asyncio
    async def test_deep_research_no_vector_service(self):
        """Test deep research with no vector service"""
        service = InternalDeepResearchService(
            llm_service=self.mock_llm_service,
            retrieval_service=self.mock_retrieval_service,
            vector_service=None,  # No vector service
            embedding_service=self.mock_embedding_service,
        )

        result = await service.deep_research("test query")

        assert result["success"] is False
        assert "Vector database not configured" in result["error"]
        assert result["query"] == "test query"

    @pytest.mark.asyncio
    async def test_deep_research_low_effort(self):
        """Test deep research with low effort (3 sub-queries)"""
        # Mock query decomposition
        self.mock_llm_service.get_response.side_effect = [
            '["sub-query 1", "sub-query 2", "sub-query 3"]',  # Decomposition
            "This is a synthesized summary.",  # Synthesis
        ]

        # Mock retrieval results
        self.mock_retrieval_service.retrieve_context.return_value = [
            {
                "content": "Test content 1",
                "similarity": 0.9,
                "metadata": {"file_name": "doc1.pdf"},
            }
        ]

        result = await self.service.deep_research("test query", effort="low")

        assert result["success"] is True
        assert result["query"] == "test query"
        assert len(result["sub_queries"]) == 3
        assert result["effort"] == "low"
        assert result["summary"] == "This is a synthesized summary."
        assert result["total_chunks"] > 0

    @pytest.mark.asyncio
    async def test_deep_research_medium_effort(self):
        """Test deep research with medium effort (5 sub-queries, default)"""
        # Mock query decomposition
        self.mock_llm_service.get_response.side_effect = [
            '["sq1", "sq2", "sq3", "sq4", "sq5"]',  # Decomposition
            "Medium effort synthesis.",  # Synthesis
        ]

        # Mock retrieval results
        self.mock_retrieval_service.retrieve_context.return_value = [
            {
                "content": "Content A",
                "similarity": 0.85,
                "metadata": {"file_name": "docA.pdf"},
            }
        ]

        result = await self.service.deep_research("complex query", effort="medium")

        assert result["success"] is True
        assert len(result["sub_queries"]) == 5
        assert result["effort"] == "medium"

    @pytest.mark.asyncio
    async def test_deep_research_high_effort(self):
        """Test deep research with high effort (8 sub-queries)"""
        # Mock query decomposition
        self.mock_llm_service.get_response.side_effect = [
            '["sq1", "sq2", "sq3", "sq4", "sq5", "sq6", "sq7", "sq8"]',  # Decomposition
            "High effort comprehensive analysis.",  # Synthesis
        ]

        # Mock retrieval results
        self.mock_retrieval_service.retrieve_context.return_value = []

        result = await self.service.deep_research("comprehensive query", effort="high")

        assert result["success"] is True
        assert len(result["sub_queries"]) == 8
        assert result["effort"] == "high"

    @pytest.mark.asyncio
    async def test_query_decomposition_with_conversation_history(self):
        """Test query decomposition includes conversation history"""
        conversation_history = [
            {"role": "user", "content": "What are our API standards?"},
            {"role": "assistant", "content": "Here are the standards..."},
        ]

        self.mock_llm_service.get_response.side_effect = [
            '["sub-query 1", "sub-query 2", "sub-query 3"]',
            "Synthesis with context.",
        ]

        self.mock_retrieval_service.retrieve_context.return_value = []

        result = await self.service.deep_research(
            "test query", conversation_history=conversation_history, effort="low"
        )

        assert result["success"] is True
        # Verify retrieval was called with conversation history
        assert self.mock_retrieval_service.retrieve_context.call_count == 3
        call_args = self.mock_retrieval_service.retrieve_context.call_args_list[0]
        assert call_args[1]["conversation_history"] == conversation_history

    @pytest.mark.asyncio
    async def test_query_decomposition_with_user_id(self):
        """Test query decomposition passes user_id for 'me/I' resolution"""
        self.mock_llm_service.get_response.side_effect = [
            '["sub-query about user"]',
            "User-specific synthesis.",
        ]

        self.mock_retrieval_service.retrieve_context.return_value = []

        result = await self.service.deep_research(
            "what did I work on?", user_id="U12345", effort="low"
        )

        assert result["success"] is True
        # Verify user_id was passed to retrieval
        call_args = self.mock_retrieval_service.retrieve_context.call_args_list[0]
        assert call_args[1]["user_id"] == "U12345"

    @pytest.mark.asyncio
    async def test_chunk_deduplication(self):
        """Test that duplicate chunks are filtered out"""
        self.mock_llm_service.get_response.side_effect = [
            '["query 1", "query 2"]',
            "Deduplicated synthesis.",
        ]

        # Return same chunk for both queries (should be deduplicated)
        duplicate_chunk = {
            "content": "Duplicate content here",
            "similarity": 0.9,
            "metadata": {"file_name": "same_doc.pdf"},
        }

        self.mock_retrieval_service.retrieve_context.side_effect = [
            [duplicate_chunk.copy()],  # Query 1
            [duplicate_chunk.copy()],  # Query 2
        ]

        result = await self.service.deep_research("test query", effort="low")

        assert result["success"] is True
        # Should only have 1 chunk despite 2 retrievals returning the same content
        assert result["total_chunks"] == 1

    @pytest.mark.asyncio
    async def test_chunk_ranking_by_similarity(self):
        """Test that chunks are ranked by similarity score"""
        self.mock_llm_service.get_response.side_effect = [
            '["query 1"]',
            "Ranked synthesis.",
        ]

        # Return chunks with different similarity scores
        self.mock_retrieval_service.retrieve_context.return_value = [
            {
                "content": "Low relevance",
                "similarity": 0.6,
                "metadata": {"file_name": "doc1.pdf"},
            },
            {
                "content": "High relevance",
                "similarity": 0.95,
                "metadata": {"file_name": "doc2.pdf"},
            },
            {
                "content": "Medium relevance",
                "similarity": 0.75,
                "metadata": {"file_name": "doc3.pdf"},
            },
        ]

        result = await self.service.deep_research("test query", effort="low")

        assert result["success"] is True
        # Chunks should be sorted by similarity (highest first)
        chunks = result["chunks"]
        assert chunks[0]["similarity"] == 0.95
        assert chunks[1]["similarity"] == 0.75
        assert chunks[2]["similarity"] == 0.6

    @pytest.mark.asyncio
    async def test_unique_document_count(self):
        """Test calculation of unique documents"""
        self.mock_llm_service.get_response.side_effect = [
            '["query 1"]',
            "Multi-document synthesis.",
        ]

        # Return chunks from 3 different documents
        self.mock_retrieval_service.retrieve_context.return_value = [
            {
                "content": "Content 1",
                "similarity": 0.9,
                "metadata": {"file_name": "doc1.pdf"},
            },
            {
                "content": "Content 2",
                "similarity": 0.85,
                "metadata": {"file_name": "doc2.pdf"},
            },
            {
                "content": "Content 3",
                "similarity": 0.8,
                "metadata": {"file_name": "doc1.pdf"},
            },  # Duplicate doc
            {
                "content": "Content 4",
                "similarity": 0.75,
                "metadata": {"file_name": "doc3.pdf"},
            },
        ]

        result = await self.service.deep_research("test query", effort="low")

        assert result["success"] is True
        assert result["unique_documents"] == 3  # doc1, doc2, doc3

    @pytest.mark.asyncio
    async def test_max_chunks_limit_low_effort(self):
        """Test that low effort limits to 10 chunks"""
        self.mock_llm_service.get_response.side_effect = [
            '["query 1"]',
            "Limited synthesis.",
        ]

        # Return 20 chunks (should be limited to 10 for low effort)
        many_chunks = [
            {
                "content": f"Content {i}",
                "similarity": 0.9 - (i * 0.01),
                "metadata": {"file_name": f"doc{i}.pdf"},
            }
            for i in range(20)
        ]

        self.mock_retrieval_service.retrieve_context.return_value = many_chunks

        result = await self.service.deep_research("test query", effort="low")

        assert result["success"] is True
        assert result["total_chunks"] == 10  # Limited to 10 for low effort

    @pytest.mark.asyncio
    async def test_max_chunks_limit_medium_effort(self):
        """Test that medium effort limits to 15 chunks"""
        self.mock_llm_service.get_response.side_effect = [
            '["query 1"]',
            "Medium synthesis.",
        ]

        # Return 25 chunks (should be limited to 15 for medium effort)
        many_chunks = [
            {
                "content": f"Content {i}",
                "similarity": 0.9 - (i * 0.01),
                "metadata": {"file_name": f"doc{i}.pdf"},
            }
            for i in range(25)
        ]

        self.mock_retrieval_service.retrieve_context.return_value = many_chunks

        result = await self.service.deep_research("test query", effort="medium")

        assert result["success"] is True
        assert result["total_chunks"] == 15  # Limited to 15 for medium effort

    @pytest.mark.asyncio
    async def test_synthesis_with_no_chunks(self):
        """Test synthesis when no chunks are found"""
        self.mock_llm_service.get_response.side_effect = [
            '["query 1"]',
            # No synthesis call needed since no chunks
        ]

        self.mock_retrieval_service.retrieve_context.return_value = []

        result = await self.service.deep_research("test query", effort="low")

        assert result["success"] is True
        assert result["total_chunks"] == 0
        assert "No relevant information found" in result["summary"]

    @pytest.mark.asyncio
    async def test_invalid_json_decomposition_fallback(self):
        """Test fallback when LLM returns invalid JSON for decomposition"""
        # Return invalid JSON
        self.mock_llm_service.get_response.side_effect = [
            "This is not valid JSON",
            "Fallback synthesis.",
        ]

        self.mock_retrieval_service.retrieve_context.return_value = []

        result = await self.service.deep_research("test query", effort="low")

        assert result["success"] is True
        # Should fallback to using original query
        assert len(result["sub_queries"]) == 1
        assert result["sub_queries"][0] == "test query"

    @pytest.mark.asyncio
    async def test_exception_handling(self):
        """Test exception handling during deep research"""
        # Make retrieval fail
        self.mock_retrieval_service.retrieve_context.side_effect = Exception(
            "Retrieval failed"
        )

        self.mock_llm_service.get_response.return_value = '["query 1"]'

        result = await self.service.deep_research("test query", effort="low")

        assert result["success"] is False
        assert "error" in result
        assert result["query"] == "test query"

    @pytest.mark.asyncio
    async def test_sub_query_metadata_tracking(self):
        """Test that sub-query is tracked in chunk metadata"""
        self.mock_llm_service.get_response.side_effect = [
            '["specific sub-query"]',
            "Tracked synthesis.",
        ]

        self.mock_retrieval_service.retrieve_context.return_value = [
            {
                "content": "Test content",
                "similarity": 0.9,
                "metadata": {"file_name": "doc.pdf"},
            }
        ]

        result = await self.service.deep_research("test query", effort="low")

        assert result["success"] is True
        # Check that sub-query was added to metadata
        assert result["chunks"][0]["metadata"]["sub_query"] == "specific sub-query"


class TestInternalDeepResearchFactory:
    """Test factory function for creating service"""

    def test_create_service(self):
        """Test factory function creates service correctly"""
        mock_llm = AsyncMock()
        mock_retrieval = AsyncMock()
        mock_vector = AsyncMock()
        mock_embedding = AsyncMock()

        service = create_internal_deep_research_service(
            llm_service=mock_llm,
            retrieval_service=mock_retrieval,
            vector_service=mock_vector,
            embedding_service=mock_embedding,
        )

        assert isinstance(service, InternalDeepResearchService)
        assert service.llm_service == mock_llm
        assert service.retrieval_service == mock_retrieval
        assert service.vector_service == mock_vector
        assert service.embedding_service == mock_embedding
        assert service.enable_query_rewriting is True


class TestInternalDeepResearchEdgeCases:
    """Test edge cases and error conditions"""

    def setup_method(self):
        """Set up test fixtures"""
        self.mock_llm_service = AsyncMock()
        self.mock_retrieval_service = AsyncMock()
        self.mock_vector_service = AsyncMock()
        self.mock_embedding_service = AsyncMock()

        self.service = InternalDeepResearchService(
            llm_service=self.mock_llm_service,
            retrieval_service=self.mock_retrieval_service,
            vector_service=self.mock_vector_service,
            embedding_service=self.mock_embedding_service,
        )

    @pytest.mark.asyncio
    async def test_empty_query(self):
        """Test deep research with empty query - test that fallback works"""
        self.mock_llm_service.get_response.side_effect = [
            '[""]',  # Empty string returned - will fallback to original query
            "No relevant information found.",
        ]

        self.mock_retrieval_service.retrieve_context.return_value = []

        result = await self.service.deep_research("test query", effort="low")

        # Should succeed with fallback to original query
        assert result["success"] is True
        assert len(result["sub_queries"]) >= 1  # At least the fallback query

    @pytest.mark.asyncio
    async def test_very_long_query(self):
        """Test deep research with very long query"""
        long_query = "test " * 1000  # Very long query

        self.mock_llm_service.get_response.side_effect = [
            '["sub-query"]',
            "Long query synthesis.",
        ]

        self.mock_retrieval_service.retrieve_context.return_value = []

        result = await self.service.deep_research(long_query, effort="low")

        assert result["success"] is True
        assert result["query"] == long_query

    @pytest.mark.asyncio
    async def test_invalid_effort_level(self):
        """Test deep research with invalid effort level (should use default)"""
        self.mock_llm_service.get_response.side_effect = [
            '["query 1", "query 2", "query 3", "query 4", "query 5"]',  # Default to medium (5)
            "Default effort synthesis.",
        ]

        self.mock_retrieval_service.retrieve_context.return_value = []

        result = await self.service.deep_research("test query", effort="invalid")

        assert result["success"] is True
        # Should default to medium (5 queries)
        assert len(result["sub_queries"]) == 5
