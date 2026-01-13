"""Comprehensive tests for RetrievalService.

Tests cover:
- Context retrieval with query rewriting
- Vector search and ranking
- Entity extraction and boosting
- Diversification strategies
- Error handling
- Edge cases
"""

import os
import sys
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Mock the query_rewriter module before importing retrieval_service
sys.modules["services.query_rewriter"] = MagicMock()

from config.settings import RAGSettings, Settings
from services.retrieval_service import STOP_WORDS, RetrievalService


class TestRetrievalServiceInitialization:
    """Test RetrievalService initialization."""

    def test_initialization_with_defaults(self):
        """Test initialization with default settings."""
        # Arrange
        settings = Mock(spec=Settings)
        settings.rag = Mock(spec=RAGSettings)

        # Act
        service = RetrievalService(settings)

        # Assert
        assert service.settings == settings
        assert service.llm_service is None
        assert service.enable_query_rewriting is True
        assert service.query_rewriter is None

    def test_initialization_with_llm_service(self):
        """Test initialization with LLM service provided."""
        # Arrange
        settings = Mock(spec=Settings)
        settings.rag = Mock(spec=RAGSettings)
        llm_service = Mock()

        # Act
        service = RetrievalService(settings, llm_service=llm_service)

        # Assert
        assert service.llm_service == llm_service
        assert service.query_rewriter is None  # Lazy loaded

    def test_initialization_with_query_rewriting_disabled(self):
        """Test initialization with query rewriting disabled."""
        # Arrange
        settings = Mock(spec=Settings)
        settings.rag = Mock(spec=RAGSettings)

        # Act
        service = RetrievalService(
            settings, llm_service=Mock(), enable_query_rewriting=False
        )

        # Assert
        assert service.enable_query_rewriting is False
        assert service.query_rewriter is None


class TestRetrieveContext:
    """Test retrieve_context method."""

    @pytest.mark.asyncio
    async def test_retrieve_context_no_vector_service(self):
        """Test that empty list is returned when vector service is None."""
        # Arrange
        settings = Mock(spec=Settings)
        settings.rag = Mock(spec=RAGSettings)
        service = RetrievalService(settings)

        # Act
        result = await service.retrieve_context(
            query="test query",
            vector_service=None,
            embedding_service=Mock(),
        )

        # Assert
        assert result == []

    @pytest.mark.asyncio
    async def test_retrieve_context_basic_search(self):
        """Test basic context retrieval without query rewriting."""
        # Arrange
        settings = Mock(spec=Settings)
        settings.rag = Mock(spec=RAGSettings)
        settings.rag.max_results = 5
        settings.rag.similarity_threshold = 0.35
        settings.rag.results_similarity_threshold = 0.5
        settings.rag.entity_content_boost = 0.05
        settings.rag.entity_title_boost = 0.1
        settings.rag.max_chunks_per_document = 3

        service = RetrievalService(settings, enable_query_rewriting=False)

        # Mock services
        embedding_service = AsyncMock()
        embedding_service.get_embedding = AsyncMock(return_value=[0.1, 0.2, 0.3])

        vector_service = AsyncMock()
        mock_results = [
            {
                "content": "Test content about Python",
                "similarity": 0.9,
                "metadata": {"file_name": "doc1.pdf"},
            },
            {
                "content": "More Python content",
                "similarity": 0.8,
                "metadata": {"file_name": "doc2.pdf"},
            },
        ]
        vector_service.search = AsyncMock(return_value=mock_results)

        # Act
        result = await service.retrieve_context(
            query="Python programming",
            vector_service=vector_service,
            embedding_service=embedding_service,
        )

        # Assert
        assert len(result) == 2
        assert result[0]["similarity"] >= result[1]["similarity"]
        embedding_service.get_embedding.assert_called_once_with("Python programming")
        vector_service.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_retrieve_context_with_query_rewriting(self):
        """Test context retrieval with query rewriting enabled."""
        # Arrange
        settings = Mock(spec=Settings)
        settings.rag = Mock(spec=RAGSettings)
        settings.rag.max_results = 5
        settings.rag.similarity_threshold = 0.35
        settings.rag.results_similarity_threshold = 0.5
        settings.rag.entity_content_boost = 0.05
        settings.rag.entity_title_boost = 0.1
        settings.rag.max_chunks_per_document = 3

        llm_service = Mock()

        service = RetrievalService(settings, llm_service=llm_service)

        # Mock query rewriter
        mock_rewriter = AsyncMock()
        mock_rewriter.rewrite_query = AsyncMock(
            return_value={
                "query": "rewritten query",
                "strategy": "entity_focused",
                "intent": {"type": "factual"},
                "filters": {"document_type": "manual"},
            }
        )

        # Patch AdaptiveQueryRewriter
        with patch(
            "services.retrieval_service.AdaptiveQueryRewriter",
            return_value=mock_rewriter,
        ):
            # Mock services
            embedding_service = AsyncMock()
            embedding_service.get_embedding = AsyncMock(return_value=[0.1, 0.2, 0.3])

            vector_service = AsyncMock()
            mock_results = [
                {
                    "content": "Manual content",
                    "similarity": 0.85,
                    "metadata": {"file_name": "manual.pdf"},
                }
            ]
            vector_service.search = AsyncMock(return_value=mock_results)

            # Act
            result = await service.retrieve_context(
                query="original query",
                vector_service=vector_service,
                embedding_service=embedding_service,
                conversation_history=[{"role": "user", "content": "previous message"}],
                user_id="U123",
            )

            # Assert
            assert len(result) == 1
            # Should use rewritten query for embedding
            embedding_service.get_embedding.assert_called_once_with("rewritten query")
            # Should pass filters to search
            call_args = vector_service.search.call_args
            assert call_args.kwargs["filter"] == {"document_type": "manual"}

    @pytest.mark.asyncio
    async def test_retrieve_context_filters_by_threshold(self):
        """Test that results below similarity threshold are filtered out."""
        # Arrange
        settings = Mock(spec=Settings)
        settings.rag = Mock(spec=RAGSettings)
        settings.rag.max_results = 5
        settings.rag.similarity_threshold = 0.35
        settings.rag.results_similarity_threshold = 0.7  # High threshold
        settings.rag.entity_content_boost = 0.05
        settings.rag.entity_title_boost = 0.1
        settings.rag.max_chunks_per_document = 3

        service = RetrievalService(settings, enable_query_rewriting=False)

        # Mock services
        embedding_service = AsyncMock()
        embedding_service.get_embedding = AsyncMock(return_value=[0.1, 0.2, 0.3])

        vector_service = AsyncMock()
        mock_results = [
            {
                "content": "High relevance content",
                "similarity": 0.9,
                "metadata": {"file_name": "doc1.pdf"},
            },
            {
                "content": "Medium relevance content",
                "similarity": 0.65,
                "metadata": {"file_name": "doc2.pdf"},
            },
            {
                "content": "Low relevance content",
                "similarity": 0.4,
                "metadata": {"file_name": "doc3.pdf"},
            },
        ]
        vector_service.search = AsyncMock(return_value=mock_results)

        # Act
        result = await service.retrieve_context(
            query="test query",
            vector_service=vector_service,
            embedding_service=embedding_service,
        )

        # Assert - Only first result should pass 0.7 threshold
        assert len(result) == 1
        assert result[0]["similarity"] >= 0.7

    @pytest.mark.asyncio
    async def test_retrieve_context_handles_errors(self):
        """Test that errors during retrieval are caught and empty list returned."""
        # Arrange
        settings = Mock(spec=Settings)
        settings.rag = Mock(spec=RAGSettings)
        settings.rag.max_results = 5
        settings.rag.similarity_threshold = 0.35
        settings.rag.results_similarity_threshold = 0.5

        service = RetrievalService(settings, enable_query_rewriting=False)

        # Mock services to raise exception
        embedding_service = AsyncMock()
        embedding_service.get_embedding = AsyncMock(
            side_effect=Exception("Embedding failed")
        )

        vector_service = AsyncMock()

        # Act
        result = await service.retrieve_context(
            query="test query",
            vector_service=vector_service,
            embedding_service=embedding_service,
        )

        # Assert
        assert result == []

    @pytest.mark.asyncio
    async def test_retrieve_context_empty_results(self):
        """Test handling of empty search results."""
        # Arrange
        settings = Mock(spec=Settings)
        settings.rag = Mock(spec=RAGSettings)
        settings.rag.max_results = 5
        settings.rag.similarity_threshold = 0.35
        settings.rag.results_similarity_threshold = 0.5

        service = RetrievalService(settings, enable_query_rewriting=False)

        # Mock services
        embedding_service = AsyncMock()
        embedding_service.get_embedding = AsyncMock(return_value=[0.1, 0.2, 0.3])

        vector_service = AsyncMock()
        vector_service.search = AsyncMock(return_value=[])

        # Act
        result = await service.retrieve_context(
            query="test query",
            vector_service=vector_service,
            embedding_service=embedding_service,
        )

        # Assert
        assert result == []

    @pytest.mark.asyncio
    async def test_retrieve_context_with_long_rewritten_query(self):
        """Test logging truncation with very long rewritten query."""
        # Arrange
        settings = Mock(spec=Settings)
        settings.rag = Mock(spec=RAGSettings)
        settings.rag.max_results = 5
        settings.rag.similarity_threshold = 0.35
        settings.rag.results_similarity_threshold = 0.5
        settings.rag.entity_content_boost = 0.05
        settings.rag.entity_title_boost = 0.1
        settings.rag.max_chunks_per_document = 3

        llm_service = Mock()

        service = RetrievalService(settings, llm_service=llm_service)

        # Mock query rewriter to return very long query
        mock_rewriter = AsyncMock()
        long_query = "a" * 1000  # Very long query that will be truncated in logs
        mock_rewriter.rewrite_query = AsyncMock(
            return_value={
                "query": long_query,
                "strategy": "entity_focused",
                "intent": {"type": "factual"},
                "filters": {},
            }
        )

        # Patch AdaptiveQueryRewriter
        with patch(
            "services.retrieval_service.AdaptiveQueryRewriter",
            return_value=mock_rewriter,
        ):
            # Mock services
            embedding_service = AsyncMock()
            embedding_service.get_embedding = AsyncMock(return_value=[0.1, 0.2, 0.3])

            vector_service = AsyncMock()
            mock_results = [
                {
                    "content": "Test content",
                    "similarity": 0.85,
                    "metadata": {"file_name": "test.pdf"},
                }
            ]
            vector_service.search = AsyncMock(return_value=mock_results)

            # Act
            result = await service.retrieve_context(
                query="original query",
                vector_service=vector_service,
                embedding_service=embedding_service,
            )

            # Assert
            assert len(result) == 1
            # Should use long rewritten query
            embedding_service.get_embedding.assert_called_once_with(long_query)


class TestRetrieveContextByEmbedding:
    """Test retrieve_context_by_embedding method."""

    @pytest.mark.asyncio
    async def test_retrieve_by_embedding_success(self):
        """Test successful retrieval using document embedding."""
        # Arrange
        settings = Mock(spec=Settings)
        settings.rag = Mock(spec=RAGSettings)
        settings.rag.max_results = 5
        settings.rag.similarity_threshold = 0.35
        settings.rag.max_chunks_per_document = 3

        service = RetrievalService(settings)

        # Mock vector service
        vector_service = AsyncMock()
        mock_results = [
            {
                "content": "Similar document content",
                "similarity": 0.85,
                "metadata": {"file_name": "similar_doc.pdf"},
            },
            {
                "content": "Another similar document",
                "similarity": 0.75,
                "metadata": {"file_name": "another_doc.pdf"},
            },
        ]
        vector_service.search = AsyncMock(return_value=mock_results)

        document_embedding = [0.1, 0.2, 0.3, 0.4, 0.5]

        # Act
        result = await service.retrieve_context_by_embedding(
            document_embedding=document_embedding,
            vector_service=vector_service,
        )

        # Assert
        assert len(result) == 2
        vector_service.search.assert_called_once()
        call_args = vector_service.search.call_args
        assert call_args.kwargs["query_embedding"] == document_embedding
        assert call_args.kwargs["query_text"] == ""

    @pytest.mark.asyncio
    async def test_retrieve_by_embedding_no_results(self):
        """Test handling when no similar documents found."""
        # Arrange
        settings = Mock(spec=Settings)
        settings.rag = Mock(spec=RAGSettings)
        settings.rag.max_results = 5
        settings.rag.similarity_threshold = 0.35
        settings.rag.max_chunks_per_document = 3

        service = RetrievalService(settings)

        # Mock vector service
        vector_service = AsyncMock()
        vector_service.search = AsyncMock(return_value=[])

        document_embedding = [0.1, 0.2, 0.3]

        # Act
        result = await service.retrieve_context_by_embedding(
            document_embedding=document_embedding,
            vector_service=vector_service,
        )

        # Assert
        assert result == []

    @pytest.mark.asyncio
    async def test_retrieve_by_embedding_handles_errors(self):
        """Test error handling during embedding-based retrieval."""
        # Arrange
        settings = Mock(spec=Settings)
        settings.rag = Mock(spec=RAGSettings)

        service = RetrievalService(settings)

        # Mock vector service to raise exception
        vector_service = AsyncMock()
        vector_service.search = AsyncMock(side_effect=Exception("Search failed"))

        document_embedding = [0.1, 0.2, 0.3]

        # Act
        result = await service.retrieve_context_by_embedding(
            document_embedding=document_embedding,
            vector_service=vector_service,
        )

        # Assert
        assert result == []


class TestEntityExtraction:
    """Test entity extraction and stop word filtering."""

    def test_extract_entities_simple(self):
        """Test basic entity extraction."""
        # Arrange
        settings = Mock(spec=Settings)
        settings.rag = Mock(spec=RAGSettings)
        service = RetrievalService(settings)

        query = "What is Python programming language"

        # Act
        entities = service._extract_entities_simple(query)

        # Assert
        assert "python" in entities
        assert "programming" in entities
        assert "language" in entities
        # Stop words should be filtered out
        assert "what" not in entities
        assert "is" not in entities

    def test_extract_entities_filters_stop_words(self):
        """Test that stop words are properly filtered."""
        # Arrange
        settings = Mock(spec=Settings)
        settings.rag = Mock(spec=RAGSettings)
        service = RetrievalService(settings)

        query = "How can I use the Docker container with Python"

        # Act
        entities = service._extract_entities_simple(query)

        # Assert
        assert "docker" in entities
        assert "container" in entities
        assert "python" in entities
        # Stop words should be filtered
        assert "how" not in entities
        assert "can" not in entities
        assert "the" not in entities
        assert "with" not in entities

    def test_extract_entities_with_special_characters(self):
        """Test entity extraction with special characters."""
        # Arrange
        settings = Mock(spec=Settings)
        settings.rag = Mock(spec=RAGSettings)
        service = RetrievalService(settings)

        query = "API-Gateway configuration in AWS-EC2"

        # Act
        entities = service._extract_entities_simple(query)

        # Assert
        assert "api" in entities
        assert "gateway" in entities
        assert "configuration" in entities
        assert "aws" in entities
        assert "ec2" in entities

    def test_extract_entities_minimum_length(self):
        """Test that single character words are filtered out."""
        # Arrange
        settings = Mock(spec=Settings)
        settings.rag = Mock(spec=RAGSettings)
        service = RetrievalService(settings)

        query = "I a Go API"

        # Act
        entities = service._extract_entities_simple(query)

        # Assert
        assert "go" in entities
        assert "api" in entities
        # Single characters should be filtered
        assert "i" not in entities
        assert "a" not in entities

    def test_extract_entities_empty_query(self):
        """Test entity extraction with empty query."""
        # Arrange
        settings = Mock(spec=Settings)
        settings.rag = Mock(spec=RAGSettings)
        service = RetrievalService(settings)

        # Act
        entities = service._extract_entities_simple("")

        # Assert
        assert entities == set()

    def test_extract_entities_only_stop_words(self):
        """Test entity extraction when query contains only stop words."""
        # Arrange
        settings = Mock(spec=Settings)
        settings.rag = Mock(spec=RAGSettings)
        service = RetrievalService(settings)

        query = "what is the"

        # Act
        entities = service._extract_entities_simple(query)

        # Assert
        assert entities == set()


class TestEntityBoosting:
    """Test entity boosting logic."""

    def test_apply_entity_boosting_content_match(self):
        """Test entity boosting when entities match in content."""
        # Arrange
        settings = Mock(spec=Settings)
        settings.rag = Mock(spec=RAGSettings)
        settings.rag.entity_content_boost = 0.05
        settings.rag.entity_title_boost = 0.1

        service = RetrievalService(settings)

        query = "Python programming"
        results = [
            {
                "content": "This document covers Python programming fundamentals",
                "similarity": 0.6,
                "metadata": {"file_name": "tutorial.pdf"},
            }
        ]

        # Act
        boosted_results = service._apply_entity_boosting(query, results)

        # Assert
        assert len(boosted_results) == 1
        # Should have boosted for "python" and "programming" in content
        assert boosted_results[0]["similarity"] > 0.6
        assert boosted_results[0]["_original_similarity"] == 0.6
        assert boosted_results[0]["_entity_boost"] > 0
        assert boosted_results[0]["_matching_entities"] >= 2

    def test_apply_entity_boosting_title_match(self):
        """Test entity boosting when entities match in title/filename."""
        # Arrange
        settings = Mock(spec=Settings)
        settings.rag = Mock(spec=RAGSettings)
        settings.rag.entity_content_boost = 0.05
        settings.rag.entity_title_boost = 0.1

        service = RetrievalService(settings)

        query = "Python tutorial"
        results = [
            {
                "content": "Basic programming concepts",
                "similarity": 0.5,
                "metadata": {"file_name": "Python_Tutorial.pdf"},
            }
        ]

        # Act
        boosted_results = service._apply_entity_boosting(query, results)

        # Assert
        assert len(boosted_results) == 1
        # Should have significant boost for title match
        assert boosted_results[0]["similarity"] > 0.5
        assert boosted_results[0]["_entity_boost"] > 0

    def test_apply_entity_boosting_multiple_results(self):
        """Test entity boosting with multiple results and sorting."""
        # Arrange
        settings = Mock(spec=Settings)
        settings.rag = Mock(spec=RAGSettings)
        settings.rag.entity_content_boost = 0.05
        settings.rag.entity_title_boost = 0.1

        service = RetrievalService(settings)

        query = "Docker container"
        results = [
            {
                "content": "General content",
                "similarity": 0.8,
                "metadata": {"file_name": "general.pdf"},
            },
            {
                "content": "Docker container deployment guide",
                "similarity": 0.6,
                "metadata": {"file_name": "docker_guide.pdf"},
            },
        ]

        # Act
        boosted_results = service._apply_entity_boosting(query, results)

        # Assert
        assert len(boosted_results) == 2
        # Results should be re-sorted by boosted similarity
        # Second result should be boosted significantly
        assert boosted_results[0]["_entity_boost"] >= 0

    def test_apply_entity_boosting_max_similarity_capped(self):
        """Test that boosted similarity is capped at 1.0."""
        # Arrange
        settings = Mock(spec=Settings)
        settings.rag = Mock(spec=RAGSettings)
        settings.rag.entity_content_boost = 0.5  # Very high boost
        settings.rag.entity_title_boost = 0.5

        service = RetrievalService(settings)

        query = "Python programming tutorial"
        results = [
            {
                "content": "Python programming tutorial with Python examples",
                "similarity": 0.9,
                "metadata": {"file_name": "Python_Tutorial.pdf"},
            }
        ]

        # Act
        boosted_results = service._apply_entity_boosting(query, results)

        # Assert
        assert boosted_results[0]["similarity"] <= 1.0

    def test_apply_entity_boosting_no_matches(self):
        """Test entity boosting when no entities match."""
        # Arrange
        settings = Mock(spec=Settings)
        settings.rag = Mock(spec=RAGSettings)
        settings.rag.entity_content_boost = 0.05
        settings.rag.entity_title_boost = 0.1

        service = RetrievalService(settings)

        query = "Python programming"
        results = [
            {
                "content": "JavaScript fundamentals",
                "similarity": 0.5,
                "metadata": {"file_name": "javascript.pdf"},
            }
        ]

        # Act
        boosted_results = service._apply_entity_boosting(query, results)

        # Assert
        assert len(boosted_results) == 1
        # No boost should be applied
        assert boosted_results[0]["similarity"] == 0.5
        assert boosted_results[0]["_entity_boost"] == 0.0

    def test_apply_entity_boosting_handles_errors(self):
        """Test that entity boosting errors don't break retrieval."""
        # Arrange
        settings = Mock(spec=Settings)
        settings.rag = Mock(spec=RAGSettings)
        settings.rag.entity_content_boost = 0.05
        settings.rag.entity_title_boost = 0.1

        service = RetrievalService(settings)

        query = "test query"
        # Create a result that will cause an exception during processing
        bad_result = {
            "content": "test content",
            "similarity": 0.5,
            "metadata": {"file_name": "test.pdf"},
        }
        results = [bad_result]

        # Mock _extract_entities_simple to raise an exception
        with patch.object(
            service, "_extract_entities_simple", side_effect=Exception("Entity extraction failed")
        ):
            # Act
            boosted_results = service._apply_entity_boosting(query, results)

            # Assert - Should return original results on error
            assert boosted_results == results


class TestDiversificationStrategies:
    """Test diversification strategies."""

    def test_smart_similarity_diversify_limits_per_document(self):
        """Test that diversification limits chunks per document."""
        # Arrange
        settings = Mock(spec=Settings)
        settings.rag = Mock(spec=RAGSettings)
        settings.rag.max_results = 10
        settings.rag.max_chunks_per_document = 3

        service = RetrievalService(settings)

        # Multiple chunks from same document
        results = [
            {
                "content": f"Content chunk {i}",
                "similarity": 0.9 - (i * 0.01),
                "metadata": {"file_name": "doc1.pdf"},
            }
            for i in range(5)
        ]

        # Act
        diversified = service._smart_similarity_diversify(results, 10)

        # Assert
        # Should only return 3 chunks from doc1.pdf
        assert len(diversified) == 3
        assert all(r["metadata"]["file_name"] == "doc1.pdf" for r in diversified)

    def test_smart_similarity_diversify_multiple_documents(self):
        """Test diversification across multiple documents."""
        # Arrange
        settings = Mock(spec=Settings)
        settings.rag = Mock(spec=RAGSettings)
        settings.rag.max_results = 6
        settings.rag.max_chunks_per_document = 2

        service = RetrievalService(settings)

        # Chunks from three different documents
        results = [
            {
                "content": "Doc1 chunk 1",
                "similarity": 0.9,
                "metadata": {"file_name": "doc1.pdf"},
            },
            {
                "content": "Doc2 chunk 1",
                "similarity": 0.85,
                "metadata": {"file_name": "doc2.pdf"},
            },
            {
                "content": "Doc1 chunk 2",
                "similarity": 0.8,
                "metadata": {"file_name": "doc1.pdf"},
            },
            {
                "content": "Doc3 chunk 1",
                "similarity": 0.75,
                "metadata": {"file_name": "doc3.pdf"},
            },
            {
                "content": "Doc1 chunk 3",
                "similarity": 0.7,
                "metadata": {"file_name": "doc1.pdf"},
            },
            {
                "content": "Doc2 chunk 2",
                "similarity": 0.65,
                "metadata": {"file_name": "doc2.pdf"},
            },
        ]

        # Act
        diversified = service._smart_similarity_diversify(results, 6)

        # Assert
        # Doc1 has 3 chunks but max_per_doc is 2, so only 5 total chunks returned
        assert len(diversified) == 5
        # Count chunks per document
        doc1_count = sum(1 for r in diversified if r["metadata"]["file_name"] == "doc1.pdf")
        doc2_count = sum(1 for r in diversified if r["metadata"]["file_name"] == "doc2.pdf")
        doc3_count = sum(1 for r in diversified if r["metadata"]["file_name"] == "doc3.pdf")

        assert doc1_count <= 2
        assert doc2_count <= 2
        assert doc3_count <= 2

    def test_smart_similarity_diversify_metric_data(self):
        """Test diversification with metric data (no file_name)."""
        # Arrange
        settings = Mock(spec=Settings)
        settings.rag = Mock(spec=RAGSettings)
        settings.rag.max_results = 5
        settings.rag.max_chunks_per_document = 3

        service = RetrievalService(settings)

        # Metric data without file_name
        results = [
            {
                "content": f"Metric data {i}",
                "similarity": 0.9 - (i * 0.1),
                "metadata": {"type": "metric"},
            }
            for i in range(10)
        ]

        # Act
        diversified = service._smart_similarity_diversify(results, 5)

        # Assert
        # Should return pure similarity order, no document limiting
        assert len(diversified) == 5
        assert diversified[0]["similarity"] == 0.9

    def test_smart_similarity_diversify_unknown_filename(self):
        """Test diversification with 'Unknown' filename."""
        # Arrange
        settings = Mock(spec=Settings)
        settings.rag = Mock(spec=RAGSettings)
        settings.rag.max_results = 5
        settings.rag.max_chunks_per_document = 2

        service = RetrievalService(settings)

        results = [
            {
                "content": f"Content {i}",
                "similarity": 0.9 - (i * 0.1),
                "metadata": {"file_name": "Unknown"},
            }
            for i in range(5)
        ]

        # Act
        diversified = service._smart_similarity_diversify(results, 5)

        # Assert
        # "Unknown" should be treated like metric data
        assert len(diversified) == 5

    def test_smart_similarity_diversify_empty_results(self):
        """Test diversification with empty results."""
        # Arrange
        settings = Mock(spec=Settings)
        settings.rag = Mock(spec=RAGSettings)
        settings.rag.max_results = 5
        settings.rag.max_chunks_per_document = 3

        service = RetrievalService(settings)

        # Act
        diversified = service._smart_similarity_diversify([], 5)

        # Assert
        assert diversified == []

    def test_smart_similarity_diversify_respects_max_results(self):
        """Test that diversification respects max_results limit."""
        # Arrange
        settings = Mock(spec=Settings)
        settings.rag = Mock(spec=RAGSettings)
        settings.rag.max_chunks_per_document = 5

        service = RetrievalService(settings)

        results = [
            {
                "content": f"Content {i}",
                "similarity": 0.9,
                "metadata": {"file_name": f"doc{i}.pdf"},
            }
            for i in range(20)
        ]

        # Act
        diversified = service._smart_similarity_diversify(results, 10)

        # Assert
        assert len(diversified) == 10

    def test_apply_diversification_strategy(self):
        """Test apply_diversification_strategy wrapper method."""
        # Arrange
        settings = Mock(spec=Settings)
        settings.rag = Mock(spec=RAGSettings)
        settings.rag.max_results = 5
        settings.rag.max_chunks_per_document = 3

        service = RetrievalService(settings)

        results = [
            {
                "content": f"Content {i}",
                "similarity": 0.9,
                "metadata": {"file_name": "doc.pdf"},
            }
            for i in range(10)
        ]

        # Act
        diversified = service._apply_diversification_strategy(results)

        # Assert
        assert len(diversified) <= settings.rag.max_results

    def test_apply_diversification_strategy_empty_results(self):
        """Test diversification strategy with empty results."""
        # Arrange
        settings = Mock(spec=Settings)
        settings.rag = Mock(spec=RAGSettings)
        settings.rag.max_results = 5

        service = RetrievalService(settings)

        # Act
        diversified = service._apply_diversification_strategy([])

        # Assert
        assert diversified == []


class TestStopWords:
    """Test STOP_WORDS constant."""

    def test_stop_words_contains_common_words(self):
        """Test that STOP_WORDS contains common filler words."""
        # Assert
        assert "the" in STOP_WORDS
        assert "and" in STOP_WORDS
        assert "is" in STOP_WORDS
        assert "what" in STOP_WORDS
        assert "how" in STOP_WORDS
        assert "can" in STOP_WORDS

    def test_stop_words_is_set(self):
        """Test that STOP_WORDS is a set for O(1) lookups."""
        # Assert
        assert isinstance(STOP_WORDS, set)

    def test_stop_words_lowercase(self):
        """Test that all stop words are lowercase."""
        # Assert
        assert all(word.islower() for word in STOP_WORDS)
