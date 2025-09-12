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
        # The RAG service initialize method only calls vector_store.initialize() if vector_store exists
        rag_service.vector_store.initialize = AsyncMock()

        await rag_service.initialize()

        # The actual initialize method calls vector_store.initialize(), not retrieval_service
        rag_service.vector_store.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialization_failure(self, rag_service):
        """Test initialization failure"""
        rag_service.vector_store.initialize = AsyncMock(
            side_effect=Exception("Init failed")
        )

        with pytest.raises(Exception, match="Init failed"):
            await rag_service.initialize()

    @pytest.mark.asyncio
    async def test_ingest_documents_success(self, rag_service):
        """Test successful document ingestion"""
        # Set up the document processor and embedding provider mocks
        rag_service.document_processor.process_generic_document = Mock(
            return_value=[
                {"content": "processed chunk", "metadata": {"file_name": "test.pdf"}}
            ]
        )
        rag_service.embedding_provider.get_embedding = AsyncMock(
            return_value=[0.1, 0.2, 0.3]
        )
        rag_service.vector_store.add_documents = AsyncMock()

        documents = [
            {"content": "test document", "metadata": {"file_name": "test.pdf"}}
        ]

        result = await rag_service.ingest_documents(documents)

        assert result == (1, 0)  # (success_count, error_count)
        rag_service.vector_store.add_documents.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_response_success(self, rag_service):
        """Test successful response generation"""
        # Set up all the method mocks explicitly
        rag_service.retrieval_service.retrieve_context = AsyncMock(
            return_value=[
                {
                    "content": "context",
                    "similarity": 0.8,
                    "metadata": {"file_name": "test.pdf"},
                }
            ]
        )
        rag_service.context_builder.build_rag_prompt = Mock(
            return_value=(
                "system",
                [{"role": "user", "content": "query"}],
            )
        )
        rag_service.llm_provider.get_response = AsyncMock(return_value="LLM response")
        rag_service.citation_service.add_source_citations = Mock(
            return_value=("Final response with citations")
        )

        response = await rag_service.generate_response("query", [])

        assert "Final response with citations" in response
        # The actual method signature includes vector_store and embedding_provider
        rag_service.retrieval_service.retrieve_context.assert_called_once_with(
            "query", rag_service.vector_store, rag_service.embedding_provider
        )

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
