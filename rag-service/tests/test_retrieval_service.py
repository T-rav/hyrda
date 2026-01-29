"""
Comprehensive tests for retrieval service.

Tests entity extraction, boosting, and diversification logic.
"""

from unittest.mock import Mock

import pytest

from config.settings import Settings
from services.retrieval_service import STOP_WORDS, RetrievalService


class TestRetrievalServiceBasics:
    """Test basic retrieval service functionality."""

    def test_retrieval_service_can_be_imported(self):
        """Test that RetrievalService can be imported and instantiated."""
        settings = Settings()
        service = RetrievalService(settings)
        assert service is not None

    def test_retrieval_service_initialization(self):
        """Test RetrievalService initialization."""
        settings = Settings()
        service = RetrievalService(settings, enable_query_rewriting=False)

        assert service.settings == settings
        assert service.llm_service is None
        assert service.enable_query_rewriting is False
        assert service.query_rewriter is None

    def test_retrieval_service_with_llm_service(self):
        """Test initialization with LLM service."""
        settings = Settings()
        mock_llm = Mock()
        service = RetrievalService(settings, llm_service=mock_llm, enable_query_rewriting=True)

        assert service.llm_service == mock_llm
        assert service.enable_query_rewriting is True


class TestEntityExtraction:
    """Test entity extraction logic."""

    def test_extract_entities_simple_single_word(self):
        """Test extracting single significant word."""
        settings = Settings()
        service = RetrievalService(settings)

        entities = service._extract_entities_simple("Python")
        assert "python" in entities
        assert len(entities) == 1

    def test_extract_entities_simple_multiple_words(self):
        """Test extracting multiple significant words."""
        settings = Settings()
        service = RetrievalService(settings)

        entities = service._extract_entities_simple("Python programming language")
        assert "python" in entities
        assert "programming" in entities
        assert "language" in entities

    def test_extract_entities_simple_filters_stop_words(self):
        """Test that stop words are filtered out."""
        settings = Settings()
        service = RetrievalService(settings)

        entities = service._extract_entities_simple("What is the Python programming language?")
        assert "python" in entities
        assert "programming" in entities
        assert "language" in entities
        # Stop words should be filtered
        assert "what" not in entities
        assert "is" not in entities
        assert "the" not in entities

    def test_extract_entities_simple_min_length(self):
        """Test that words under 2 characters are filtered."""
        settings = Settings()
        service = RetrievalService(settings)

        entities = service._extract_entities_simple("I like Go programming")
        assert "go" in entities  # 2 chars, should be included
        assert "like" in entities
        assert "programming" in entities
        # Single character should be filtered
        assert "i" not in entities

    def test_extract_entities_simple_alphanumeric_only(self):
        """Test that only alphanumeric words are extracted."""
        settings = Settings()
        service = RetrievalService(settings)

        entities = service._extract_entities_simple("Python 3.11 programming (advanced)")
        assert "python" in entities
        assert "programming" in entities
        assert "advanced" in entities
        # Should not extract punctuation
        assert "." not in entities
        assert "(" not in entities

    def test_extract_entities_simple_case_insensitive(self):
        """Test that extraction is case-insensitive."""
        settings = Settings()
        service = RetrievalService(settings)

        entities = service._extract_entities_simple("Python PYTHON python")
        assert "python" in entities
        assert len(entities) == 1  # Should deduplicate

    def test_extract_entities_simple_with_numbers(self):
        """Test extracting entities with numbers."""
        settings = Settings()
        service = RetrievalService(settings)

        entities = service._extract_entities_simple("Python3 v3 2024 data")
        assert "python3" in entities
        assert "v3" in entities
        assert "2024" in entities
        assert "data" in entities


class TestStopWords:
    """Test stop words configuration."""

    def test_stop_words_contains_articles(self):
        """Test that STOP_WORDS includes common articles."""
        assert "a" in STOP_WORDS
        assert "an" in STOP_WORDS
        assert "the" in STOP_WORDS

    def test_stop_words_contains_prepositions(self):
        """Test that STOP_WORDS includes common prepositions."""
        assert "in" in STOP_WORDS
        assert "on" in STOP_WORDS
        assert "at" in STOP_WORDS
        assert "to" in STOP_WORDS
        assert "for" in STOP_WORDS

    def test_stop_words_contains_question_words(self):
        """Test that STOP_WORDS includes question words."""
        assert "what" in STOP_WORDS
        assert "when" in STOP_WORDS
        assert "where" in STOP_WORDS
        assert "how" in STOP_WORDS
        assert "why" in STOP_WORDS


class TestEntityBoosting:
    """Test entity boosting logic."""

    def test_apply_entity_boosting_no_entities(self):
        """Test boosting with no entities extracted."""
        settings = Settings()
        service = RetrievalService(settings)

        results = [
            {
                "content": "Test content",
                "similarity": 0.5,
                "metadata": {"file_name": "doc.pdf"},
            }
        ]

        boosted = service._apply_entity_boosting("what is this", results)
        # No entities after filtering stop words, so no boost
        assert boosted[0]["similarity"] == 0.5

    def test_apply_entity_boosting_content_match(self):
        """Test boosting when entity matches content."""
        settings = Settings()
        settings.rag.entity_content_boost = 0.1
        service = RetrievalService(settings)

        results = [
            {
                "content": "Python programming is great",
                "similarity": 0.5,
                "metadata": {"file_name": "doc.pdf"},
            }
        ]

        boosted = service._apply_entity_boosting("Python programming", results)
        # Should have 0.1 boost for each entity (python, programming)
        assert boosted[0]["similarity"] > 0.5
        assert boosted[0]["_entity_boost"] > 0
        assert boosted[0]["_matching_entities"] == 2

    def test_apply_entity_boosting_title_match(self):
        """Test boosting when entity matches title."""
        settings = Settings()
        settings.rag.entity_title_boost = 0.15
        service = RetrievalService(settings)

        results = [
            {
                "content": "Some content",
                "similarity": 0.5,
                "metadata": {"file_name": "python_guide.pdf"},
            }
        ]

        boosted = service._apply_entity_boosting("Python guide", results)
        # Should boost for both python and guide in title
        assert boosted[0]["similarity"] > 0.5
        assert boosted[0]["_entity_boost"] > 0

    def test_apply_entity_boosting_caps_at_1_0(self):
        """Test that boosting caps similarity at 1.0."""
        settings = Settings()
        settings.rag.entity_content_boost = 0.5
        service = RetrievalService(settings)

        results = [
            {
                "content": "Python Python Python",
                "similarity": 0.9,
                "metadata": {"file_name": "python.pdf"},
            }
        ]

        boosted = service._apply_entity_boosting("Python", results)
        # Should cap at 1.0 even with large boost
        assert boosted[0]["similarity"] == 1.0

    def test_apply_entity_boosting_preserves_original(self):
        """Test that original similarity is preserved in metadata."""
        settings = Settings()
        settings.rag.entity_content_boost = 0.1
        service = RetrievalService(settings)

        results = [
            {
                "content": "Python content",
                "similarity": 0.5,
                "metadata": {"file_name": "doc.pdf"},
            }
        ]

        boosted = service._apply_entity_boosting("Python", results)
        assert boosted[0]["_original_similarity"] == 0.5
        assert boosted[0]["similarity"] > 0.5

    def test_apply_entity_boosting_sorts_by_boosted_score(self):
        """Test that results are sorted by boosted similarity."""
        settings = Settings()
        settings.rag.entity_content_boost = 0.3
        service = RetrievalService(settings)

        results = [
            {
                "content": "Generic content",
                "similarity": 0.7,
                "metadata": {"file_name": "generic.pdf"},
            },
            {
                "content": "Python programming",
                "similarity": 0.5,
                "metadata": {"file_name": "python.pdf"},
            },
        ]

        boosted = service._apply_entity_boosting("Python programming", results)
        # Second result should now be first due to boost (0.5 + 0.3*2 = 1.1→1.0 > 0.7)
        assert boosted[0]["metadata"]["file_name"] == "python.pdf"


class TestDiversificationStrategy:
    """Test result diversification logic."""

    def test_smart_similarity_diversify_empty(self):
        """Test diversification with empty results."""
        settings = Settings()
        service = RetrievalService(settings)

        diversified = service._smart_similarity_diversify([], max_results=5)
        assert len(diversified) == 0

    def test_smart_similarity_diversify_under_limit(self):
        """Test diversification when results under max limit."""
        settings = Settings()
        settings.rag.max_chunks_per_document = 3
        service = RetrievalService(settings)

        results = [
            {
                "content": "Chunk 1",
                "similarity": 0.9,
                "metadata": {"file_name": "doc.pdf"},
            },
            {
                "content": "Chunk 2",
                "similarity": 0.8,
                "metadata": {"file_name": "doc.pdf"},
            },
        ]

        diversified = service._smart_similarity_diversify(results, max_results=5)
        assert len(diversified) == 2

    def test_smart_similarity_diversify_limits_per_document(self):
        """Test that chunks are limited per document."""
        settings = Settings()
        settings.rag.max_chunks_per_document = 2
        service = RetrievalService(settings)

        results = [
            {
                "content": f"Chunk {i}",
                "similarity": 0.9 - i * 0.01,
                "metadata": {"file_name": "doc.pdf"},
            }
            for i in range(5)
        ]

        diversified = service._smart_similarity_diversify(results, max_results=10)
        # Should only have 2 chunks from doc.pdf
        assert len(diversified) == 2

    def test_smart_similarity_diversify_multiple_documents(self):
        """Test diversification across multiple documents."""
        settings = Settings()
        settings.rag.max_chunks_per_document = 2
        service = RetrievalService(settings)

        results = [
            {
                "content": "Doc1 Chunk1",
                "similarity": 0.9,
                "metadata": {"file_name": "doc1.pdf"},
            },
            {
                "content": "Doc2 Chunk1",
                "similarity": 0.85,
                "metadata": {"file_name": "doc2.pdf"},
            },
            {
                "content": "Doc1 Chunk2",
                "similarity": 0.8,
                "metadata": {"file_name": "doc1.pdf"},
            },
            {
                "content": "Doc1 Chunk3",
                "similarity": 0.75,
                "metadata": {"file_name": "doc1.pdf"},
            },
        ]

        diversified = service._smart_similarity_diversify(results, max_results=10)
        # Should have 2 from doc1, 1 from doc2 = 3 total
        assert len(diversified) == 3

    def test_smart_similarity_diversify_metric_data_no_limit(self):
        """Test that metric data (no file_name) has no per-document limit."""
        settings = Settings()
        settings.rag.max_chunks_per_document = 2
        service = RetrievalService(settings)

        results = [
            {"content": f"Metric {i}", "similarity": 0.9 - i * 0.01, "metadata": {}}
            for i in range(5)
        ]

        diversified = service._smart_similarity_diversify(results, max_results=10)
        # All metrics should be included (no file_name = no limit)
        assert len(diversified) == 5

    def test_smart_similarity_diversify_respects_max_results(self):
        """Test that max_results limit is respected."""
        settings = Settings()
        settings.rag.max_chunks_per_document = 10  # High limit
        service = RetrievalService(settings)

        results = [
            {
                "content": f"Chunk {i}",
                "similarity": 0.9 - i * 0.01,
                "metadata": {"file_name": f"doc{i}.pdf"},
            }
            for i in range(10)
        ]

        diversified = service._smart_similarity_diversify(results, max_results=5)
        assert len(diversified) == 5


class TestApplyDiversificationStrategy:
    """Test the main diversification strategy method."""

    def test_apply_diversification_strategy_empty(self):
        """Test applying diversification to empty results."""
        settings = Settings()
        service = RetrievalService(settings)

        diversified = service._apply_diversification_strategy([])
        assert len(diversified) == 0

    def test_apply_diversification_strategy_uses_settings(self):
        """Test that diversification uses max_results from settings."""
        settings = Settings()
        settings.rag.max_results = 3
        settings.rag.max_chunks_per_document = 10
        service = RetrievalService(settings)

        results = [
            {
                "content": f"Chunk {i}",
                "similarity": 0.9 - i * 0.01,
                "metadata": {"file_name": f"doc{i}.pdf"},
            }
            for i in range(10)
        ]

        diversified = service._apply_diversification_strategy(results)
        assert len(diversified) <= settings.rag.max_results


class TestRetrieveContextNoVectorService:
    """Test context retrieval without vector service."""

    @pytest.mark.asyncio
    async def test_retrieve_context_no_vector_service(self):
        """Test that empty context returned when no vector service."""
        settings = Settings()
        service = RetrievalService(settings)

        mock_embedding_service = Mock()
        result = await service.retrieve_context(
            query="test", vector_service=None, embedding_service=mock_embedding_service
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_retrieve_context_by_embedding_returns_empty_on_error(self):
        """Test that empty context returned on error."""
        settings = Settings()
        service = RetrievalService(settings)

        mock_vector_service = Mock()
        mock_vector_service.search.side_effect = Exception("Search failed")

        result = await service.retrieve_context_by_embedding(
            document_embedding=[0.1, 0.2, 0.3], vector_service=mock_vector_service
        )

        assert result == []
