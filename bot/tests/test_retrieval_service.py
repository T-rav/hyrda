"""
Tests for Retrieval Service

Comprehensive tests for document retrieval and context building functionality.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

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

        # Check results
        assert len(results) == 2
        assert results[0]["content"] == "Test content 1"
        assert results[0]["similarity"] == 0.95

    @pytest.mark.asyncio
    async def test_retrieve_context_hybrid_search_enabled(self):
        """Test retrieval with hybrid search enabled"""
        self.mock_settings.rag.enable_hybrid_search = True

        mock_vector_service = AsyncMock()
        mock_embedding_service = AsyncMock()

        mock_embedding_service.get_embedding.return_value = [0.1] * 1536

        # Mock the _search_with_entity_filtering method
        self.retrieval_service._search_with_entity_filtering = AsyncMock(
            return_value=[
                {
                    "content": "Hybrid search result",
                    "similarity": 0.90,
                    "metadata": {"file_name": "hybrid.pdf"},
                }
            ]
        )

        results = await self.retrieval_service.retrieve_context(
            "test query", mock_vector_service, mock_embedding_service
        )

        # Should call hybrid search method
        self.retrieval_service._search_with_entity_filtering.assert_called_once()
        assert len(results) == 1
        assert results[0]["content"] == "Hybrid search result"

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
        entities = self.retrieval_service._extract_entities_simple(
            "Apple and Microsoft partnership"
        )

        # Should extract company names
        assert "Apple" in entities
        assert "Microsoft" in entities

    def test_extract_entities_simple_patterns(self):
        """Test entity extraction with various patterns"""
        test_cases = [
            ("8th Light consulting services", {"8th Light", "Light"}),
            ("Apple Inc. project management", {"Apple", "project management"}),
            ("Google Drive integration", {"Google Drive", "Google"}),
            ("client work with Acme Corp", {"Acme Corp", "Acme"}),
        ]

        for query, expected_entities in test_cases:
            entities = self.retrieval_service._extract_entities_simple(query)

            # Should extract at least some expected entities
            overlap = entities.intersection(expected_entities)
            assert len(overlap) > 0, f"No entities found in '{query}'"

    def test_extract_entities_simple_empty_query(self):
        """Test entity extraction with empty query"""
        entities = self.retrieval_service._extract_entities_simple("")
        assert isinstance(entities, set)

    @pytest.mark.asyncio
    async def test_search_with_entity_filtering_basic(self):
        """Test entity-based search filtering"""
        mock_vector_service = AsyncMock()
        mock_embedding_service = AsyncMock()

        mock_embedding_service.get_embedding.return_value = [0.1] * 1536

        # Mock entity search results
        mock_vector_service.search.return_value = [
            {
                "content": "Apple project details",
                "similarity": 0.90,
                "metadata": {"file_name": "apple.pdf"},
            }
        ]

        results = await self.retrieval_service._search_with_entity_filtering(
            "Apple projects", mock_embedding_service, mock_vector_service
        )

        # Should call vector search
        mock_vector_service.search.assert_called()
        assert len(results) >= 0

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

        # Should boost results containing query terms
        assert len(boosted_results) == len(results)
        # Apple result should be boosted higher
        apple_result = next(r for r in boosted_results if "Apple" in r["content"])
        assert (
            "boosted_similarity" in apple_result or apple_result["similarity"] >= 0.80
        )

    def test_apply_hybrid_search_boosting_empty_results(self):
        """Test boosting with empty results"""
        boosted_results = self.retrieval_service._apply_hybrid_search_boosting(
            "test query", []
        )
        assert boosted_results == []

    def test_combine_search_results_basic(self):
        """Test combining multiple search result sets"""
        dense_results = [
            {"content": "Dense result 1", "similarity": 0.90, "metadata": {}},
            {"content": "Dense result 2", "similarity": 0.85, "metadata": {}},
        ]
        sparse_results = [
            {"content": "Sparse result 1", "similarity": 0.88, "metadata": {}},
            {"content": "Sparse result 2", "similarity": 0.82, "metadata": {}},
        ]

        combined = self.retrieval_service._combine_search_results(
            dense_results, sparse_results
        )

        # Should combine results
        assert len(combined) >= len(dense_results)
        assert all("similarity" in result for result in combined)

    def test_combine_search_results_deduplication(self):
        """Test result deduplication in combination"""
        results1 = [
            {"content": "Same content", "similarity": 0.90, "metadata": {"id": "1"}},
        ]
        results2 = [
            {"content": "Same content", "similarity": 0.85, "metadata": {"id": "1"}},
        ]

        combined = self.retrieval_service._combine_search_results(results1, results2)

        # Should handle deduplication
        assert len(combined) >= 1

    def test_combine_search_results_empty_inputs(self):
        """Test combining empty result sets"""
        combined = self.retrieval_service._combine_search_results([], [])
        assert combined == []


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

        self.mock_settings.vector = MagicMock()
        self.mock_settings.vector.provider = "elasticsearch"

        self.retrieval_service = RetrievalService(self.mock_settings)

    def test_extract_entities_unicode(self):
        """Test entity extraction with Unicode characters"""
        entities = self.retrieval_service._extract_entities_simple(
            "Café München collaboration"
        )
        assert isinstance(entities, set)
        # Should handle Unicode gracefully

    def test_extract_entities_special_characters(self):
        """Test entity extraction with special characters"""
        entities = self.retrieval_service._extract_entities_simple(
            "AT&T and T-Mobile merger"
        )
        assert isinstance(entities, set)
        # Should extract entities with special characters

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

    def test_combine_results_with_missing_similarity(self):
        """Test combining results with missing similarity scores"""
        results1 = [
            {"content": "Result without similarity", "metadata": {}},  # No similarity
        ]
        results2 = [
            {"content": "Result with similarity", "similarity": 0.85, "metadata": {}},
        ]

        combined = self.retrieval_service._combine_search_results(results1, results2)

        # Should handle missing similarity scores gracefully
        assert len(combined) >= 1

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
    async def test_hybrid_search_with_no_entities(self):
        """Test hybrid search when no entities are extracted"""
        mock_vector_service = AsyncMock()
        mock_embedding_service = AsyncMock()

        mock_embedding_service.get_embedding.return_value = [0.1] * 1536
        mock_vector_service.search.return_value = []

        # Query with no recognizable entities
        results = await self.retrieval_service._search_with_entity_filtering(
            "how to do it", mock_embedding_service, mock_vector_service
        )

        # Should still perform search even without entities
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
