import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add the parent directory to sys.path to allow importing the module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.llm_service import LLMService


@pytest.fixture
def mock_settings():
    """Create mock settings for testing"""
    settings = MagicMock()

    # LLM settings
    settings.llm = MagicMock()
    settings.llm.provider = "openai"
    settings.llm.api_key = MagicMock()
    settings.llm.api_key.get_secret_value.return_value = "test-api-key"
    settings.llm.model = "gpt-4o-mini"
    settings.llm.temperature = 0.7
    settings.llm.max_tokens = 2000
    settings.llm.base_url = None

    # Vector settings (disabled for most tests)
    settings.vector = MagicMock()
    settings.vector.enabled = False
    settings.vector.provider = "chroma"
    settings.vector.url = "./test_chroma"
    settings.vector.collection_name = "test_collection"

    # Embedding settings
    settings.embedding = MagicMock()
    settings.embedding.provider = "openai"
    settings.embedding.model = "text-embedding-3-small"
    settings.embedding.api_key = None
    settings.embedding.chunk_size = 1000
    settings.embedding.chunk_overlap = 200

    # RAG settings
    settings.rag = MagicMock()
    settings.rag.max_chunks = 5
    settings.rag.similarity_threshold = 0.7
    settings.rag.rerank_enabled = False
    settings.rag.include_metadata = True

    # Hybrid settings - ensure it's disabled for tests
    settings.hybrid = MagicMock()
    settings.hybrid.enabled = False

    return settings


@pytest.fixture
def llm_service(mock_settings):
    """Create LLM service for testing"""
    with patch("services.llm_service.RAGService"):
        service = LLMService(mock_settings)
        return service


class TestLLMService:
    """Tests for RAG-enabled LLM service"""

    def test_init(self, llm_service):
        """Test LLM service initialization"""
        assert llm_service.model == "gpt-4o-mini"
        assert llm_service.settings is not None
        assert llm_service.rag_service is not None

    @pytest.mark.asyncio
    async def test_initialize(self, llm_service):
        """Test LLM service initialization"""
        llm_service.rag_service.initialize = AsyncMock()

        await llm_service.initialize()

        llm_service.rag_service.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_response_success(self, llm_service):
        """Test successful response generation"""
        messages = [{"role": "user", "content": "Hello"}]
        user_id = "U12345"

        # Mock RAG service response
        llm_service.rag_service.generate_response = AsyncMock(
            return_value="Hello! How can I help you?"
        )

        result = await llm_service.get_response(messages, user_id)

        assert result == "Hello! How can I help you?"
        llm_service.rag_service.generate_response.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_response_with_user_prompt(self, llm_service):
        """Test response generation with custom user prompt"""
        messages = [{"role": "user", "content": "What is Python?"}]
        user_id = "U12345"

        # Mock user prompt service
        # Test basic functionality

        # Mock RAG service response
        llm_service.rag_service.generate_response = AsyncMock(
            return_value="Python is a programming language..."
        )

        result = await llm_service.get_response(messages, user_id)

        assert result == "Python is a programming language..."
        # Test completed

    @pytest.mark.asyncio
    async def test_get_response_without_rag(self, llm_service):
        """Test response generation without RAG"""
        messages = [{"role": "user", "content": "Hello"}]
        user_id = "U12345"

        # Mock RAG service response
        llm_service.rag_service.generate_response = AsyncMock(
            return_value="Hello without RAG!"
        )

        result = await llm_service.get_response_without_rag(messages, user_id)

        assert result == "Hello without RAG!"
        # Verify RAG service was called with use_rag=False
        llm_service.rag_service.generate_response.assert_called_once_with(
            query="Hello",
            conversation_history=[],
            system_message=None,
            use_rag=False,
            session_id=None,
            user_id="U12345",
        )

    @pytest.mark.asyncio
    async def test_get_response_error(self, llm_service):
        """Test response generation with error"""
        messages = [{"role": "user", "content": "Hello"}]

        # Mock RAG service to raise exception
        llm_service.rag_service.generate_response = AsyncMock(
            side_effect=Exception("API error")
        )

        result = await llm_service.get_response(messages)

        assert result is None

    @pytest.mark.asyncio
    async def test_ingest_documents_success(self, llm_service):
        """Test document ingestion"""
        documents = [{"content": "Test document", "metadata": {"source": "test"}}]

        # Mock RAG service ingestion
        llm_service.rag_service.ingest_documents = AsyncMock(return_value=5)
        llm_service.settings.vector.enabled = True

        result = await llm_service.ingest_documents(documents)

        assert result == 5
        llm_service.rag_service.ingest_documents.assert_called_once_with(documents)

    @pytest.mark.asyncio
    async def test_ingest_documents_disabled(self, llm_service):
        """Test document ingestion when vector storage is disabled"""
        documents = [{"content": "Test document"}]

        llm_service.settings.vector.enabled = False

        result = await llm_service.ingest_documents(documents)

        assert result == 0

    @pytest.mark.asyncio
    async def test_get_system_status(self, llm_service):
        """Test system status retrieval"""
        expected_status = {
            "rag_enabled": False,
            "llm_provider": "openai",
            "llm_model": "gpt-4o-mini",
        }

        llm_service.rag_service.get_system_status = AsyncMock(
            return_value=expected_status
        )

        result = await llm_service.get_system_status()

        assert result == expected_status
        llm_service.rag_service.get_system_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_close(self, llm_service):
        """Test closing LLM service"""
        llm_service.rag_service.close = AsyncMock()

        await llm_service.close()

        llm_service.rag_service.close.assert_called_once()
