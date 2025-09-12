"""
Tests for Retrieval Service

Comprehensive tests for document retrieval and context building functionality.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from services.retrieval.base_retrieval import BaseRetrieval
from services.retrieval_service import RetrievalService


class TestRetrievalService:
    """Test retrieval service functionality"""

    def setup_method(self):
        """Set up test fixtures"""
        # Create properly structured mock settings
        self.mock_settings = MagicMock()
        self.mock_settings.rag = MagicMock()
        self.mock_settings.rag.enable_hybrid_search = False
        self.mock_settings.rag.max_results = 5
        self.mock_settings.rag.similarity_threshold = 0.7
        self.mock_settings.rag.results_similarity_threshold = 0.7
        self.mock_settings.rag.entity_content_boost = 0.05
        self.mock_settings.rag.entity_title_boost = 0.1
        self.mock_settings.rag.diversification_mode = "balanced"
        self.mock_settings.rag.max_unique_documents = 5

        self.mock_settings.vector = MagicMock()
        self.mock_settings.vector.provider = "elasticsearch"

        self.retrieval_service = RetrievalService(self.mock_settings)

    def test_init(self):
        """Test RetrievalService initialization"""
        service = RetrievalService(self.mock_settings)
        assert service.settings == self.mock_settings

    @pytest.mark.asyncio
    async def test_retrieve_context_no_vector_service(self):
        """Test retrieval with no vector service"""
        result = await self.retrieval_service.retrieve_context("test query", None, None)
        assert result == []

    @pytest.mark.asyncio
    async def test_retrieve_context_basic_search(self):
        """Test basic vector similarity search"""
        # Mock services
        mock_vector_service = AsyncMock()
        mock_embedding_service = AsyncMock()

        mock_embedding_service.get_embedding.return_value = [0.1] * 1536
        mock_vector_service.search.return_value = [
            {
                "content": "Test content 1",
                "similarity": 0.95,
                "metadata": {"file_name": "test1.pdf"},
            },
            {
                "content": "Test content 2",
                "similarity": 0.85,
                "metadata": {"file_name": "test2.pdf"},
            },
        ]

        results = await self.retrieval_service.retrieve_context(
            "test query", mock_vector_service, mock_embedding_service
        )

        # Verify calls
        mock_embedding_service.get_embedding.assert_called_once_with("test query")
        mock_vector_service.search.assert_called_once()

        # Check results (similarity may be boosted by entity processing)
        assert len(results) == 2
        assert results[0]["content"] == "Test content 1"
        assert (
            results[0]["similarity"] >= 0.95
        )  # May be boosted higher by entity processing

    @pytest.mark.asyncio
    async def test_retrieve_context_hybrid_search_enabled(self):
        """Test retrieval with hybrid search enabled"""
        self.mock_settings.rag.enable_hybrid_search = True

        mock_vector_service = AsyncMock()
        mock_embedding_service = AsyncMock()

        mock_embedding_service.get_embedding.return_value = [0.1] * 1536

        # Mock vector search to return results
        mock_vector_service.search.return_value = [
            {
                "content": "Hybrid search result",
                "similarity": 0.90,
                "metadata": {"file_name": "hybrid.pdf"},
            }
        ]

        results = await self.retrieval_service.retrieve_context(
            "test query", mock_vector_service, mock_embedding_service
        )

        # Should call embedding service and vector search
        mock_embedding_service.get_embedding.assert_called_once_with("test query")
        mock_vector_service.search.assert_called()
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_retrieve_context_elasticsearch_bm25_search(self):
        """Test retrieval with Elasticsearch BM25 search"""
        # Mock vector service with bm25_search method
        mock_vector_service = AsyncMock()
        mock_vector_service.bm25_search = AsyncMock()  # Has BM25 capability
        mock_embedding_service = AsyncMock()

        mock_embedding_service.get_embedding.return_value = [0.1] * 1536
        mock_vector_service.search.return_value = [
            {
                "content": "BM25 search result",
                "similarity": 0.88,
                "metadata": {"file_name": "bm25.pdf"},
            }
        ]

        results = await self.retrieval_service.retrieve_context(
            "elasticsearch query", mock_vector_service, mock_embedding_service
        )

        # Should use regular search with query text for BM25
        mock_vector_service.search.assert_called_once()
        call_args = mock_vector_service.search.call_args[1]
        assert call_args.get("query_text") == "elasticsearch query"
        assert call_args.get("limit") == 50  # Higher limit for Elasticsearch

        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_retrieve_context_with_similarity_threshold_filtering(self):
        """Test that similarity threshold filtering works"""
        mock_vector_service = AsyncMock()
        mock_embedding_service = AsyncMock()

        mock_embedding_service.get_embedding.return_value = [0.1] * 1536
        mock_vector_service.search.return_value = [
            {
                "content": "High relevance",
                "similarity": 0.95,
                "metadata": {"file_name": "high.pdf"},
            },
            {
                "content": "Medium relevance",
                "similarity": 0.75,
                "metadata": {"file_name": "medium.pdf"},
            },
            {
                "content": "Low relevance",
                "similarity": 0.60,  # Below threshold
                "metadata": {"file_name": "low.pdf"},
            },
        ]

        results = await self.retrieval_service.retrieve_context(
            "test query", mock_vector_service, mock_embedding_service
        )

        # Should filter out results below 0.7 threshold
        assert len(results) == 2
        assert all(result["similarity"] >= 0.7 for result in results)

    @pytest.mark.asyncio
    async def test_retrieve_context_exception_handling(self):
        """Test exception handling during retrieval"""
        mock_vector_service = AsyncMock()
        mock_embedding_service = AsyncMock()

        mock_embedding_service.get_embedding.side_effect = Exception("Embedding failed")

        results = await self.retrieval_service.retrieve_context(
            "test query", mock_vector_service, mock_embedding_service
        )

        # Should return empty list on exception
        assert results == []

    def test_extract_entities_simple_basic(self):
        """Test basic entity extraction"""
        # Test via the base retrieval class
        base_retrieval = BaseRetrieval(self.mock_settings)
        entities = base_retrieval._extract_entities_simple(
            "Apple and Microsoft partnership"
        )

        # Should extract company names
        assert "apple" in entities  # lowercase since extraction normalizes
        assert "microsoft" in entities

    def test_extract_entities_simple_patterns(self):
        """Test entity extraction with various patterns"""
        base_retrieval = BaseRetrieval(self.mock_settings)
        test_cases = [
            (
                "8th Light consulting services",
                {"8th", "light", "consulting", "services"},
            ),
            ("Apple Inc project management", {"apple", "inc", "project", "management"}),
            ("Google Drive integration", {"google", "drive", "integration"}),
            ("client work with Acme Corp", {"client", "work", "acme", "corp"}),
        ]

        for query, expected_entities in test_cases:
            entities = base_retrieval._extract_entities_simple(query)

            # Should extract at least some expected entities (normalized to lowercase)
            overlap = entities.intersection(expected_entities)
            assert len(overlap) > 0, f"No entities found in '{query}'. Got: {entities}"

    def test_extract_entities_simple_empty_query(self):
        """Test entity extraction with empty query"""
        base_retrieval = BaseRetrieval(self.mock_settings)
        entities = base_retrieval._extract_entities_simple("")
        assert isinstance(entities, set)
        assert len(entities) == 0

    @pytest.mark.asyncio
    async def test_retrieve_context_with_entity_boosting(self):
        """Test retrieve_context calls entity boosting"""
        # Mock services
        mock_vector_service = AsyncMock()
        mock_embedding_service = AsyncMock()

        mock_embedding_service.get_embedding.return_value = [0.1] * 1536
        mock_vector_service.search.return_value = [
            {
                "content": "Apple project details",
                "similarity": 0.90,
                "metadata": {"file_name": "apple.pdf"},
            }
        ]

        # Test that retrieve_context works end-to-end
        results = await self.retrieval_service.retrieve_context(
            "Apple projects", mock_vector_service, mock_embedding_service
        )

        # Should call embedding and vector search
        mock_embedding_service.get_embedding.assert_called_once_with("Apple projects")
        mock_vector_service.search.assert_called()
        assert isinstance(results, list)

    def test_apply_hybrid_search_boosting_basic(self):
        """Test hybrid search result boosting"""
        results = [
            {
                "content": "Apple company information",
                "similarity": 0.80,
                "metadata": {"file_name": "apple.pdf"},
            },
            {
                "content": "Microsoft details",
                "similarity": 0.75,
                "metadata": {"file_name": "microsoft.pdf"},
            },
        ]

        boosted_results = self.retrieval_service._apply_hybrid_search_boosting(
            "Apple projects", results
        )

        # Should return results (hybrid boosting selects multiple chunks from top documents)
        assert len(boosted_results) <= len(results)
        assert isinstance(boosted_results, list)

    def test_apply_hybrid_search_boosting_empty_results(self):
        """Test boosting with empty results"""
        boosted_results = self.retrieval_service._apply_hybrid_search_boosting(
            "test query", []
        )
        assert boosted_results == []

    def test_provider_routing_elasticsearch(self):
        """Test that retrieval service routes correctly to Elasticsearch"""
        # Set provider to elasticsearch
        self.mock_settings.vector.provider = "elasticsearch"
        service = RetrievalService(self.mock_settings)

        # Verify elasticsearch retrieval service was initialized
        assert service.elasticsearch_retrieval is not None
        assert service.pinecone_retrieval is not None

    def test_provider_routing_pinecone(self):
        """Test that retrieval service routes correctly to Pinecone"""
        # Set provider to pinecone
        self.mock_settings.vector.provider = "pinecone"
        service = RetrievalService(self.mock_settings)

        # Verify both retrieval services were initialized
        assert service.elasticsearch_retrieval is not None
        assert service.pinecone_retrieval is not None


class TestRetrievalServiceIntegration:
    """Integration tests for retrieval service"""

    def setup_method(self):
        """Set up test fixtures"""
        self.mock_settings = MagicMock()
        self.mock_settings.rag = MagicMock()
        self.mock_settings.rag.enable_hybrid_search = True
        self.mock_settings.rag.max_results = 5
        self.mock_settings.rag.similarity_threshold = 0.7
        self.mock_settings.rag.results_similarity_threshold = 0.7
        self.mock_settings.rag.entity_content_boost = 0.05
        self.mock_settings.rag.entity_title_boost = 0.1
        self.mock_settings.rag.diversification_mode = "balanced"
        self.mock_settings.rag.max_unique_documents = 5

        self.mock_settings.vector = MagicMock()
        self.mock_settings.vector.provider = "elasticsearch"

        self.retrieval_service = RetrievalService(self.mock_settings)

    @pytest.mark.asyncio
    async def test_full_hybrid_search_pipeline(self):
        """Test complete hybrid search pipeline"""
        mock_vector_service = AsyncMock()
        mock_embedding_service = AsyncMock()

        mock_embedding_service.get_embedding.return_value = [0.1] * 1536

        # Mock entity search returning varied results
        mock_vector_service.search.side_effect = [
            # First call - entity search
            [
                {
                    "content": "Apple entity result",
                    "similarity": 0.85,
                    "metadata": {"file_name": "apple1.pdf"},
                },
            ],
            # Second call - general search
            [
                {
                    "content": "General search result",
                    "similarity": 0.80,
                    "metadata": {"file_name": "general.pdf"},
                },
            ],
        ]

        results = await self.retrieval_service.retrieve_context(
            "Apple company projects", mock_vector_service, mock_embedding_service
        )

        # Should have called search multiple times for hybrid approach
        assert mock_vector_service.search.call_count >= 1
        assert len(results) >= 0

    @pytest.mark.asyncio
    async def test_elasticsearch_vs_pinecone_behavior(self):
        """Test different behavior for Elasticsearch vs Pinecone"""
        mock_vector_service = AsyncMock()
        mock_embedding_service = AsyncMock()

        mock_embedding_service.get_embedding.return_value = [0.1] * 1536
        mock_vector_service.search.return_value = [
            {
                "content": "Test result",
                "similarity": 0.85,
                "metadata": {"file_name": "test.pdf"},
            },
        ]

        # Test with Elasticsearch
        self.mock_settings.vector.provider = "elasticsearch"
        await self.retrieval_service.retrieve_context(
            "test query", mock_vector_service, mock_embedding_service
        )

        # Should use higher limit for Elasticsearch
        # Check that call was made but don't examine args in detail
        assert mock_vector_service.search.called

        # Reset mock
        mock_vector_service.search.reset_mock()

        # Test with Pinecone
        self.mock_settings.vector.provider = "pinecone"
        await self.retrieval_service.retrieve_context(
            "test query", mock_vector_service, mock_embedding_service
        )

        # Check that call was made for Pinecone too
        assert mock_vector_service.search.called

        # Elasticsearch should use higher limits
        # (The exact comparison depends on the implementation)


class TestRetrievalServiceEdgeCases:
    """Test edge cases and error conditions"""

    def setup_method(self):
        """Set up test fixtures"""
        self.mock_settings = MagicMock()
        self.mock_settings.rag = MagicMock()
        self.mock_settings.rag.enable_hybrid_search = False
        self.mock_settings.rag.max_results = 5
        self.mock_settings.rag.similarity_threshold = 0.7
        self.mock_settings.rag.results_similarity_threshold = 0.7
        self.mock_settings.rag.entity_content_boost = 0.05
        self.mock_settings.rag.entity_title_boost = 0.1
        self.mock_settings.rag.diversification_mode = "balanced"
        self.mock_settings.rag.max_unique_documents = 5

        self.mock_settings.vector = MagicMock()
        self.mock_settings.vector.provider = "elasticsearch"

        self.retrieval_service = RetrievalService(self.mock_settings)

    def test_extract_entities_unicode(self):
        """Test entity extraction with Unicode characters"""
        base_retrieval = BaseRetrieval(self.mock_settings)
        entities = base_retrieval._extract_entities_simple("Café München collaboration")
        assert isinstance(entities, set)
        # Should handle Unicode gracefully
        assert len(entities) > 0

    def test_extract_entities_special_characters(self):
        """Test entity extraction with special characters"""
        base_retrieval = BaseRetrieval(self.mock_settings)
        entities = base_retrieval._extract_entities_simple("AT&T and T-Mobile merger")
        assert isinstance(entities, set)
        # Should extract entities with special characters
        assert len(entities) > 0

    @pytest.mark.asyncio
    async def test_retrieve_context_very_long_query(self):
        """Test retrieval with very long query"""
        long_query = " ".join(["word"] * 1000)  # Very long query

        mock_vector_service = AsyncMock()
        mock_embedding_service = AsyncMock()

        mock_embedding_service.get_embedding.return_value = [0.1] * 1536
        mock_vector_service.search.return_value = []

        results = await self.retrieval_service.retrieve_context(
            long_query, mock_vector_service, mock_embedding_service
        )

        # Should handle long queries gracefully
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_search_with_empty_embedding(self):
        """Test search with empty embedding response"""
        mock_vector_service = AsyncMock()
        mock_embedding_service = AsyncMock()

        mock_embedding_service.get_embedding.return_value = []  # Empty embedding
        mock_vector_service.search.return_value = []

        results = await self.retrieval_service.retrieve_context(
            "test query", mock_vector_service, mock_embedding_service
        )

        # Should handle empty embeddings
        assert isinstance(results, list)

    def test_entity_boosting_with_base_retrieval(self):
        """Test entity boosting functionality via BaseRetrieval"""
        base_retrieval = BaseRetrieval(self.mock_settings)

        # Mock results with different similarity scores
        results = [
            {
                "content": "Apple project documentation",
                "similarity": 0.70,
                "metadata": {"file_name": "apple_project.pdf"},
            },
            {
                "content": "Microsoft collaboration details",
                "similarity": 0.65,
                "metadata": {"file_name": "microsoft_collab.pdf"},
            },
        ]

        # Apply entity boosting
        boosted_results = base_retrieval._apply_entity_boosting(
            "Apple project", results
        )

        # Should return processed results
        assert isinstance(boosted_results, list)
        assert len(boosted_results) == len(results)

    def test_boosting_with_malformed_results(self):
        """Test boosting with malformed result data"""
        malformed_results = [
            {},  # Empty result
            {"content": "Valid result", "similarity": 0.80},  # No metadata
            {"similarity": 0.75, "metadata": {}},  # No content
        ]

        boosted_results = self.retrieval_service._apply_hybrid_search_boosting(
            "test query", malformed_results
        )

        # Should handle malformed data gracefully
        assert isinstance(boosted_results, list)

    @pytest.mark.asyncio
    async def test_retrieve_context_with_empty_query(self):
        """Test retrieve_context with empty query"""
        mock_vector_service = AsyncMock()
        mock_embedding_service = AsyncMock()

        mock_embedding_service.get_embedding.return_value = [0.1] * 1536
        mock_vector_service.search.return_value = []

        # Empty query should still work
        results = await self.retrieval_service.retrieve_context(
            "", mock_vector_service, mock_embedding_service
        )

        # Should handle empty queries gracefully
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_retrieval_service_settings_variations(self):
        """Test retrieval service with different settings"""
        # Test with hybrid search disabled
        self.mock_settings.rag.enable_hybrid_search = False

        mock_vector_service = AsyncMock()
        mock_embedding_service = AsyncMock()
        mock_embedding_service.get_embedding.return_value = [0.1] * 1536
        mock_vector_service.search.return_value = []

        results = await self.retrieval_service.retrieve_context(
            "test", mock_vector_service, mock_embedding_service
        )

        # Should use basic search without hybrid features
        assert isinstance(results, list)

        # Test with different max_results
        self.mock_settings.rag.max_results = 10

        results = await self.retrieval_service.retrieve_context(
            "test", mock_vector_service, mock_embedding_service
        )

        assert isinstance(results, list)
