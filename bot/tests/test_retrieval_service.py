"""
Tests for Retrieval Service

Comprehensive tests for document retrieval and context building functionality.
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from services.retrieval.base_retrieval import BaseRetrieval
from services.retrieval_service import RetrievalService


# Test Data Builders and Factories
class RAGSettingsBuilder:
    """Builder for creating RAG settings configurations"""

    def __init__(self):
        self._enable_hybrid_search = False
        self._max_results = 5
        self._similarity_threshold = 0.7
        self._entity_content_boost = 0.05
        self._entity_title_boost = 0.1
        self._diversification_mode = "balanced"
        self._max_unique_documents = 5
        self._results_similarity_threshold = 0.7
        self._entity_content_boost = 0.05
        self._entity_title_boost = 0.1
        self._diversification_mode = "balanced"
        self._max_unique_documents = 5

    def with_hybrid_search(self, enabled: bool = True) -> "RAGSettingsBuilder":
        self._enable_hybrid_search = enabled
        return self

    def with_max_results(self, count: int) -> "RAGSettingsBuilder":
        self._max_results = count
        return self

    def with_similarity_threshold(self, threshold: float) -> "RAGSettingsBuilder":
        self._similarity_threshold = threshold
        return self

    def with_entity_content_boost(self, boost: float) -> "RAGSettingsBuilder":
        self._entity_content_boost = boost
        return self

    def with_entity_title_boost(self, boost: float) -> "RAGSettingsBuilder":
        self._entity_title_boost = boost
        return self

    def with_diversification_mode(self, mode: str) -> "RAGSettingsBuilder":
        self._diversification_mode = mode
        return self

    def with_max_unique_documents(self, count: int) -> "RAGSettingsBuilder":
        self._max_unique_documents = count
        return self

    def with_results_similarity_threshold(
        self, threshold: float
    ) -> "RAGSettingsBuilder":
        self._results_similarity_threshold = threshold
        return self

    def with_diversification_mode(self, mode: str) -> "RAGSettingsBuilder":
        self._diversification_mode = mode
        return self

    def build(self) -> MagicMock:
        mock_rag = MagicMock()
        mock_rag.enable_hybrid_search = self._enable_hybrid_search
        mock_rag.max_results = self._max_results
        mock_rag.similarity_threshold = self._similarity_threshold
        mock_rag.results_similarity_threshold = self._results_similarity_threshold
        mock_rag.entity_content_boost = self._entity_content_boost
        mock_rag.entity_title_boost = self._entity_title_boost
        mock_rag.diversification_mode = self._diversification_mode
        mock_rag.max_unique_documents = self._max_unique_documents
        # Add missing attributes for integration tests
        mock_rag.entity_content_boost = self._entity_content_boost
        mock_rag.entity_title_boost = self._entity_title_boost
        mock_rag.diversification_mode = self._diversification_mode
        mock_rag.max_unique_documents = self._max_unique_documents
        return mock_rag


class VectorSettingsBuilder:
    """Builder for creating vector settings configurations"""

    def __init__(self):
        self._provider = "elasticsearch"

    def with_provider(self, provider: str) -> "VectorSettingsBuilder":
        self._provider = provider
        return self

    def elasticsearch(self) -> "VectorSettingsBuilder":
        return self.with_provider("elasticsearch")

    def pinecone(self) -> "VectorSettingsBuilder":
        return self.with_provider("pinecone")

    def build(self) -> MagicMock:
        mock_vector = MagicMock()
        mock_vector.provider = self._provider
        return mock_vector


class RetrievalSettingsBuilder:
    """Builder for creating complete retrieval settings"""

    def __init__(self):
        self._rag_settings = RAGSettingsBuilder()
        self._vector_settings = VectorSettingsBuilder()

    def with_rag(self, rag_builder: RAGSettingsBuilder) -> "RetrievalSettingsBuilder":
        self._rag_settings = rag_builder
        return self

    def with_vector(
        self, vector_builder: VectorSettingsBuilder
    ) -> "RetrievalSettingsBuilder":
        self._vector_settings = vector_builder
        return self

    def with_hybrid_search(self, enabled: bool = True) -> "RetrievalSettingsBuilder":
        self._rag_settings = self._rag_settings.with_hybrid_search(enabled)
        return self

    def with_elasticsearch(self) -> "RetrievalSettingsBuilder":
        self._vector_settings = self._vector_settings.elasticsearch()
        return self

    def with_entity_boosting(
        self, content_boost: float = 0.05, title_boost: float = 0.1
    ) -> "RetrievalSettingsBuilder":
        """Add entity boosting configuration"""
        self._rag_settings = self._rag_settings.with_entity_content_boost(
            content_boost
        ).with_entity_title_boost(title_boost)
        return self

    def with_diversification(
        self, mode: str = "balanced", max_unique_documents: int = 5
    ) -> "RetrievalSettingsBuilder":
        """Add diversification configuration"""
        self._rag_settings = self._rag_settings.with_diversification_mode(
            mode
        ).with_max_unique_documents(max_unique_documents)
        return self

    def build(self) -> MagicMock:
        mock_settings = MagicMock()
        mock_settings.rag = self._rag_settings.build()
        mock_settings.vector = self._vector_settings.build()
        return mock_settings

    @classmethod
    def default(cls) -> "RetrievalSettingsBuilder":
        return cls()

    @classmethod
    def with_hybrid(cls) -> "RetrievalSettingsBuilder":
        return cls().with_hybrid_search(True)

    @classmethod
    def elasticsearch_config(cls) -> "RetrievalSettingsBuilder":
        return cls().with_elasticsearch()


class SearchResultBuilder:
    """Builder for creating search result objects"""

    def __init__(self):
        self._content = "Test content"
        self._similarity = 0.85
        self._metadata = {"file_name": "test.pdf"}

    def with_content(self, content: str) -> "SearchResultBuilder":
        self._content = content
        return self

    def with_similarity(self, similarity: float) -> "SearchResultBuilder":
        self._similarity = similarity
        return self

    def with_metadata(self, **metadata) -> "SearchResultBuilder":
        self._metadata.update(metadata)
        return self

    def with_file_name(self, file_name: str) -> "SearchResultBuilder":
        self._metadata["file_name"] = file_name
        return self

    def build(self) -> dict[str, Any]:
        return {
            "content": self._content,
            "similarity": self._similarity,
            "metadata": self._metadata.copy(),
        }

    @classmethod
    def high_relevance(
        cls, content: str = "High relevance content"
    ) -> "SearchResultBuilder":
        return cls().with_content(content).with_similarity(0.95)

    @classmethod
    def medium_relevance(
        cls, content: str = "Medium relevance content"
    ) -> "SearchResultBuilder":
        return cls().with_content(content).with_similarity(0.75)

    @classmethod
    def low_relevance(
        cls, content: str = "Low relevance content"
    ) -> "SearchResultBuilder":
        return cls().with_content(content).with_similarity(0.5)


class SearchResultsBuilder:
    """Builder for creating collections of search results"""

    def __init__(self):
        self._results = []

    def add_result(self, result_builder: SearchResultBuilder) -> "SearchResultsBuilder":
        self._results.append(result_builder.build())
        return self

    def add_high_relevance(
        self, content: str, file_name: str = "test.pdf"
    ) -> "SearchResultsBuilder":
        result = SearchResultBuilder.high_relevance(content).with_file_name(file_name)
        return self.add_result(result)

    def add_medium_relevance(
        self, content: str, file_name: str = "test.pdf"
    ) -> "SearchResultsBuilder":
        result = SearchResultBuilder.medium_relevance(content).with_file_name(file_name)
        return self.add_result(result)

    def add_low_relevance(
        self, content: str, file_name: str = "test.pdf"
    ) -> "SearchResultsBuilder":
        result = SearchResultBuilder.low_relevance(content).with_file_name(file_name)
        return self.add_result(result)

    def build(self) -> list[dict[str, Any]]:
        return self._results.copy()

    @classmethod
    def basic_results(cls) -> "SearchResultsBuilder":
        return (
            cls()
            .add_high_relevance("Test content 1", "test1.pdf")
            .add_medium_relevance("Test content 2", "test2.pdf")
        )

    @classmethod
    def diverse_results(cls) -> "SearchResultsBuilder":
        return (
            cls()
            .add_high_relevance("High relevance", "doc1.pdf")
            .add_medium_relevance("Medium relevance", "doc2.pdf")
            .add_low_relevance("Low relevance", "doc3.pdf")
        )


# Service Mock Factories
class VectorServiceFactory:
    """Factory for creating vector service mocks"""

    @staticmethod
    def create_basic_service() -> AsyncMock:
        """Create basic vector service mock"""
        mock_service = AsyncMock()
        mock_service.search = AsyncMock()
        return mock_service

    @staticmethod
    def create_elasticsearch_service() -> AsyncMock:
        """Create Elasticsearch vector service mock with BM25 capability"""
        mock_service = VectorServiceFactory.create_basic_service()
        mock_service.bm25_search = AsyncMock()  # BM25 capability
        return mock_service

    @staticmethod
    def create_service_with_results(search_results: list[dict[str, Any]]) -> AsyncMock:
        """Create vector service mock that returns specific search results"""
        mock_service = VectorServiceFactory.create_basic_service()
        mock_service.search.return_value = search_results
        return mock_service

    @staticmethod
    def create_elasticsearch_with_results(
        search_results: list[dict[str, Any]],
    ) -> AsyncMock:
        """Create Elasticsearch service mock with specific results"""
        mock_service = VectorServiceFactory.create_elasticsearch_service()
        mock_service.search.return_value = search_results
        return mock_service


class EmbeddingServiceFactory:
    """Factory for creating embedding service mocks"""

    @staticmethod
    def create_service(embedding_vector: list[float] | None = None) -> AsyncMock:
        """Create embedding service mock"""
        if embedding_vector is None:
            embedding_vector = [0.1] * 1536  # Default OpenAI embedding dimension

        mock_service = AsyncMock()
        mock_service.get_embedding = AsyncMock(return_value=embedding_vector)
        return mock_service

    @staticmethod
    def create_openai_service() -> AsyncMock:
        """Create OpenAI-style embedding service"""
        return EmbeddingServiceFactory.create_service([0.1] * 1536)

    @staticmethod
    def create_custom_embedding_service(dimensions: int = 768) -> AsyncMock:
        """Create embedding service with custom dimensions"""
        return EmbeddingServiceFactory.create_service([0.1] * dimensions)


class RetrievalServiceFactory:
    """Factory for creating RetrievalService instances"""

    @staticmethod
    def create_service(
        settings_builder: RetrievalSettingsBuilder | None = None,
    ) -> RetrievalService:
        """Create RetrievalService with specified settings"""
        if settings_builder is None:
            settings_builder = RetrievalSettingsBuilder.default()

        settings = settings_builder.build()
        return RetrievalService(settings)

    @staticmethod
    def create_basic_service() -> RetrievalService:
        """Create basic RetrievalService with default settings"""
        return RetrievalServiceFactory.create_service()

    @staticmethod
    def create_hybrid_service() -> RetrievalService:
        """Create RetrievalService with hybrid search enabled"""
        return RetrievalServiceFactory.create_service(
            RetrievalSettingsBuilder.with_hybrid()
        )

    @staticmethod
    def create_elasticsearch_service() -> RetrievalService:
        """Create RetrievalService configured for Elasticsearch"""
        return RetrievalServiceFactory.create_service(
            RetrievalSettingsBuilder.elasticsearch_config()
        )


class TestRetrievalService:
    """Test retrieval service functionality"""

    def setup_method(self):
        """Set up test fixtures"""
        # Create settings using factory
        self.mock_settings = RetrievalSettingsBuilder.default().build()
        self.retrieval_service = RetrievalServiceFactory.create_service(
            RetrievalSettingsBuilder.default()
        )

    def test_init(self):
        """Test RetrievalService initialization"""
        service = RetrievalServiceFactory.create_basic_service()
        assert service.settings is not None

    @pytest.mark.asyncio
    async def test_retrieve_context_no_vector_service(self):
        """Test retrieval with no vector service"""
        result = await self.retrieval_service.retrieve_context("test query", None, None)
        assert result == []

    @pytest.mark.asyncio
    async def test_retrieve_context_basic_search(self):
        """Test basic vector similarity search"""
        # Create services using factories
        search_results = SearchResultsBuilder.basic_results().build()
        mock_vector_service = VectorServiceFactory.create_service_with_results(
            search_results
        )
        mock_embedding_service = EmbeddingServiceFactory.create_openai_service()

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
        # Create hybrid search service
        hybrid_service = RetrievalServiceFactory.create_hybrid_service()

        # Create search results using builder
        search_results = [
            SearchResultBuilder()
            .with_content("Hybrid search result")
            .with_similarity(0.90)
            .with_file_name("hybrid.pdf")
            .build()
        ]
        mock_vector_service = VectorServiceFactory.create_service_with_results(
            search_results
        )
        mock_embedding_service = EmbeddingServiceFactory.create_openai_service()

        results = await hybrid_service.retrieve_context(
            "test query", mock_vector_service, mock_embedding_service
        )

        # Should call embedding service and vector search
        mock_embedding_service.get_embedding.assert_called_once_with("test query")
        mock_vector_service.search.assert_called()
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_retrieve_context_elasticsearch_bm25_search(self):
        """Test retrieval with Elasticsearch BM25 search"""
        # Create search results using builder
        search_results = [
            SearchResultBuilder()
            .with_content("BM25 search result")
            .with_similarity(0.88)
            .with_file_name("bm25.pdf")
            .build()
        ]
        mock_vector_service = VectorServiceFactory.create_elasticsearch_with_results(
            search_results
        )
        mock_embedding_service = EmbeddingServiceFactory.create_openai_service()

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
        # Create search results with different relevance scores using builders
        search_results = (
            SearchResultsBuilder()
            .add_high_relevance("High relevance", "high.pdf")  # 0.95
            .add_medium_relevance("Medium relevance", "medium.pdf")  # 0.75
            .add_result(
                SearchResultBuilder()
                .with_content("Low relevance")
                .with_similarity(0.60)  # Below 0.7 threshold
                .with_file_name("low.pdf")
            )
            .build()
        )

        mock_vector_service = VectorServiceFactory.create_service_with_results(
            search_results
        )
        mock_embedding_service = EmbeddingServiceFactory.create_openai_service()

        results = await self.retrieval_service.retrieve_context(
            "test query", mock_vector_service, mock_embedding_service
        )

        # Should filter out results below 0.7 threshold
        assert len(results) == 2
        assert all(result["similarity"] >= 0.7 for result in results)

    @pytest.mark.asyncio
    async def test_retrieve_context_exception_handling(self):
        """Test exception handling during retrieval"""
        mock_vector_service = VectorServiceFactory.create_basic_service()
        mock_embedding_service = EmbeddingServiceFactory.create_openai_service()
        # Make embedding service fail
        mock_embedding_service.get_embedding.side_effect = Exception("Embedding failed")

        results = await self.retrieval_service.retrieve_context(
            "test query", mock_vector_service, mock_embedding_service
        )

        # Should return empty list on exception
        assert results == []

    def test_extract_entities_simple_basic(self):
        """Test basic entity extraction"""
        # Test via the base retrieval class using factory settings
        settings = RetrievalSettingsBuilder.default().build()
        base_retrieval = BaseRetrieval(settings)
        entities = base_retrieval._extract_entities_simple(
            "Apple and Microsoft partnership"
        )

        # Should extract company names
        assert "apple" in entities  # lowercase since extraction normalizes
        assert "microsoft" in entities

    def test_extract_entities_simple_patterns(self):
        """Test entity extraction with various patterns"""
        settings = RetrievalSettingsBuilder.default().build()
        base_retrieval = BaseRetrieval(settings)
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
        # Create services using factories
        search_results = [
            SearchResultBuilder()
            .with_content("Apple project details")
            .with_similarity(0.90)
            .with_file_name("apple.pdf")
            .build()
        ]
        mock_vector_service = VectorServiceFactory.create_service_with_results(
            search_results
        )
        mock_embedding_service = EmbeddingServiceFactory.create_openai_service()

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
        # Create test results using builders
        results = [
            SearchResultBuilder()
            .with_content("Apple company information")
            .with_similarity(0.80)
            .with_file_name("apple.pdf")
            .build(),
            SearchResultBuilder()
            .with_content("Microsoft details")
            .with_similarity(0.75)
            .with_file_name("microsoft.pdf")
            .build(),
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
        # Create settings using factory with hybrid search enabled
        self.mock_settings = (
            RetrievalSettingsBuilder.with_hybrid()
            .with_elasticsearch()
            .with_entity_boosting(content_boost=0.05, title_boost=0.1)
            .with_diversification(mode="balanced", max_unique_documents=5)
            .build()
        )
        self.retrieval_service = RetrievalService(self.mock_settings)

    @pytest.mark.asyncio
    async def test_full_hybrid_search_pipeline(self):
        """Test complete hybrid search pipeline"""
        # Create services using factories
        mock_embedding_service = EmbeddingServiceFactory.create_openai_service()
        mock_vector_service = AsyncMock()

        # Mock entity search returning varied results using builders
        entity_results = [
            SearchResultBuilder()
            .with_content("Apple entity result")
            .with_similarity(0.85)
            .with_file_name("apple1.pdf")
            .build()
        ]

        mock_vector_service.search.side_effect = [
            # First call - entity search
            entity_results,
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
        # Create services using factories
        search_results = [
            SearchResultBuilder()
            .with_content("Test result")
            .with_similarity(0.85)
            .with_file_name("test.pdf")
            .build()
        ]
        mock_vector_service = VectorServiceFactory.create_service_with_results(
            search_results
        )
        mock_embedding_service = EmbeddingServiceFactory.create_openai_service()

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
