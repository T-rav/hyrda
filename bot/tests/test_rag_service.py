"""
Tests for RAG Service functionality.

Tests basic RAG service operations and integration.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from pydantic import SecretStr

from bot.services.rag_service import RAGService
from config.settings import EmbeddingSettings, LLMSettings, Settings, VectorSettings


class TestRAGService:
    """Test cases for RAGService"""

    @pytest.fixture
    def settings(self):
        """Create settings for testing"""
        return Settings(
            vector=VectorSettings(
                provider="pinecone",
                api_key=SecretStr("test-key"),
                collection_name="test-collection"
            ),
            embedding=EmbeddingSettings(
                provider="openai",
                model="text-embedding-ada-002",
                api_key=SecretStr("embedding-key")
            ),
            llm=LLMSettings(
                provider="openai",
                api_key=SecretStr("llm-key"),
                model="gpt-4"
            )
        )

    @pytest.fixture
    def rag_service(self, settings):
        """Create RAG service for testing"""
        with patch('bot.services.rag_service.create_vector_store'), \
             patch('bot.services.rag_service.create_embedding_provider'), \
             patch('bot.services.rag_service.create_llm_provider'):
            return RAGService(settings)

    def test_init(self, rag_service, settings):
        """Test service initialization"""
        assert rag_service.settings == settings
        assert rag_service._initialized is False

    @pytest.mark.asyncio
    async def test_initialization_success(self, rag_service):
        """Test successful initialization"""
        # Mock dependencies
        rag_service.vector_store = AsyncMock()
        rag_service.embedding_service = Mock()
        rag_service.llm_provider = Mock()

        await rag_service.initialize()

        assert rag_service._initialized is True
        rag_service.vector_store.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialization_failure(self, rag_service):
        """Test initialization failure"""
        rag_service.vector_store = AsyncMock()
        rag_service.vector_store.initialize.side_effect = Exception("Init failed")

        with pytest.raises(Exception, match="Init failed"):
            await rag_service.initialize()

        assert rag_service._initialized is False

    @pytest.mark.asyncio
    async def test_operations_require_initialization(self, rag_service):
        """Test that operations require initialization"""
        with pytest.raises(RuntimeError, match="not initialized"):
            await rag_service.add_documents(["text"], [[0.1]], [{}])

        with pytest.raises(RuntimeError, match="not initialized"):
            await rag_service.search("query", [0.1])

        with pytest.raises(RuntimeError, match="not initialized"):
            await rag_service.generate_response("query", [])

    @pytest.mark.asyncio
    async def test_add_documents_success(self, rag_service):
        """Test successful document addition"""
        rag_service._initialized = True
        rag_service.vector_store = AsyncMock()
        rag_service.vector_store.add_documents.return_value = True

        result = await rag_service.add_documents(
            ["document text"],
            [[0.1, 0.2, 0.3]],
            [{"file_name": "test.pdf"}]
        )

        assert result is True
        rag_service.vector_store.add_documents.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_success(self, rag_service):
        """Test successful search"""
        rag_service._initialized = True
        rag_service.vector_store = AsyncMock()
        expected_results = [{"content": "result", "similarity": 0.8}]
        rag_service.vector_store.search.return_value = expected_results

        results = await rag_service.search("query", [0.1, 0.2], top_k=5)

        assert results == expected_results
        rag_service.vector_store.search.assert_called_once_with(
            query_embedding=[0.1, 0.2],
            limit=5,
            similarity_threshold=0.0
        )

    @pytest.mark.asyncio
    async def test_generate_response_success(self, rag_service):
        """Test successful response generation"""
        rag_service._initialized = True
        rag_service.embedding_service = AsyncMock()
        rag_service.vector_store = AsyncMock()
        rag_service.llm_provider = AsyncMock()
        rag_service.context_builder = Mock()

        # Mock dependencies
        rag_service.embedding_service.get_embedding.return_value = [0.1, 0.2]
        rag_service.vector_store.search.return_value = [{"content": "context", "similarity": 0.8}]
        rag_service.context_builder.build_rag_prompt.return_value = ("system", [{"role": "user", "content": "query"}])
        rag_service.llm_provider.get_response.return_value = "LLM response"

        response = await rag_service.generate_response("query", [])

        assert "LLM response" in response
        rag_service.embedding_service.get_embedding.assert_called_once_with("query")
        rag_service.vector_store.search.assert_called_once()
        rag_service.llm_provider.get_response.assert_called_once()

    @pytest.mark.asyncio
    async def test_close(self, rag_service):
        """Test resource cleanup"""
        rag_service.vector_store = AsyncMock()
        rag_service.embedding_service = AsyncMock()
        rag_service.llm_provider = AsyncMock()

        await rag_service.close()

        rag_service.vector_store.close.assert_called_once()
        rag_service.embedding_service.close.assert_called_once()
        rag_service.llm_provider.close.assert_called_once()
