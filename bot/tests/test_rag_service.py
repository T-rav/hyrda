"""
Tests for RAG Service functionality.

Tests RAG service orchestration and integration.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from pydantic import SecretStr

from bot.services.rag_service import RAGService
from config.settings import EmbeddingSettings, LLMSettings, Settings, VectorSettings


class TestRAGService:
    """Test cases for RAG service"""

    @pytest.fixture
    def settings(self):
        """Create settings for testing"""
        return Settings(
            embedding=EmbeddingSettings(
                provider="openai",
                model="text-embedding-ada-002",
                api_key=SecretStr("test-key"),
            ),
            llm=LLMSettings(
                provider="openai",
                model="gpt-4",
                api_key=SecretStr("test-key"),
            ),
            vector=VectorSettings(
                provider="pinecone",
                api_key=SecretStr("test-key"),
                collection_name="test",
            ),
        )

    @pytest.fixture
    def rag_service(self, settings):
        """Create RAG service for testing"""
        with (
            patch("bot.services.rag_service.create_vector_store") as mock_vector_store,
            patch(
                "bot.services.rag_service.create_embedding_provider"
            ) as mock_embedding,
            patch("bot.services.rag_service.create_llm_provider") as mock_llm,
        ):
            mock_vector_store.return_value = AsyncMock()
            mock_embedding.return_value = AsyncMock()
            mock_llm.return_value = AsyncMock()
            return RAGService(settings)

    def test_init(self, rag_service, settings):
        """Test service initialization"""
        assert rag_service.settings == settings
        assert hasattr(rag_service, "retrieval_service")
        assert hasattr(rag_service, "citation_service")
        assert hasattr(rag_service, "context_builder")

    @pytest.mark.asyncio
    async def test_initialization_success(self, rag_service):
        """Test successful initialization"""
        # Mock dependencies
        rag_service.retrieval_service = AsyncMock()
        rag_service.embedding_service = Mock()
        rag_service.llm_provider = Mock()

        await rag_service.initialize()

        rag_service.retrieval_service.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialization_failure(self, rag_service):
        """Test initialization failure"""
        rag_service.retrieval_service = AsyncMock()
        rag_service.retrieval_service.initialize.side_effect = Exception("Init failed")

        with pytest.raises(Exception, match="Init failed"):
            await rag_service.initialize()

    @pytest.mark.asyncio
    async def test_ingest_documents_success(self, rag_service):
        """Test successful document ingestion"""
        rag_service.document_processor = AsyncMock()
        rag_service.retrieval_service = AsyncMock()
        rag_service.retrieval_service.add_documents.return_value = True

        documents = ["test document"]
        metadatas = [{"file_name": "test.pdf"}]

        result = await rag_service.ingest_documents(documents, metadatas)

        assert result is True
        rag_service.document_processor.process_documents.assert_called_once_with(
            documents, metadatas
        )

    @pytest.mark.asyncio
    async def test_generate_response_success(self, rag_service):
        """Test successful response generation"""
        rag_service.embedding_service = AsyncMock()
        rag_service.retrieval_service = AsyncMock()
        rag_service.llm_provider = AsyncMock()
        rag_service.context_builder = Mock()
        rag_service.citation_service = Mock()

        # Mock dependencies
        rag_service.embedding_service.get_embedding.return_value = [0.1, 0.2]
        rag_service.retrieval_service.search.return_value = [
            {
                "content": "context",
                "similarity": 0.8,
                "metadata": {"file_name": "test.pdf"},
            }
        ]
        rag_service.context_builder.build_rag_prompt.return_value = (
            "system",
            [{"role": "user", "content": "query"}],
        )
        rag_service.llm_provider.get_response.return_value = "LLM response"
        rag_service.citation_service.add_source_citations.return_value = (
            "Final response with citations"
        )

        response = await rag_service.generate_response("query", [])

        assert "Final response with citations" in response
        rag_service.embedding_service.get_embedding.assert_called_once_with("query")

    @pytest.mark.asyncio
    async def test_get_system_status(self, rag_service):
        """Test getting system status"""
        rag_service.retrieval_service = Mock()
        rag_service.retrieval_service.get_status.return_value = {"status": "ready"}

        status = await rag_service.get_system_status()

        assert isinstance(status, dict)
        assert "services" in status
        assert "vector_enabled" in status

    @pytest.mark.asyncio
    async def test_close(self, rag_service):
        """Test closing the service"""
        # The vector_store should be AsyncMock from fixture
        await rag_service.close()

        # Only vector_store.close() is called in the actual implementation
        rag_service.vector_store.close.assert_called_once()
