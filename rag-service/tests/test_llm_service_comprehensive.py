"""
Comprehensive tests for LLM service.

Tests LLM service with mocked RAG, prompt service, and LLM providers.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch

from config.settings import Settings
from services.llm_service import LLMService, create_llm_service, get_llm_service


class TestLLMServiceInitialization:
    """Test LLM service initialization."""

    def test_llm_service_can_be_imported(self):
        """Test that LLMService can be imported."""
        assert LLMService is not None

    def test_llm_service_initialization(self):
        """Test basic LLM service initialization."""
        settings = Settings()
        service = LLMService(settings)

        assert service.settings == settings
        assert service.model == settings.llm.model
        assert service.rag_service is not None
        assert service.prompt_service is not None

    def test_llm_service_has_legacy_properties(self):
        """Test that legacy properties are set for backward compatibility."""
        settings = Settings()
        service = LLMService(settings)

        assert service.model is not None
        assert service.api_url is not None

    def test_llm_service_initializes_rag_service(self):
        """Test that RAG service is initialized."""
        settings = Settings()
        service = LLMService(settings)

        assert service.rag_service is not None
        assert service.use_hybrid is False


class TestGetResponse:
    """Test get_response method."""

    @pytest.mark.asyncio
    async def test_get_response_with_simple_message(self):
        """Test getting response with simple message."""
        settings = Settings()
        service = LLMService(settings)

        # Mock RAG service
        service.rag_service.generate_response = AsyncMock(return_value="Test response")

        messages = [{"role": "user", "content": "Hello"}]
        response = await service.get_response(messages)

        assert response == "Test response"
        service.rag_service.generate_response.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_response_with_conversation_history(self):
        """Test getting response with conversation history."""
        settings = Settings()
        service = LLMService(settings)

        service.rag_service.generate_response = AsyncMock(return_value="Response with history")

        messages = [
            {"role": "user", "content": "First message"},
            {"role": "assistant", "content": "First response"},
            {"role": "user", "content": "Second message"},
        ]

        response = await service.get_response(messages)
        assert response == "Response with history"

    @pytest.mark.asyncio
    async def test_get_response_with_user_id(self):
        """Test getting response with user ID for custom prompts."""
        settings = Settings()
        service = LLMService(settings)

        service.rag_service.generate_response = AsyncMock(return_value="Custom response")

        messages = [{"role": "user", "content": "Hello"}]
        response = await service.get_response(messages, user_id="U123")

        assert response == "Custom response"

    @pytest.mark.asyncio
    async def test_get_response_with_rag_disabled(self):
        """Test getting response without RAG."""
        settings = Settings()
        service = LLMService(settings)

        service.rag_service.generate_response = AsyncMock(return_value="Response without RAG")

        messages = [{"role": "user", "content": "Hello"}]
        response = await service.get_response(messages, use_rag=False)

        # Verify use_rag=False was passed
        call_args = service.rag_service.generate_response.call_args
        assert call_args.kwargs["use_rag"] is False

    @pytest.mark.asyncio
    async def test_get_response_with_conversation_id(self):
        """Test getting response with conversation ID for tracing."""
        settings = Settings()
        service = LLMService(settings)

        service.rag_service.generate_response = AsyncMock(return_value="Traced response")

        messages = [{"role": "user", "content": "Hello"}]
        response = await service.get_response(
            messages, conversation_id="thread_123"
        )

        assert response == "Traced response"

    @pytest.mark.asyncio
    async def test_get_response_with_current_query_override(self):
        """Test getting response with explicit current query."""
        settings = Settings()
        service = LLMService(settings)

        service.rag_service.generate_response = AsyncMock(return_value="Query response")

        messages = [{"role": "user", "content": "Old message"}]
        response = await service.get_response(
            messages, current_query="New query"
        )

        # Verify the new query was used
        call_args = service.rag_service.generate_response.call_args
        assert call_args.kwargs["query"] == "New query"

    @pytest.mark.asyncio
    async def test_get_response_with_document_content(self):
        """Test getting response with uploaded document."""
        settings = Settings()
        service = LLMService(settings)

        service.rag_service.generate_response = AsyncMock(return_value="Document response")

        messages = [{"role": "user", "content": "Analyze this"}]
        response = await service.get_response(
            messages,
            document_content="Document text here",
            document_filename="report.pdf"
        )

        # Verify document was passed
        call_args = service.rag_service.generate_response.call_args
        assert call_args.kwargs["document_content"] == "Document text here"
        assert call_args.kwargs["document_filename"] == "report.pdf"

    @pytest.mark.asyncio
    async def test_get_response_with_conversation_cache(self):
        """Test getting response with conversation cache."""
        settings = Settings()
        service = LLMService(settings)

        service.rag_service.generate_response = AsyncMock(return_value="Cached response")
        mock_cache = Mock()

        messages = [{"role": "user", "content": "Hello"}]
        response = await service.get_response(
            messages, conversation_cache=mock_cache
        )

        # Verify cache was passed
        call_args = service.rag_service.generate_response.call_args
        assert call_args.kwargs["conversation_cache"] == mock_cache

    @pytest.mark.asyncio
    async def test_get_response_handles_no_query(self):
        """Test that None is returned when no query found."""
        settings = Settings()
        service = LLMService(settings)

        service.rag_service.generate_response = AsyncMock(return_value="Response")

        # Empty messages
        messages = []
        response = await service.get_response(messages)

        assert response is None

    @pytest.mark.asyncio
    async def test_get_response_handles_error(self):
        """Test error handling in get_response."""
        settings = Settings()
        service = LLMService(settings)

        # Simulate error
        service.rag_service.generate_response = AsyncMock(
            side_effect=Exception("LLM error")
        )

        messages = [{"role": "user", "content": "Hello"}]
        response = await service.get_response(messages)

        assert response is None

    @pytest.mark.asyncio
    async def test_get_response_handles_value_error(self):
        """Test handling of ValueError."""
        settings = Settings()
        service = LLMService(settings)

        service.rag_service.generate_response = AsyncMock(
            side_effect=ValueError("Invalid input")
        )

        messages = [{"role": "user", "content": "Hello"}]
        response = await service.get_response(messages)

        assert response is None

    @pytest.mark.asyncio
    async def test_get_response_handles_connection_error(self):
        """Test handling of ConnectionError."""
        settings = Settings()
        service = LLMService(settings)

        service.rag_service.generate_response = AsyncMock(
            side_effect=ConnectionError("Network error")
        )

        messages = [{"role": "user", "content": "Hello"}]
        response = await service.get_response(messages)

        assert response is None


class TestGetResponseWithoutRAG:
    """Test get_response_without_rag convenience method."""

    @pytest.mark.asyncio
    async def test_get_response_without_rag_calls_with_use_rag_false(self):
        """Test that convenience method disables RAG."""
        settings = Settings()
        service = LLMService(settings)

        service.rag_service.generate_response = AsyncMock(return_value="No RAG response")

        messages = [{"role": "user", "content": "Hello"}]
        response = await service.get_response_without_rag(messages)

        # Verify use_rag=False was passed
        call_args = service.rag_service.generate_response.call_args
        assert call_args.kwargs["use_rag"] is False

    @pytest.mark.asyncio
    async def test_get_response_without_rag_with_user_id(self):
        """Test convenience method with user ID."""
        settings = Settings()
        service = LLMService(settings)

        service.rag_service.generate_response = AsyncMock(return_value="No RAG")

        messages = [{"role": "user", "content": "Hello"}]
        response = await service.get_response_without_rag(messages, user_id="U123")

        assert response == "No RAG"


class TestDocumentIngestion:
    """Test document ingestion."""

    @pytest.mark.asyncio
    async def test_ingest_documents_success(self):
        """Test successful document ingestion."""
        settings = Settings()
        service = LLMService(settings)

        service.rag_service.ingest_documents = AsyncMock(return_value=(5, 0))

        documents = [
            {"content": "Doc 1", "metadata": {}},
            {"content": "Doc 2", "metadata": {}},
        ]

        success, error = await service.ingest_documents(documents)
        assert success == 5
        assert error == 0

    @pytest.mark.asyncio
    async def test_ingest_documents_partial_failure(self):
        """Test document ingestion with partial failure."""
        settings = Settings()
        service = LLMService(settings)

        service.rag_service.ingest_documents = AsyncMock(return_value=(3, 2))

        documents = [{"content": f"Doc {i}"} for i in range(5)]

        success, error = await service.ingest_documents(documents)
        assert success == 3
        assert error == 2

    @pytest.mark.asyncio
    async def test_ingest_documents_handles_error(self):
        """Test ingestion error handling."""
        settings = Settings()
        service = LLMService(settings)

        service.rag_service.ingest_documents = AsyncMock(
            side_effect=Exception("Ingestion failed")
        )

        documents = [{"content": "Doc"}]

        success, error = await service.ingest_documents(documents)
        assert success == 0
        assert error == len(documents)


class TestSystemStatus:
    """Test system status retrieval."""

    @pytest.mark.asyncio
    async def test_get_system_status(self):
        """Test getting system status."""
        settings = Settings()
        service = LLMService(settings)

        mock_status = {
            "provider": "openai",
            "model": "gpt-4",
            "rag_enabled": True,
        }
        service.rag_service.get_system_status = AsyncMock(return_value=mock_status)

        status = await service.get_system_status()
        assert status == mock_status


class TestServiceLifecycle:
    """Test service initialization and cleanup."""

    @pytest.mark.asyncio
    async def test_initialize(self):
        """Test async initialization."""
        settings = Settings()
        service = LLMService(settings)

        service.rag_service.initialize = AsyncMock()

        await service.initialize()
        service.rag_service.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_close(self):
        """Test service cleanup."""
        settings = Settings()
        service = LLMService(settings)

        service.rag_service.close = AsyncMock()
        service.langfuse_service.close = AsyncMock()

        await service.close()

        service.rag_service.close.assert_called_once()


class TestCreateLLMService:
    """Test create_llm_service factory function."""

    @pytest.mark.asyncio
    async def test_create_llm_service_with_settings(self):
        """Test creating LLM service with settings."""
        settings = Settings()

        # Mock RAG service initialize to avoid Qdrant connection
        with patch('services.llm_service.RAGService') as MockRAG:
            mock_rag = AsyncMock()
            mock_rag.initialize = AsyncMock()
            MockRAG.return_value = mock_rag

            service = await create_llm_service(settings)

            assert service is not None
            assert isinstance(service, LLMService)

    @pytest.mark.asyncio
    async def test_create_llm_service_initializes(self):
        """Test that factory initializes the service."""
        settings = Settings()

        # Mock RAG service to avoid Qdrant connection
        with patch('services.llm_service.RAGService') as MockRAG:
            mock_rag = AsyncMock()
            mock_rag.initialize = AsyncMock()
            MockRAG.return_value = mock_rag

            service = await create_llm_service(settings)

            # Service should be initialized and ready
            assert service.rag_service is not None
            mock_rag.initialize.assert_called_once()


class TestGlobalServiceManagement:
    """Test global LLM service management."""

    def test_get_llm_service_creates_instance(self):
        """Test that get_llm_service creates instance on demand."""
        service = get_llm_service()

        assert service is not None
        assert isinstance(service, LLMService)


class TestPromptServiceIntegration:
    """Test LLM service integration with prompt service."""

    @pytest.mark.asyncio
    async def test_get_response_uses_prompt_service(self):
        """Test that get_response fetches system prompt from prompt service."""
        settings = Settings()
        service = LLMService(settings)

        # Mock prompt service
        mock_prompt_service = Mock()
        mock_prompt_service.get_system_prompt.return_value = "Custom system prompt from Langfuse"

        # Mock RAG service
        mock_rag = AsyncMock()
        mock_rag.generate_response = AsyncMock(return_value="Test response")
        service.rag_service = mock_rag

        # Patch get_prompt_service to return our mock
        with patch("services.prompt_service.get_prompt_service", return_value=mock_prompt_service):
            # Call get_response
            result = await service.get_response(
                messages=[{"role": "user", "content": "test query"}],
                user_id="test-user",
                use_rag=True,
            )

            # Verify prompt service was called
            mock_prompt_service.get_system_prompt.assert_called_once_with("test-user")

            # Verify RAG service received the custom system prompt
            rag_call = mock_rag.generate_response.call_args
            assert rag_call.kwargs["system_message"] == "Custom system prompt from Langfuse"

    @pytest.mark.asyncio
    async def test_get_response_uses_default_prompt_when_service_unavailable(self):
        """Test that get_response uses default prompt when prompt service unavailable."""
        settings = Settings()
        service = LLMService(settings)

        # Set prompt service to None
        service.prompt_service = None

        # Mock RAG service
        mock_rag = AsyncMock()
        mock_rag.generate_response = AsyncMock(return_value="Test response")
        service.rag_service = mock_rag

        # Call get_response
        result = await service.get_response(
            messages=[{"role": "user", "content": "test query"}],
            user_id="test-user",
            use_rag=True,
        )

        # Verify RAG service received the default system prompt
        rag_call = mock_rag.generate_response.call_args
        assert rag_call.kwargs["system_message"] == "You are a helpful AI assistant."
