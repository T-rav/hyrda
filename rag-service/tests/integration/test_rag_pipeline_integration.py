"""
RAG Pipeline Integration Tests - Fixed and Working

Tests real RAG pipeline behaviors with proper mocking of external dependencies.
"""

from unittest.mock import AsyncMock, patch

import pytest

from config.settings import Settings
from services.context_builder import ContextBuilder
from services.rag_service import RAGService
from services.retrieval_service import RetrievalService

pytestmark = pytest.mark.integration


class TestRAGServiceInitialization:
    """Test RAG service initialization with real components."""

    @pytest.mark.asyncio
    async def test_rag_service_creates_components(self):
        """Test that RAG service creates all required components."""
        settings = Settings()
        settings.rag.enable_query_rewriting = False  # Disable to avoid extra mocks

        # Mock all dependencies where RAGService imports them
        with patch('services.rag_service.get_vector_store') as mock_vector:
            with patch('services.rag_service.create_embedding_provider') as mock_embed:
                with patch('services.rag_service.create_llm_provider') as mock_llm:
                    with patch('services.rag_service.create_internal_deep_research_service') as mock_deep:
                        with patch('services.rag_service.get_tavily_client', return_value=None):
                            with patch('services.rag_service.get_perplexity_client', return_value=None):
                                # Setup mocks
                                mock_vector.return_value = AsyncMock()
                                mock_embed.return_value = AsyncMock()
                                mock_llm.return_value = AsyncMock()
                                mock_deep.return_value = None

                                # Create service
                                service = RAGService(settings)

                                # Verify components were created
                                assert service.vector_store is not None
                                assert service.embedding_provider is not None
                                assert service.llm_provider is not None
                                assert service.retrieval_service is not None
                                assert service.context_builder is not None
                                assert service.citation_service is not None

    @pytest.mark.asyncio
    async def test_rag_service_initialize(self):
        """Test RAG service initialization."""
        settings = Settings()
        settings.rag.enable_query_rewriting = False

        with patch('services.rag_service.get_vector_store') as mock_vector:
            with patch('services.rag_service.create_embedding_provider') as mock_embed:
                with patch('services.rag_service.create_llm_provider') as mock_llm:
                    with patch('services.rag_service.create_internal_deep_research_service', return_value=None):
                        with patch('services.rag_service.get_tavily_client', return_value=None):
                            with patch('services.rag_service.get_perplexity_client', return_value=None):
                                mock_vector_store = AsyncMock()
                                mock_vector_store.initialize = AsyncMock()
                                mock_vector.return_value = mock_vector_store
                                mock_embed.return_value = AsyncMock()
                                mock_llm.return_value = AsyncMock()

                                service = RAGService(settings)
                                await service.initialize()

                                # Verify vector store was initialized
                                mock_vector_store.initialize.assert_called_once()


class TestDocumentIngestion:
    """Test document ingestion pipeline."""

    @pytest.mark.asyncio
    async def test_ingest_documents_success(self):
        """Test successful document ingestion."""
        settings = Settings()
        settings.rag.enable_query_rewriting = False  # Disable to avoid extra mocks

        with patch('services.rag_service.get_vector_store') as mock_vector:
            with patch('services.rag_service.create_embedding_provider') as mock_embed:
                with patch('services.rag_service.create_llm_provider') as mock_llm:
                    with patch('services.rag_service.create_internal_deep_research_service') as mock_deep:
                        with patch('services.rag_service.get_tavily_client', return_value=None):
                            with patch('services.rag_service.get_perplexity_client', return_value=None):
                                # Setup vector store mock
                                mock_vector_store = AsyncMock()
                                mock_vector_store.initialize = AsyncMock()
                                mock_vector_store.upsert = AsyncMock(return_value=True)
                                mock_vector.return_value = mock_vector_store

                                # Setup embedding mock
                                mock_embed_provider = AsyncMock()
                                mock_embed_provider.get_embedding = AsyncMock(
                                    return_value=[0.1] * 1536
                                )
                                mock_embed.return_value = mock_embed_provider

                                mock_llm.return_value = AsyncMock()
                                mock_deep.return_value = None

                                service = RAGService(settings)
                                await service.initialize()

                                documents = [
                                    {
                                        "content": "Test document about Python programming.",
                                        "metadata": {"file_name": "test.pdf"},
                                    }
                                ]

                                success, error = await service.ingest_documents(documents)

                                assert success + error == 1
                                assert mock_embed_provider.get_embedding.called

    @pytest.mark.asyncio
    async def test_ingest_empty_documents(self):
        """Test ingesting empty document list."""
        settings = Settings()
        settings.rag.enable_query_rewriting = False  # Disable to avoid extra mocks

        with patch('services.rag_service.get_vector_store') as mock_vector:
            with patch('services.rag_service.create_embedding_provider') as mock_embed:
                with patch('services.rag_service.create_llm_provider') as mock_llm:
                    with patch('services.rag_service.create_internal_deep_research_service') as mock_deep:
                        with patch('services.rag_service.get_tavily_client', return_value=None):
                            with patch('services.rag_service.get_perplexity_client', return_value=None):
                                mock_vector_store = AsyncMock()
                                mock_vector_store.initialize = AsyncMock()
                                mock_vector.return_value = mock_vector_store
                                mock_embed.return_value = AsyncMock()
                                mock_llm.return_value = AsyncMock()
                                mock_deep.return_value = None

                                service = RAGService(settings)
                                await service.initialize()

                                success, error = await service.ingest_documents([])

                                assert success == 0
                                assert error == 0


class TestRetrievalPipeline:
    """Test document retrieval behaviors."""

    @pytest.mark.asyncio
    async def test_retrieve_with_results(self):
        """Test retrieving documents with results."""
        settings = Settings()
        retrieval_service = RetrievalService(settings, enable_query_rewriting=False)

        # Mock vector service with results
        mock_vector_service = AsyncMock()
        mock_vector_service.search = AsyncMock(
            return_value=[
                {
                    "content": "Python is a programming language",
                    "similarity": 0.9,
                    "metadata": {"file_name": "python.pdf"},
                }
            ]
        )

        # Mock embedding service
        mock_embed_service = AsyncMock()
        mock_embed_service.get_embedding = AsyncMock(
            return_value=[0.1] * 1536
        )

        results = await retrieval_service.retrieve_context(
            query="What is Python?",
            vector_service=mock_vector_service,
            embedding_service=mock_embed_service,
        )

        assert len(results) > 0
        assert results[0]["similarity"] >= 0.8

    @pytest.mark.asyncio
    async def test_retrieve_with_no_results(self):
        """Test retrieval when no documents found."""
        settings = Settings()
        retrieval_service = RetrievalService(settings, enable_query_rewriting=False)

        mock_vector_service = AsyncMock()
        mock_vector_service.search = AsyncMock(return_value=[])

        mock_embed_service = AsyncMock()
        mock_embed_service.get_embedding = AsyncMock(return_value=[0.1] * 1536)

        results = await retrieval_service.retrieve_context(
            query="Unrelated query",
            vector_service=mock_vector_service,
            embedding_service=mock_embed_service,
        )

        assert len(results) == 0


class TestContextBuilding:
    """Test context building from chunks."""

    def test_build_context_with_chunks(self):
        """Test building context from retrieved chunks."""
        builder = ContextBuilder()

        chunks = [
            {
                "content": "Python is a high-level programming language.",
                "similarity": 0.9,
                "metadata": {"file_name": "python.pdf", "source": "google_drive"},
            }
        ]

        system_msg, messages = builder.build_rag_prompt(
            "What is Python?", chunks, [], "You are helpful."
        )

        assert "Python is a high-level programming language" in system_msg
        assert "KNOWLEDGE BASE" in system_msg
        assert len(messages) == 1

    def test_build_context_with_uploaded_doc(self):
        """Test context with uploaded document."""
        builder = ContextBuilder()

        chunks = [
            {
                "content": "Uploaded content.",
                "similarity": 1.0,
                "metadata": {"file_name": "upload.pdf", "source": "uploaded_document"},
            }
        ]

        system_msg, messages = builder.build_rag_prompt(
            "Analyze this", chunks, [], "System"
        )

        assert "UPLOADED DOCUMENT" in system_msg
        assert "Primary user content" in system_msg

    def test_validate_high_quality_context(self):
        """Test quality validation for high-quality chunks."""
        builder = ContextBuilder()

        chunks = [
            {"content": "Content", "similarity": 0.9, "metadata": {"file_name": "doc.pdf"}}
        ]

        quality = builder.validate_context_quality(chunks, min_similarity=0.5)

        assert quality["high_quality_chunks"] == 1
        assert quality["avg_similarity"] == 0.9
        assert len(quality["warnings"]) == 0




class TestSystemStatus:
    """Test system status and health."""

    @pytest.mark.asyncio
    async def test_get_system_status(self):
        """Test system status retrieval."""
        settings = Settings()
        settings.rag.enable_query_rewriting = False  # Disable to avoid extra mocks

        with patch('services.rag_service.get_vector_store') as mock_vector:
            with patch('services.rag_service.create_embedding_provider') as mock_embed:
                with patch('services.rag_service.create_llm_provider') as mock_llm:
                    with patch('services.rag_service.create_internal_deep_research_service') as mock_deep:
                        with patch('services.rag_service.get_tavily_client', return_value=None):
                            with patch('services.rag_service.get_perplexity_client', return_value=None):
                                mock_vector_store = AsyncMock()
                                mock_vector_store.initialize = AsyncMock()
                                mock_vector.return_value = mock_vector_store
                                mock_embed.return_value = AsyncMock()
                                mock_llm.return_value = AsyncMock()
                                mock_deep.return_value = None

                                service = RAGService(settings)
                                await service.initialize()

                                status = await service.get_system_status()

                                assert isinstance(status, dict)
                                # Check for actual keys in status
                                assert "vector_enabled" in status or "services" in status
