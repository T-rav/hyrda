"""Comprehensive tests for LLMService.

Tests cover:
- Initialization with settings and dependencies
- LLM response generation with RAG
- Response generation without RAG
- Document ingestion
- System status retrieval
- Error handling and fallbacks
- Metrics recording
- Resource cleanup
- Factory function
"""

import os
import sys
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Mock the query_rewriter module before importing retrieval_service
sys.modules["services.query_rewriter"] = MagicMock()

# Mock handlers module (from bot service) that some tests reference
sys.modules["handlers"] = MagicMock()
sys.modules["handlers.message_handlers"] = MagicMock()

from config.settings import LangfuseSettings, LLMSettings, Settings  # noqa: E402
from services.llm_service import LLMService, create_llm_service  # noqa: E402


class TestLLMServiceInitialization:
    """Test LLMService initialization."""

    def test_initialization_with_settings(self):
        """Test initialization with full settings."""
        # Arrange
        settings = Mock(spec=Settings)
        settings.llm = Mock(spec=LLMSettings)
        settings.llm.provider = "openai"
        settings.llm.model = "gpt-4o-mini"
        settings.langfuse = Mock(spec=LangfuseSettings)
        settings.langfuse.enabled = False
        settings.environment = "test"

        # Mock dependencies
        with patch("services.llm_service.PromptService"):
            with patch("services.llm_service.RAGService"):
                with patch(
                    "services.llm_service.initialize_langfuse_service"
                ) as mock_langfuse:
                    mock_langfuse.return_value = Mock(enabled=False)

                    # Act
                    service = LLMService(settings)

                    # Assert
                    assert service.settings == settings
                    assert service.model == "gpt-4o-mini"
                    assert service.api_url == "openai API"
                    assert service.use_hybrid is False

    def test_initialization_with_langfuse_enabled(self):
        """Test initialization with Langfuse observability enabled."""
        # Arrange
        settings = Mock(spec=Settings)
        settings.llm = Mock(spec=LLMSettings)
        settings.llm.provider = "openai"
        settings.llm.model = "gpt-4o-mini"
        settings.langfuse = Mock(spec=LangfuseSettings)
        settings.langfuse.enabled = True
        settings.environment = "production"

        # Mock dependencies
        with patch("services.llm_service.PromptService"):
            with patch("services.llm_service.RAGService"):
                with patch(
                    "services.llm_service.initialize_langfuse_service"
                ) as mock_langfuse:
                    mock_langfuse_service = Mock()
                    mock_langfuse_service.enabled = True
                    mock_langfuse.return_value = mock_langfuse_service

                    # Act
                    service = LLMService(settings)

                    # Assert
                    assert service.langfuse_service.enabled is True
                    mock_langfuse.assert_called_once_with(
                        settings.langfuse, "production"
                    )

    def test_initialization_creates_prompt_service(self):
        """Test that PromptService is initialized."""
        # Arrange
        settings = Mock(spec=Settings)
        settings.llm = Mock(spec=LLMSettings)
        settings.llm.provider = "openai"
        settings.llm.model = "gpt-4o-mini"
        settings.langfuse = Mock(spec=LangfuseSettings)
        settings.environment = "test"

        # Mock dependencies
        with patch("services.llm_service.PromptService") as mock_prompt_service:
            with patch("services.llm_service.RAGService"):
                with patch(
                    "services.llm_service.initialize_langfuse_service"
                ) as mock_langfuse:
                    mock_langfuse.return_value = Mock(enabled=False)

                    # Act
                    service = LLMService(settings)

                    # Assert
                    mock_prompt_service.assert_called_once_with(settings)
                    assert service.prompt_service is not None

    def test_initialization_creates_rag_service(self):
        """Test that RAGService is initialized."""
        # Arrange
        settings = Mock(spec=Settings)
        settings.llm = Mock(spec=LLMSettings)
        settings.llm.provider = "openai"
        settings.llm.model = "gpt-4o-mini"
        settings.langfuse = Mock(spec=LangfuseSettings)
        settings.environment = "test"

        # Mock dependencies
        with patch("services.llm_service.PromptService"):
            with patch("services.llm_service.RAGService") as mock_rag_service:
                with patch(
                    "services.llm_service.initialize_langfuse_service"
                ) as mock_langfuse:
                    mock_langfuse.return_value = Mock(enabled=False)

                    # Act
                    service = LLMService(settings)

                    # Assert
                    mock_rag_service.assert_called_once_with(settings)
                    assert service.rag_service is not None


class TestLLMServiceInitialize:
    """Test LLMService async initialization."""

    @pytest.mark.asyncio
    async def test_initialize_calls_rag_service(self):
        """Test that initialize calls RAG service initialization."""
        # Arrange
        settings = Mock(spec=Settings)
        settings.llm = Mock(spec=LLMSettings)
        settings.llm.provider = "openai"
        settings.llm.model = "gpt-4o-mini"
        settings.langfuse = Mock(spec=LangfuseSettings)
        settings.environment = "test"

        # Mock dependencies
        with patch("services.llm_service.PromptService"):
            with patch("services.llm_service.RAGService") as mock_rag_service:
                with patch(
                    "services.llm_service.initialize_langfuse_service"
                ) as mock_langfuse:
                    mock_langfuse.return_value = Mock(enabled=False)

                    mock_rag = AsyncMock()
                    mock_rag.initialize = AsyncMock()
                    mock_rag_service.return_value = mock_rag

                    service = LLMService(settings)

                    # Act
                    await service.initialize()

                    # Assert
                    mock_rag.initialize.assert_called_once()


class TestGetResponse:
    """Test get_response method."""

    @pytest.mark.asyncio
    async def test_get_response_success_with_rag(self):
        """Test successful response generation with RAG enabled."""
        # Arrange
        settings = Mock(spec=Settings)
        settings.llm = Mock(spec=LLMSettings)
        settings.llm.provider = "openai"
        settings.llm.model = "gpt-4o-mini"
        settings.langfuse = Mock(spec=LangfuseSettings)
        settings.environment = "test"

        messages = [{"role": "user", "content": "What is Python?"}]

        # Mock dependencies
        with patch("services.llm_service.PromptService"):
            with patch("services.llm_service.RAGService") as mock_rag_service:
                with patch(
                    "services.llm_service.initialize_langfuse_service"
                ) as mock_langfuse:
                    with patch(
                        "services.llm_service.get_metrics_service"
                    ) as mock_metrics:
                        mock_langfuse.return_value = Mock(enabled=False)
                        mock_metrics.return_value = None

                        mock_rag = AsyncMock()
                        mock_rag.generate_response = AsyncMock(
                            return_value="Python is a programming language"
                        )
                        mock_rag_service.return_value = mock_rag

                        service = LLMService(settings)

                        # Mock get_user_system_prompt
                        with patch(
                            "handlers.message_handlers.get_user_system_prompt",
                            return_value="You are a helpful assistant",
                        ):
                            # Act
                            result = await service.get_response(
                                messages=messages,
                                user_id="U123",
                                use_rag=True,
                                conversation_id="C123",
                            )

                            # Assert
                            assert result == "Python is a programming language"
                            mock_rag.generate_response.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_response_success_without_rag(self):
        """Test successful response generation with RAG disabled."""
        # Arrange
        settings = Mock(spec=Settings)
        settings.llm = Mock(spec=LLMSettings)
        settings.llm.provider = "openai"
        settings.llm.model = "gpt-4o-mini"
        settings.langfuse = Mock(spec=LangfuseSettings)
        settings.environment = "test"

        messages = [{"role": "user", "content": "Hello"}]

        # Mock dependencies
        with patch("services.llm_service.PromptService"):
            with patch("services.llm_service.RAGService") as mock_rag_service:
                with patch(
                    "services.llm_service.initialize_langfuse_service"
                ) as mock_langfuse:
                    with patch(
                        "services.llm_service.get_metrics_service"
                    ) as mock_metrics:
                        mock_langfuse.return_value = Mock(enabled=False)
                        mock_metrics.return_value = None

                        mock_rag = AsyncMock()
                        mock_rag.generate_response = AsyncMock(return_value="Hi there!")
                        mock_rag_service.return_value = mock_rag

                        service = LLMService(settings)

                        # Mock get_user_system_prompt
                        with patch(
                            "handlers.message_handlers.get_user_system_prompt",
                            return_value="You are a helpful assistant",
                        ):
                            # Act
                            result = await service.get_response(
                                messages=messages, user_id="U123", use_rag=False
                            )

                            # Assert
                            assert result == "Hi there!"
                            # Verify use_rag=False was passed
                            call_args = mock_rag.generate_response.call_args
                            assert call_args.kwargs["use_rag"] is False

    @pytest.mark.asyncio
    async def test_get_response_with_current_query_override(self):
        """Test response generation with explicit current_query parameter."""
        # Arrange
        settings = Mock(spec=Settings)
        settings.llm = Mock(spec=LLMSettings)
        settings.llm.provider = "openai"
        settings.llm.model = "gpt-4o-mini"
        settings.langfuse = Mock(spec=LangfuseSettings)
        settings.environment = "test"

        messages = [
            {"role": "user", "content": "Old message"},
            {"role": "assistant", "content": "Old response"},
        ]
        current_query = "What is the weather?"

        # Mock dependencies
        with patch("services.llm_service.PromptService"):
            with patch("services.llm_service.RAGService") as mock_rag_service:
                with patch(
                    "services.llm_service.initialize_langfuse_service"
                ) as mock_langfuse:
                    with patch("services.llm_service.get_metrics_service"):
                        mock_langfuse.return_value = Mock(enabled=False)

                        mock_rag = AsyncMock()
                        mock_rag.generate_response = AsyncMock(
                            return_value="It's sunny"
                        )
                        mock_rag_service.return_value = mock_rag

                        service = LLMService(settings)

                        # Mock get_user_system_prompt
                        with patch(
                            "handlers.message_handlers.get_user_system_prompt",
                            return_value="You are a helpful assistant",
                        ):
                            # Act
                            result = await service.get_response(
                                messages=messages,
                                user_id="U123",
                                current_query=current_query,
                            )

                            # Assert
                            assert result == "It's sunny"
                            # Verify current_query was used
                            call_args = mock_rag.generate_response.call_args
                            assert call_args.kwargs["query"] == "What is the weather?"
                            # Verify full history was passed
                            assert call_args.kwargs["conversation_history"] == messages

    @pytest.mark.asyncio
    async def test_get_response_with_document_content(self):
        """Test response generation with document content."""
        # Arrange
        settings = Mock(spec=Settings)
        settings.llm = Mock(spec=LLMSettings)
        settings.llm.provider = "openai"
        settings.llm.model = "gpt-4o-mini"
        settings.langfuse = Mock(spec=LangfuseSettings)
        settings.environment = "test"

        messages = [{"role": "user", "content": "Summarize this document"}]
        document_content = "This is the document content"
        document_filename = "test.pdf"

        # Mock dependencies
        with patch("services.llm_service.PromptService"):
            with patch("services.llm_service.RAGService") as mock_rag_service:
                with patch(
                    "services.llm_service.initialize_langfuse_service"
                ) as mock_langfuse:
                    with patch("services.llm_service.get_metrics_service"):
                        mock_langfuse.return_value = Mock(enabled=False)

                        mock_rag = AsyncMock()
                        mock_rag.generate_response = AsyncMock(
                            return_value="Document summary"
                        )
                        mock_rag_service.return_value = mock_rag

                        service = LLMService(settings)

                        # Mock get_user_system_prompt
                        with patch(
                            "handlers.message_handlers.get_user_system_prompt",
                            return_value="You are a helpful assistant",
                        ):
                            # Act
                            result = await service.get_response(
                                messages=messages,
                                user_id="U123",
                                document_content=document_content,
                                document_filename=document_filename,
                            )

                            # Assert
                            assert result == "Document summary"
                            call_args = mock_rag.generate_response.call_args
                            assert (
                                call_args.kwargs["document_content"] == document_content
                            )
                            assert (
                                call_args.kwargs["document_filename"]
                                == document_filename
                            )

    @pytest.mark.asyncio
    async def test_get_response_extracts_query_from_messages(self):
        """Test that query is extracted from messages when not provided."""
        # Arrange
        settings = Mock(spec=Settings)
        settings.llm = Mock(spec=LLMSettings)
        settings.llm.provider = "openai"
        settings.llm.model = "gpt-4o-mini"
        settings.langfuse = Mock(spec=LangfuseSettings)
        settings.environment = "test"

        messages = [
            {"role": "user", "content": "First question"},
            {"role": "assistant", "content": "First answer"},
            {"role": "user", "content": "Second question"},
        ]

        # Mock dependencies
        with patch("services.llm_service.PromptService"):
            with patch("services.llm_service.RAGService") as mock_rag_service:
                with patch(
                    "services.llm_service.initialize_langfuse_service"
                ) as mock_langfuse:
                    with patch("services.llm_service.get_metrics_service"):
                        mock_langfuse.return_value = Mock(enabled=False)

                        mock_rag = AsyncMock()
                        mock_rag.generate_response = AsyncMock(return_value="Answer")
                        mock_rag_service.return_value = mock_rag

                        service = LLMService(settings)

                        # Mock get_user_system_prompt
                        with patch(
                            "handlers.message_handlers.get_user_system_prompt",
                            return_value="You are a helpful assistant",
                        ):
                            # Act
                            result = await service.get_response(
                                messages=messages, user_id="U123"
                            )

                            # Assert
                            assert result == "Answer"
                            call_args = mock_rag.generate_response.call_args
                            # Last user message should be extracted as query
                            assert call_args.kwargs["query"] == "Second question"

    @pytest.mark.asyncio
    async def test_get_response_no_user_query_returns_none(self):
        """Test that None is returned when no user query found."""
        # Arrange
        settings = Mock(spec=Settings)
        settings.llm = Mock(spec=LLMSettings)
        settings.llm.provider = "openai"
        settings.llm.model = "gpt-4o-mini"
        settings.langfuse = Mock(spec=LangfuseSettings)
        settings.environment = "test"

        messages = [{"role": "assistant", "content": "Only assistant messages"}]

        # Mock dependencies
        with patch("services.llm_service.PromptService"):
            with patch("services.llm_service.RAGService"):
                with patch(
                    "services.llm_service.initialize_langfuse_service"
                ) as mock_langfuse:
                    with patch("services.llm_service.get_metrics_service"):
                        mock_langfuse.return_value = Mock(enabled=False)

                        service = LLMService(settings)

                        # Mock get_user_system_prompt
                        with patch("handlers.message_handlers.get_user_system_prompt"):
                            # Act
                            result = await service.get_response(
                                messages=messages, user_id="U123"
                            )

                            # Assert
                            assert result is None

    @pytest.mark.asyncio
    async def test_get_response_records_success_metrics(self):
        """Test that success metrics are recorded."""
        # Arrange
        settings = Mock(spec=Settings)
        settings.llm = Mock(spec=LLMSettings)
        settings.llm.provider = "openai"
        settings.llm.model = "gpt-4o-mini"
        settings.langfuse = Mock(spec=LangfuseSettings)
        settings.environment = "test"

        messages = [{"role": "user", "content": "Test"}]

        # Mock dependencies
        with patch("services.llm_service.PromptService"):
            with patch("services.llm_service.RAGService") as mock_rag_service:
                with patch(
                    "services.llm_service.initialize_langfuse_service"
                ) as mock_langfuse:
                    with patch(
                        "services.llm_service.get_metrics_service"
                    ) as mock_metrics:
                        mock_langfuse.return_value = Mock(enabled=False)

                        mock_metrics_service = Mock()
                        mock_metrics_service.record_llm_request = Mock()
                        mock_metrics.return_value = mock_metrics_service

                        mock_rag = AsyncMock()
                        mock_rag.generate_response = AsyncMock(
                            return_value="This is a test response"
                        )
                        mock_rag_service.return_value = mock_rag

                        service = LLMService(settings)

                        # Mock get_user_system_prompt
                        with patch(
                            "handlers.message_handlers.get_user_system_prompt",
                            return_value="System prompt",
                        ):
                            # Act
                            await service.get_response(
                                messages=messages, user_id="U123"
                            )

                            # Assert
                            mock_metrics_service.record_llm_request.assert_called_once()
                            call_args = (
                                mock_metrics_service.record_llm_request.call_args
                            )
                            assert call_args.kwargs["provider"] == "openai"
                            assert call_args.kwargs["model"] == "gpt-4o-mini"
                            assert call_args.kwargs["status"] == "success"
                            assert call_args.kwargs["duration"] > 0
                            assert call_args.kwargs["tokens"] > 0

    @pytest.mark.asyncio
    async def test_get_response_handles_exception(self):
        """Test that exceptions are handled and return None."""
        # Arrange
        settings = Mock(spec=Settings)
        settings.llm = Mock(spec=LLMSettings)
        settings.llm.provider = "openai"
        settings.llm.model = "gpt-4o-mini"
        settings.langfuse = Mock(spec=LangfuseSettings)
        settings.environment = "test"

        messages = [{"role": "user", "content": "Test"}]

        # Mock dependencies
        with patch("services.llm_service.PromptService"):
            with patch("services.llm_service.RAGService") as mock_rag_service:
                with patch(
                    "services.llm_service.initialize_langfuse_service"
                ) as mock_langfuse:
                    with patch(
                        "services.llm_service.get_metrics_service"
                    ) as mock_metrics:
                        mock_langfuse.return_value = Mock(enabled=False)

                        mock_metrics_service = Mock()
                        mock_metrics_service.record_llm_request = Mock()
                        mock_metrics.return_value = mock_metrics_service

                        mock_rag = AsyncMock()
                        mock_rag.generate_response = AsyncMock(
                            side_effect=Exception("LLM error")
                        )
                        mock_rag_service.return_value = mock_rag

                        service = LLMService(settings)

                        # Mock get_user_system_prompt
                        with patch(
                            "handlers.message_handlers.get_user_system_prompt",
                            return_value="System prompt",
                        ):
                            # Act
                            result = await service.get_response(
                                messages=messages, user_id="U123"
                            )

                            # Assert
                            assert result is None
                            # Verify error metric was recorded
                            call_args = (
                                mock_metrics_service.record_llm_request.call_args
                            )
                            assert call_args.kwargs["status"] == "error"

    @pytest.mark.asyncio
    async def test_get_response_with_conversation_cache(self):
        """Test response generation with conversation cache."""
        # Arrange
        settings = Mock(spec=Settings)
        settings.llm = Mock(spec=LLMSettings)
        settings.llm.provider = "openai"
        settings.llm.model = "gpt-4o-mini"
        settings.langfuse = Mock(spec=LangfuseSettings)
        settings.environment = "test"

        messages = [{"role": "user", "content": "Test"}]
        conversation_cache = Mock()

        # Mock dependencies
        with patch("services.llm_service.PromptService"):
            with patch("services.llm_service.RAGService") as mock_rag_service:
                with patch(
                    "services.llm_service.initialize_langfuse_service"
                ) as mock_langfuse:
                    with patch("services.llm_service.get_metrics_service"):
                        mock_langfuse.return_value = Mock(enabled=False)

                        mock_rag = AsyncMock()
                        mock_rag.generate_response = AsyncMock(return_value="Response")
                        mock_rag_service.return_value = mock_rag

                        service = LLMService(settings)

                        # Mock get_user_system_prompt
                        with patch(
                            "handlers.message_handlers.get_user_system_prompt",
                            return_value="System prompt",
                        ):
                            # Act
                            await service.get_response(
                                messages=messages,
                                user_id="U123",
                                conversation_cache=conversation_cache,
                            )

                            # Assert
                            call_args = mock_rag.generate_response.call_args
                            assert (
                                call_args.kwargs["conversation_cache"]
                                == conversation_cache
                            )


class TestGetResponseWithoutRAG:
    """Test get_response_without_rag convenience method."""

    @pytest.mark.asyncio
    async def test_get_response_without_rag_calls_get_response(self):
        """Test that get_response_without_rag calls get_response with use_rag=False."""
        # Arrange
        settings = Mock(spec=Settings)
        settings.llm = Mock(spec=LLMSettings)
        settings.llm.provider = "openai"
        settings.llm.model = "gpt-4o-mini"
        settings.langfuse = Mock(spec=LangfuseSettings)
        settings.environment = "test"

        messages = [{"role": "user", "content": "Test"}]

        # Mock dependencies
        with patch("services.llm_service.PromptService"):
            with patch("services.llm_service.RAGService"):
                with patch(
                    "services.llm_service.initialize_langfuse_service"
                ) as mock_langfuse:
                    mock_langfuse.return_value = Mock(enabled=False)

                    service = LLMService(settings)

                    # Mock get_response
                    service.get_response = AsyncMock(return_value="Response")

                    # Act
                    result = await service.get_response_without_rag(
                        messages=messages, user_id="U123", conversation_id="C123"
                    )

                    # Assert
                    assert result == "Response"
                    service.get_response.assert_called_once_with(
                        messages,
                        "U123",
                        use_rag=False,
                        conversation_id="C123",
                        document_content=None,
                        document_filename=None,
                    )


class TestIngestDocuments:
    """Test document ingestion."""

    @pytest.mark.asyncio
    async def test_ingest_documents_success(self):
        """Test successful document ingestion."""
        # Arrange
        settings = Mock(spec=Settings)
        settings.llm = Mock(spec=LLMSettings)
        settings.llm.provider = "openai"
        settings.llm.model = "gpt-4o-mini"
        settings.langfuse = Mock(spec=LangfuseSettings)
        settings.environment = "test"

        documents = [
            {"content": "Doc 1", "metadata": {"source": "file1.txt"}},
            {"content": "Doc 2", "metadata": {"source": "file2.txt"}},
        ]

        # Mock dependencies
        with patch("services.llm_service.PromptService"):
            with patch("services.llm_service.RAGService") as mock_rag_service:
                with patch(
                    "services.llm_service.initialize_langfuse_service"
                ) as mock_langfuse:
                    mock_langfuse.return_value = Mock(enabled=False)

                    mock_rag = AsyncMock()
                    mock_rag.ingest_documents = AsyncMock(return_value=(2, 0))
                    mock_rag_service.return_value = mock_rag

                    service = LLMService(settings)

                    # Act
                    success_count, error_count = await service.ingest_documents(
                        documents
                    )

                    # Assert
                    assert success_count == 2
                    assert error_count == 0
                    mock_rag.ingest_documents.assert_called_once_with(documents)

    @pytest.mark.asyncio
    async def test_ingest_documents_partial_failure(self):
        """Test document ingestion with partial failures."""
        # Arrange
        settings = Mock(spec=Settings)
        settings.llm = Mock(spec=LLMSettings)
        settings.llm.provider = "openai"
        settings.llm.model = "gpt-4o-mini"
        settings.langfuse = Mock(spec=LangfuseSettings)
        settings.environment = "test"

        documents = [
            {"content": "Doc 1"},
            {"content": "Doc 2"},
            {"content": "Doc 3"},
        ]

        # Mock dependencies
        with patch("services.llm_service.PromptService"):
            with patch("services.llm_service.RAGService") as mock_rag_service:
                with patch(
                    "services.llm_service.initialize_langfuse_service"
                ) as mock_langfuse:
                    mock_langfuse.return_value = Mock(enabled=False)

                    mock_rag = AsyncMock()
                    mock_rag.ingest_documents = AsyncMock(return_value=(2, 1))
                    mock_rag_service.return_value = mock_rag

                    service = LLMService(settings)

                    # Act
                    success_count, error_count = await service.ingest_documents(
                        documents
                    )

                    # Assert
                    assert success_count == 2
                    assert error_count == 1

    @pytest.mark.asyncio
    async def test_ingest_documents_handles_exception(self):
        """Test that ingestion exceptions are handled."""
        # Arrange
        settings = Mock(spec=Settings)
        settings.llm = Mock(spec=LLMSettings)
        settings.llm.provider = "openai"
        settings.llm.model = "gpt-4o-mini"
        settings.langfuse = Mock(spec=LangfuseSettings)
        settings.environment = "test"

        documents = [{"content": "Doc 1"}]

        # Mock dependencies
        with patch("services.llm_service.PromptService"):
            with patch("services.llm_service.RAGService") as mock_rag_service:
                with patch(
                    "services.llm_service.initialize_langfuse_service"
                ) as mock_langfuse:
                    mock_langfuse.return_value = Mock(enabled=False)

                    mock_rag = AsyncMock()
                    mock_rag.ingest_documents = AsyncMock(
                        side_effect=Exception("Ingestion failed")
                    )
                    mock_rag_service.return_value = mock_rag

                    service = LLMService(settings)

                    # Act
                    success_count, error_count = await service.ingest_documents(
                        documents
                    )

                    # Assert
                    assert success_count == 0
                    assert error_count == 1


class TestGetSystemStatus:
    """Test system status retrieval."""

    @pytest.mark.asyncio
    async def test_get_system_status_success(self):
        """Test successful system status retrieval."""
        # Arrange
        settings = Mock(spec=Settings)
        settings.llm = Mock(spec=LLMSettings)
        settings.llm.provider = "openai"
        settings.llm.model = "gpt-4o-mini"
        settings.langfuse = Mock(spec=LangfuseSettings)
        settings.environment = "test"

        expected_status = {
            "vector_db": "connected",
            "documents": 100,
            "status": "healthy",
        }

        # Mock dependencies
        with patch("services.llm_service.PromptService"):
            with patch("services.llm_service.RAGService") as mock_rag_service:
                with patch(
                    "services.llm_service.initialize_langfuse_service"
                ) as mock_langfuse:
                    mock_langfuse.return_value = Mock(enabled=False)

                    mock_rag = AsyncMock()
                    mock_rag.get_system_status = AsyncMock(return_value=expected_status)
                    mock_rag_service.return_value = mock_rag

                    service = LLMService(settings)

                    # Act
                    status = await service.get_system_status()

                    # Assert
                    assert status == expected_status
                    mock_rag.get_system_status.assert_called_once()


class TestClose:
    """Test resource cleanup."""

    @pytest.mark.asyncio
    async def test_close_closes_all_services(self):
        """Test that close() closes all services."""
        # Arrange
        settings = Mock(spec=Settings)
        settings.llm = Mock(spec=LLMSettings)
        settings.llm.provider = "openai"
        settings.llm.model = "gpt-4o-mini"
        settings.langfuse = Mock(spec=LangfuseSettings)
        settings.environment = "test"

        # Mock dependencies
        with patch("services.llm_service.PromptService"):
            with patch("services.llm_service.RAGService") as mock_rag_service:
                with patch(
                    "services.llm_service.initialize_langfuse_service"
                ) as mock_langfuse:
                    mock_langfuse_service = AsyncMock()
                    mock_langfuse_service.enabled = True
                    mock_langfuse_service.close = AsyncMock()
                    mock_langfuse.return_value = mock_langfuse_service

                    mock_rag = AsyncMock()
                    mock_rag.close = AsyncMock()
                    mock_rag_service.return_value = mock_rag

                    service = LLMService(settings)

                    # Act
                    await service.close()

                    # Assert
                    mock_rag.close.assert_called_once()
                    mock_langfuse_service.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_handles_none_langfuse_service(self):
        """Test that close() handles None langfuse_service."""
        # Arrange
        settings = Mock(spec=Settings)
        settings.llm = Mock(spec=LLMSettings)
        settings.llm.provider = "openai"
        settings.llm.model = "gpt-4o-mini"
        settings.langfuse = Mock(spec=LangfuseSettings)
        settings.environment = "test"

        # Mock dependencies
        with patch("services.llm_service.PromptService"):
            with patch("services.llm_service.RAGService") as mock_rag_service:
                with patch(
                    "services.llm_service.initialize_langfuse_service"
                ) as mock_langfuse:
                    # Return a mock with enabled=False
                    mock_langfuse_service = Mock()
                    mock_langfuse_service.enabled = False
                    mock_langfuse_service.close = AsyncMock()
                    mock_langfuse.return_value = mock_langfuse_service

                    mock_rag = AsyncMock()
                    mock_rag.close = AsyncMock()
                    mock_rag_service.return_value = mock_rag

                    service = LLMService(settings)
                    # Set to None after init to test None handling
                    service.langfuse_service = None

                    # Act - Should not raise exception
                    await service.close()

                    # Assert
                    mock_rag.close.assert_called_once()


class TestCreateLLMService:
    """Test create_llm_service factory function."""

    @pytest.mark.asyncio
    async def test_create_llm_service_with_full_settings(self):
        """Test factory creates service with full settings."""
        # Arrange
        llm_settings = Mock(spec=LLMSettings)
        llm_settings.model = "gpt-4"
        llm_settings.provider = "openai"

        # Create a minimal settings mock that has all needed attributes
        mock_settings = Mock()
        mock_settings.llm = llm_settings
        mock_settings.langfuse = Mock()
        mock_settings.langfuse.enabled = False
        mock_settings.environment = "test"
        mock_settings.vector = Mock()
        mock_settings.vector.enabled = True

        # Mock Settings class to return our mock
        with patch("config.settings.Settings", return_value=mock_settings):
            # Mock dependencies
            with patch("services.llm_service.PromptService"):
                with patch("services.llm_service.RAGService") as mock_rag_service:
                    with patch(
                        "services.llm_service.initialize_langfuse_service"
                    ) as mock_langfuse:
                        mock_langfuse_service = Mock()
                        mock_langfuse_service.enabled = False
                        mock_langfuse.return_value = mock_langfuse_service

                        mock_rag = AsyncMock()
                        mock_rag.initialize = AsyncMock()
                        mock_rag_service.return_value = mock_rag

                        # Act
                        service = await create_llm_service(llm_settings)

                        # Assert
                        assert isinstance(service, LLMService)
                        mock_rag.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_llm_service_with_settings_override(self):
        """Test factory with LLM settings override."""
        # Arrange
        llm_settings = Mock(spec=LLMSettings)
        llm_settings.model = "gpt-4"
        llm_settings.provider = "openai"

        # Create mock settings with different LLM settings initially
        original_llm_settings = Mock()
        original_llm_settings.model = "gpt-3.5"
        original_llm_settings.provider = "openai"

        mock_settings = Mock()
        mock_settings.llm = original_llm_settings
        mock_settings.langfuse = Mock()
        mock_settings.langfuse.enabled = False
        mock_settings.environment = "test"
        mock_settings.vector = Mock()
        mock_settings.vector.enabled = True

        # Mock Settings class to return our mock
        with patch("config.settings.Settings", return_value=mock_settings):
            # Mock dependencies
            with patch("services.llm_service.PromptService"):
                with patch("services.llm_service.RAGService") as mock_rag_service:
                    with patch(
                        "services.llm_service.initialize_langfuse_service"
                    ) as mock_langfuse:
                        mock_langfuse_service = Mock()
                        mock_langfuse_service.enabled = False
                        mock_langfuse.return_value = mock_langfuse_service

                        mock_rag = AsyncMock()
                        mock_rag.initialize = AsyncMock()
                        mock_rag_service.return_value = mock_rag

                        # Act
                        service = await create_llm_service(llm_settings)

                        # Assert
                        assert isinstance(service, LLMService)
                        # Verify settings were updated to use provided llm_settings
                        assert service.settings.llm == llm_settings
                        mock_rag.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_llm_service_initializes_service(self):
        """Test that factory initializes the service."""
        # Arrange
        llm_settings = Mock(spec=LLMSettings)
        llm_settings.model = "gpt-4"
        llm_settings.provider = "openai"

        # Create mock settings
        mock_settings = Mock()
        mock_settings.llm = llm_settings
        mock_settings.langfuse = Mock()
        mock_settings.langfuse.enabled = False
        mock_settings.environment = "test"
        mock_settings.vector = Mock()
        mock_settings.vector.enabled = True

        # Mock Settings class to return our mock
        with patch("config.settings.Settings", return_value=mock_settings):
            # Mock dependencies
            with patch("services.llm_service.PromptService"):
                with patch("services.llm_service.RAGService") as mock_rag_service:
                    with patch(
                        "services.llm_service.initialize_langfuse_service"
                    ) as mock_langfuse:
                        mock_langfuse_service = Mock()
                        mock_langfuse_service.enabled = False
                        mock_langfuse.return_value = mock_langfuse_service

                        mock_rag = AsyncMock()
                        mock_rag.initialize = AsyncMock()
                        mock_rag_service.return_value = mock_rag

                        # Act
                        await create_llm_service(llm_settings)

                        # Assert
                        # Verify initialize was called
                        mock_rag.initialize.assert_called_once()
