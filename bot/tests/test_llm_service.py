import os
import sys
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add the parent directory to sys.path to allow importing the module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.llm_service import LLMService


# TDD Factory Patterns for LLM Service Testing
class LLMSettingsFactory:
    """Factory for creating LLM service settings with different configurations"""

    @staticmethod
    def create_openai_settings(model: str = "gpt-4o-mini") -> MagicMock:
        """Create OpenAI LLM settings mock"""
        settings = MagicMock()

        # LLM settings
        settings.llm = MagicMock()
        settings.llm.provider = "openai"
        settings.llm.api_key = MagicMock()
        settings.llm.api_key.get_secret_value.return_value = "test-api-key"
        settings.llm.model = model
        settings.llm.temperature = 0.7
        settings.llm.max_tokens = 2000
        settings.llm.base_url = None

        return settings

    @staticmethod
    def create_vector_settings(
        enabled: bool = False, provider: str = "chroma"
    ) -> MagicMock:
        """Create vector settings mock"""
        settings = MagicMock()
        settings.enabled = enabled
        settings.provider = provider
        settings.url = "./test_chroma"
        settings.collection_name = "test_collection"
        return settings

    @staticmethod
    def create_embedding_settings(provider: str = "openai") -> MagicMock:
        """Create embedding settings mock"""
        settings = MagicMock()
        settings.provider = provider
        settings.model = "text-embedding-3-small"
        settings.api_key = None
        settings.chunk_size = 1000
        settings.chunk_overlap = 200
        return settings

    @staticmethod
    def create_rag_settings(
        max_chunks: int = 5,
        similarity_threshold: float = 0.7,
        rerank_enabled: bool = False,
    ) -> MagicMock:
        """Create RAG settings mock"""
        settings = MagicMock()
        settings.max_chunks = max_chunks
        settings.similarity_threshold = similarity_threshold
        settings.rerank_enabled = rerank_enabled
        settings.include_metadata = True
        return settings

    @staticmethod
    def create_complete_settings(
        llm_model: str = "gpt-4o-mini",
        vector_enabled: bool = False,
    ) -> MagicMock:
        """Create complete settings mock with all components"""
        settings = LLMSettingsFactory.create_openai_settings(llm_model)
        settings.vector = LLMSettingsFactory.create_vector_settings(vector_enabled)
        settings.embedding = LLMSettingsFactory.create_embedding_settings()
        settings.rag = LLMSettingsFactory.create_rag_settings()
        return settings


class RAGServiceFactory:
    """Factory for creating RAG service mocks"""

    @staticmethod
    def create_basic_service() -> MagicMock:
        """Create basic RAG service mock"""
        service = MagicMock()
        service.initialize = AsyncMock()
        service.generate_response = AsyncMock(return_value="Test response")
        service.ingest_documents = AsyncMock(return_value=0)
        service.get_system_status = AsyncMock(return_value={"status": "healthy"})
        service.close = AsyncMock()
        return service

    @staticmethod
    def create_service_with_response(response: str) -> MagicMock:
        """Create RAG service mock with specific response"""
        service = RAGServiceFactory.create_basic_service()
        service.generate_response = AsyncMock(return_value=response)
        return service

    @staticmethod
    def create_service_with_ingestion_result(doc_count: int) -> MagicMock:
        """Create RAG service mock with specific ingestion result"""
        service = RAGServiceFactory.create_basic_service()
        service.ingest_documents = AsyncMock(return_value=doc_count)
        return service

    @staticmethod
    def create_service_with_status(status_data: dict[str, Any]) -> MagicMock:
        """Create RAG service mock with specific status"""
        service = RAGServiceFactory.create_basic_service()
        service.get_system_status = AsyncMock(return_value=status_data)
        return service


class MessageFactory:
    """Factory for creating test messages"""

    @staticmethod
    def create_user_message(content: str = "Hello") -> dict[str, str]:
        """Create user message"""
        return {"role": "user", "content": content}

    @staticmethod
    def create_assistant_message(content: str = "Hi there!") -> dict[str, str]:
        """Create assistant message"""
        return {"role": "assistant", "content": content}

    @staticmethod
    def create_conversation(
        user_msg: str = "Hello", assistant_msg: str = "Hi!"
    ) -> list[dict[str, str]]:
        """Create simple conversation"""
        return [
            MessageFactory.create_user_message(user_msg),
            MessageFactory.create_assistant_message(assistant_msg),
        ]


@pytest.fixture
def mock_settings():
    """Create mock settings for testing"""
    return LLMSettingsFactory.create_complete_settings()


@pytest.fixture
def llm_service(mock_settings):
    """Create LLM service for testing"""
    with patch("services.llm_service.RAGService"):
        service = LLMService(mock_settings)
        service.rag_service = RAGServiceFactory.create_basic_service()
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
        await llm_service.initialize()
        llm_service.rag_service.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_response_success(self, llm_service):
        """Test successful response generation"""
        messages = [MessageFactory.create_user_message()]
        user_id = "U12345"
        expected_response = "Hello! How can I help you?"

        llm_service.rag_service = RAGServiceFactory.create_service_with_response(
            expected_response
        )
        result = await llm_service.get_response(messages, user_id)

        assert result == expected_response
        llm_service.rag_service.generate_response.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_response_with_user_prompt(self, llm_service):
        """Test response generation with custom user prompt"""
        messages = [MessageFactory.create_user_message("What is Python?")]
        user_id = "U12345"
        expected_response = "Python is a programming language..."

        llm_service.rag_service = RAGServiceFactory.create_service_with_response(
            expected_response
        )
        result = await llm_service.get_response(messages, user_id)

        assert result == expected_response

    @pytest.mark.asyncio
    async def test_get_response_without_rag(self, llm_service):
        """Test response generation without RAG"""
        messages = [MessageFactory.create_user_message()]
        user_id = "U12345"
        expected_response = "Hello without RAG!"

        llm_service.rag_service = RAGServiceFactory.create_service_with_response(
            expected_response
        )
        result = await llm_service.get_response_without_rag(messages, user_id)

        assert result == expected_response
        # Verify RAG service was called with use_rag=False
        # Note: system_message is now the actual prompt from PromptService
        call_args = llm_service.rag_service.generate_response.call_args
        assert call_args.kwargs["query"] == "Hello"
        assert call_args.kwargs["conversation_history"] == []
        assert (
            call_args.kwargs["system_message"] is not None
        )  # Prompt from Langfuse/PromptService
        assert call_args.kwargs["use_rag"] is False
        assert call_args.kwargs["session_id"] is None
        assert call_args.kwargs["user_id"] == "U12345"
        assert call_args.kwargs["document_content"] is None
        assert call_args.kwargs["document_filename"] is None

    @pytest.mark.asyncio
    async def test_get_response_error(self, llm_service):
        """Test response generation with error"""
        messages = [MessageFactory.create_user_message()]

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

        llm_service.rag_service = (
            RAGServiceFactory.create_service_with_ingestion_result(5)
        )
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

        llm_service.rag_service = RAGServiceFactory.create_service_with_status(
            expected_status
        )
        result = await llm_service.get_system_status()

        assert result == expected_status
        llm_service.rag_service.get_system_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_close(self, llm_service):
        """Test closing LLM service"""
        await llm_service.close()
        llm_service.rag_service.close.assert_called_once()
