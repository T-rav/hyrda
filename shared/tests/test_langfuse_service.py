"""
Comprehensive unit tests for LangfuseService

Tests cover:
- Service initialization with valid/invalid configurations
- All tracing methods (LLM calls, retrieval, tools, documents, conversations)
- Error handling and resilience
- Enabled/disabled state management
- Async operations
- Prompt template fetching
- Lifetime statistics
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from pydantic import SecretStr

from shared.config.settings import LangfuseSettings
from shared.services.langfuse_service import (
    LangfuseService,
    get_langfuse_service,
    initialize_langfuse_service,
)


@pytest.fixture
def valid_settings():
    """Create valid Langfuse settings for testing"""
    return LangfuseSettings(
        enabled=True,
        public_key="test_public_key",
        secret_key=SecretStr("test_secret_key"),
        host="https://cloud.langfuse.com",
        debug=False,
    )


@pytest.fixture
def disabled_settings():
    """Create disabled Langfuse settings"""
    return LangfuseSettings(
        enabled=False,
        public_key="test_public_key",
        secret_key=SecretStr("test_secret_key"),
    )


@pytest.fixture
def empty_credentials_settings():
    """Create settings with empty credentials"""
    return LangfuseSettings(
        enabled=True,
        public_key="",
        secret_key=SecretStr(""),
    )


@pytest.fixture
def mock_langfuse_client():
    """Create a mock Langfuse client"""
    client = MagicMock()
    client.start_trace = MagicMock()
    client.start_span = MagicMock()
    client.start_generation = MagicMock()
    client.get_prompt = MagicMock()
    client.flush = MagicMock()
    return client


class TestLangfuseServiceInitialization:
    """Test LangfuseService initialization"""

    @patch("shared.services.langfuse_service._langfuse_available", True)
    @patch("shared.services.langfuse_service.Langfuse")
    def test_initialization_with_valid_credentials(
        self, mock_langfuse_class, valid_settings, mock_langfuse_client
    ):
        """Test successful initialization with valid credentials"""
        mock_langfuse_class.return_value = mock_langfuse_client

        service = LangfuseService(valid_settings, environment="test")

        assert service.enabled is True
        assert service.environment == "test"
        assert service.client is not None
        mock_langfuse_class.assert_called_once_with(
            public_key="test_public_key",
            secret_key="test_secret_key",
            host="https://cloud.langfuse.com",
            debug=False,
            environment="test",
        )

    def test_initialization_with_disabled_settings(self, disabled_settings):
        """Test initialization when Langfuse is disabled"""
        service = LangfuseService(disabled_settings)

        assert service.enabled is False
        assert service.client is None

    @patch("shared.services.langfuse_service._langfuse_available", True)
    def test_initialization_with_empty_credentials(self, empty_credentials_settings):
        """Test initialization with empty credentials disables service"""
        service = LangfuseService(empty_credentials_settings)

        assert service.enabled is False
        assert service.client is None

    @patch("shared.services.langfuse_service._langfuse_available", False)
    def test_initialization_when_langfuse_unavailable(self, valid_settings):
        """Test initialization when langfuse package is not available"""
        service = LangfuseService(valid_settings)

        assert service.enabled is False
        assert service.client is None

    @patch("shared.services.langfuse_service._langfuse_available", True)
    @patch("shared.services.langfuse_service.Langfuse")
    def test_initialization_with_exception(
        self, mock_langfuse_class, valid_settings
    ):
        """Test initialization handles exceptions gracefully"""
        mock_langfuse_class.side_effect = Exception("Connection error")

        service = LangfuseService(valid_settings)

        assert service.enabled is False
        assert service.client is None


class TestLangfuseServiceTraceLLMCall:
    """Test trace_llm_call method"""

    @patch("shared.services.langfuse_service._langfuse_available", True)
    @patch("shared.services.langfuse_service.Langfuse")
    def test_trace_llm_call_success(
        self, mock_langfuse_class, valid_settings, mock_langfuse_client
    ):
        """Test successful LLM call tracing"""
        mock_generation = MagicMock()
        mock_langfuse_client.start_generation.return_value = mock_generation
        mock_langfuse_class.return_value = mock_langfuse_client

        service = LangfuseService(valid_settings, environment="test")

        messages = [{"role": "user", "content": "Hello"}]
        response = "Hi there!"
        usage = {"prompt_tokens": 10, "completion_tokens": 5}

        service.trace_llm_call(
            provider="openai",
            model="gpt-4",
            messages=messages,
            response=response,
            usage=usage,
            metadata={"test": "value"},
        )

        mock_langfuse_client.start_generation.assert_called_once()
        call_kwargs = mock_langfuse_client.start_generation.call_args[1]
        assert call_kwargs["name"] == "openai_llm_call"
        assert call_kwargs["model"] == "gpt-4"
        assert call_kwargs["input"] == messages
        assert call_kwargs["output"] == response
        assert call_kwargs["usage"] == usage
        assert call_kwargs["metadata"]["provider"] == "openai"
        assert call_kwargs["metadata"]["test"] == "value"
        assert "test" in call_kwargs["tags"]

    @patch("shared.services.langfuse_service._langfuse_available", True)
    @patch("shared.services.langfuse_service.Langfuse")
    def test_trace_llm_call_with_error(
        self, mock_langfuse_class, valid_settings, mock_langfuse_client
    ):
        """Test LLM call tracing with error"""
        mock_generation = MagicMock()
        mock_langfuse_client.start_generation.return_value = mock_generation
        mock_langfuse_class.return_value = mock_langfuse_client

        service = LangfuseService(valid_settings, environment="test")

        service.trace_llm_call(
            provider="openai",
            model="gpt-4",
            messages=[{"role": "user", "content": "Hello"}],
            response=None,
            error="API timeout",
        )

        mock_generation.end.assert_called_once()

    @patch("shared.services.langfuse_service._langfuse_available", True)
    @patch("shared.services.langfuse_service.Langfuse")
    def test_trace_llm_call_with_prompt_template(
        self, mock_langfuse_class, valid_settings, mock_langfuse_client
    ):
        """Test LLM call tracing with prompt template"""
        mock_prompt = MagicMock()
        mock_generation = MagicMock()
        mock_langfuse_client.start_generation.return_value = mock_generation
        mock_langfuse_client.get_prompt.return_value = mock_prompt
        mock_langfuse_class.return_value = mock_langfuse_client

        service = LangfuseService(valid_settings)

        service.trace_llm_call(
            provider="openai",
            model="gpt-4",
            messages=[{"role": "user", "content": "Hello"}],
            response="Hi",
            prompt_template_name="test_template",
            prompt_template_version="v1",
        )

        mock_langfuse_client.get_prompt.assert_called_once_with(
            "test_template", version="v1"
        )
        call_kwargs = mock_langfuse_client.start_generation.call_args[1]
        assert call_kwargs["prompt"] == mock_prompt

    def test_trace_llm_call_when_disabled(self, disabled_settings):
        """Test that tracing is no-op when disabled"""
        service = LangfuseService(disabled_settings)

        # Should not raise any errors
        service.trace_llm_call(
            provider="openai",
            model="gpt-4",
            messages=[],
            response="test",
        )

    @patch("shared.services.langfuse_service._langfuse_available", True)
    @patch("shared.services.langfuse_service.Langfuse")
    def test_trace_llm_call_exception_handling(
        self, mock_langfuse_class, valid_settings, mock_langfuse_client
    ):
        """Test that exceptions in tracing are caught and logged"""
        mock_langfuse_client.start_generation.side_effect = Exception("Trace error")
        mock_langfuse_class.return_value = mock_langfuse_client

        service = LangfuseService(valid_settings)

        # Should not raise exception
        service.trace_llm_call(
            provider="openai",
            model="gpt-4",
            messages=[],
            response="test",
        )


class TestLangfuseServiceTraceRetrieval:
    """Test trace_retrieval method"""

    @patch("shared.services.langfuse_service._langfuse_available", True)
    @patch("shared.services.langfuse_service.Langfuse")
    def test_trace_retrieval_success(
        self, mock_langfuse_class, valid_settings, mock_langfuse_client
    ):
        """Test successful retrieval tracing"""
        mock_span = MagicMock()
        mock_langfuse_client.start_span.return_value = mock_span
        mock_langfuse_class.return_value = mock_langfuse_client

        service = LangfuseService(valid_settings, environment="test")

        query = "What is RAG?"
        results = [
            {
                "content": "RAG stands for Retrieval Augmented Generation",
                "similarity": 0.95,
                "metadata": {"file_name": "doc1.pdf"},
            },
            {
                "content": "RAG improves LLM responses",
                "similarity": 0.85,
                "metadata": {"file_name": "doc2.pdf"},
            },
        ]

        service.trace_retrieval(
            query=query,
            results=results,
            metadata={"retrieval_type": "semantic", "vector_store": "qdrant"},
        )

        mock_langfuse_client.start_span.assert_called_once()
        call_kwargs = mock_langfuse_client.start_span.call_args[1]
        assert call_kwargs["name"] == "rag_retrieval"
        assert call_kwargs["input"]["query"] == query
        assert call_kwargs["output"]["total_chunks_retrieved"] == 2
        assert call_kwargs["output"]["unique_documents"] == 2
        assert "doc1.pdf" in call_kwargs["output"]["document_sources"]
        assert "doc2.pdf" in call_kwargs["output"]["document_sources"]
        mock_span.end.assert_called_once()

    @patch("shared.services.langfuse_service._langfuse_available", True)
    @patch("shared.services.langfuse_service.Langfuse")
    def test_trace_retrieval_with_long_content(
        self, mock_langfuse_class, valid_settings, mock_langfuse_client
    ):
        """Test retrieval tracing with long content creates preview"""
        mock_span = MagicMock()
        mock_langfuse_client.start_span.return_value = mock_span
        mock_langfuse_class.return_value = mock_langfuse_client

        service = LangfuseService(valid_settings)

        long_content = "x" * 400
        results = [{"content": long_content, "similarity": 0.9}]

        service.trace_retrieval(query="test", results=results)

        call_kwargs = mock_langfuse_client.start_span.call_args[1]
        chunk = call_kwargs["output"]["chunks"][0]
        assert len(chunk["content_preview"]) < 310  # 300 + "..."
        assert chunk["content_preview"].endswith("...")

    def test_trace_retrieval_when_disabled(self, disabled_settings):
        """Test retrieval tracing is no-op when disabled"""
        service = LangfuseService(disabled_settings)

        service.trace_retrieval(query="test", results=[])


class TestLangfuseServiceTraceToolExecution:
    """Test trace_tool_execution method"""

    @patch("shared.services.langfuse_service._langfuse_available", True)
    @patch("shared.services.langfuse_service.Langfuse")
    def test_trace_tool_execution_success(
        self, mock_langfuse_class, valid_settings, mock_langfuse_client
    ):
        """Test successful tool execution tracing"""
        mock_span = MagicMock()
        mock_langfuse_client.start_span.return_value = mock_span
        mock_langfuse_class.return_value = mock_langfuse_client

        service = LangfuseService(valid_settings, environment="test")

        tool_input = {"query": "weather in SF"}
        tool_output = {"temperature": 72, "conditions": "sunny"}

        service.trace_tool_execution(
            tool_name="weather_api",
            tool_input=tool_input,
            tool_output=tool_output,
            metadata={"api_version": "v2"},
        )

        mock_langfuse_client.start_span.assert_called_once()
        call_kwargs = mock_langfuse_client.start_span.call_args[1]
        assert call_kwargs["name"] == "tool_weather_api"
        assert call_kwargs["input"]["tool_name"] == "weather_api"
        assert call_kwargs["input"]["tool_parameters"] == tool_input
        assert call_kwargs["output"]["tool_result"] == tool_output
        assert call_kwargs["metadata"]["tool_type"] == "weather_api"
        mock_span.end.assert_called_once()

    @patch("shared.services.langfuse_service._langfuse_available", True)
    @patch("shared.services.langfuse_service.Langfuse")
    def test_trace_tool_execution_with_list_output(
        self, mock_langfuse_class, valid_settings, mock_langfuse_client
    ):
        """Test tool execution tracing with list output"""
        mock_span = MagicMock()
        mock_langfuse_client.start_span.return_value = mock_span
        mock_langfuse_class.return_value = mock_langfuse_client

        service = LangfuseService(valid_settings)

        tool_output = [{"result": 1}, {"result": 2}, {"result": 3}]

        service.trace_tool_execution(
            tool_name="search",
            tool_input={},
            tool_output=tool_output,
        )

        call_kwargs = mock_langfuse_client.start_span.call_args[1]
        assert call_kwargs["output"]["result_count"] == 3

    def test_trace_tool_execution_when_disabled(self, disabled_settings):
        """Test tool execution tracing is no-op when disabled"""
        service = LangfuseService(disabled_settings)

        service.trace_tool_execution(
            tool_name="test",
            tool_input={},
            tool_output={},
        )


class TestLangfuseServiceTraceDocumentIngestion:
    """Test trace_document_ingestion method"""

    @patch("shared.services.langfuse_service._langfuse_available", True)
    @patch("shared.services.langfuse_service.Langfuse")
    def test_trace_document_ingestion_success(
        self, mock_langfuse_class, valid_settings, mock_langfuse_client
    ):
        """Test successful document ingestion tracing"""
        mock_span = MagicMock()
        mock_langfuse_client.start_span.return_value = mock_span
        mock_langfuse_class.return_value = mock_langfuse_client

        service = LangfuseService(valid_settings, environment="test")

        documents = [
            {
                "content": "Document 1 content",
                "metadata": {"file_name": "doc1.pdf", "file_type": "pdf"},
            },
            {
                "content": "Document 2 content",
                "metadata": {"file_name": "doc2.txt", "file_type": "text"},
            },
        ]

        service.trace_document_ingestion(
            documents=documents,
            success_count=10,
            error_count=2,
            metadata={"batch_id": "batch123"},
        )

        mock_langfuse_client.start_span.assert_called_once()
        call_kwargs = mock_langfuse_client.start_span.call_args[1]
        assert call_kwargs["name"] == "document_ingestion"
        assert call_kwargs["input"]["total_documents"] == 2
        assert call_kwargs["output"]["ingestion_results"]["successful_chunks"] == 10
        assert call_kwargs["output"]["ingestion_results"]["failed_chunks"] == 2
        assert call_kwargs["metadata"]["successful_chunks"] == 10
        mock_span.end.assert_called_once()

    @patch("shared.services.langfuse_service._langfuse_available", True)
    @patch("shared.services.langfuse_service.Langfuse")
    def test_trace_document_ingestion_limits_documents(
        self, mock_langfuse_class, valid_settings, mock_langfuse_client
    ):
        """Test document ingestion tracing limits to first 10 documents"""
        mock_span = MagicMock()
        mock_langfuse_client.start_span.return_value = mock_span
        mock_langfuse_class.return_value = mock_langfuse_client

        service = LangfuseService(valid_settings)

        # Create 15 documents
        documents = [
            {"content": f"Doc {i}", "metadata": {"file_name": f"doc{i}.txt"}}
            for i in range(15)
        ]

        service.trace_document_ingestion(
            documents=documents,
            success_count=15,
            error_count=0,
        )

        call_kwargs = mock_langfuse_client.start_span.call_args[1]
        # Should only include first 10 in detailed summaries
        assert len(call_kwargs["input"]["documents"]) == 10
        # But total count should be 15
        assert call_kwargs["input"]["total_documents"] == 15

    def test_trace_document_ingestion_when_disabled(self, disabled_settings):
        """Test document ingestion tracing is no-op when disabled"""
        service = LangfuseService(disabled_settings)

        service.trace_document_ingestion(
            documents=[],
            success_count=0,
            error_count=0,
        )


class TestLangfuseServiceTraceConversation:
    """Test conversation tracing methods"""

    @patch("shared.services.langfuse_service._langfuse_available", True)
    @patch("shared.services.langfuse_service.Langfuse")
    def test_start_conversation_trace(
        self, mock_langfuse_class, valid_settings, mock_langfuse_client
    ):
        """Test starting a conversation trace"""
        mock_span = MagicMock()
        mock_langfuse_client.start_span.return_value = mock_span
        mock_langfuse_class.return_value = mock_langfuse_client

        service = LangfuseService(valid_settings, environment="test")

        service.start_conversation_trace(
            user_id="U123",
            conversation_id="C456",
            metadata={"channel": "general"},
        )

        mock_langfuse_client.start_span.assert_called_once()
        call_kwargs = mock_langfuse_client.start_span.call_args[1]
        assert call_kwargs["name"] == "slack_conversation"
        assert call_kwargs["metadata"]["platform"] == "slack"
        assert call_kwargs["metadata"]["user_id"] == "U123"
        assert call_kwargs["metadata"]["conversation_id"] == "C456"
        assert service.current_trace == mock_span
        assert service.current_session_id == "C456"

    @patch("shared.services.langfuse_service._langfuse_available", True)
    @patch("shared.services.langfuse_service.Langfuse")
    def test_trace_conversation_creates_new_trace(
        self, mock_langfuse_class, valid_settings, mock_langfuse_client
    ):
        """Test trace_conversation creates new trace if needed"""
        mock_span = MagicMock()
        mock_generation = MagicMock()
        mock_langfuse_client.start_span.return_value = mock_span
        mock_langfuse_client.start_generation.return_value = mock_generation
        mock_langfuse_class.return_value = mock_langfuse_client

        service = LangfuseService(valid_settings)

        service.trace_conversation(
            user_id="U123",
            conversation_id="C456",
            user_message="Hello",
            bot_response="Hi there!",
            metadata={"test": "value"},
        )

        # Should create conversation trace
        mock_langfuse_client.start_span.assert_called_once()
        # Should create generation for the turn
        mock_langfuse_client.start_generation.assert_called_once()
        call_kwargs = mock_langfuse_client.start_generation.call_args[1]
        assert call_kwargs["name"] == "conversation_turn"
        assert call_kwargs["input"]["user_message"] == "Hello"
        assert call_kwargs["output"]["bot_response"] == "Hi there!"
        mock_generation.end.assert_called_once()

    @patch("shared.services.langfuse_service._langfuse_available", True)
    @patch("shared.services.langfuse_service.Langfuse")
    def test_trace_conversation_reuses_existing_trace(
        self, mock_langfuse_class, valid_settings, mock_langfuse_client
    ):
        """Test trace_conversation reuses existing trace for same session"""
        mock_span = MagicMock()
        mock_generation = MagicMock()
        mock_langfuse_client.start_span.return_value = mock_span
        mock_langfuse_client.start_generation.return_value = mock_generation
        mock_langfuse_class.return_value = mock_langfuse_client

        service = LangfuseService(valid_settings)

        # Start conversation trace
        service.start_conversation_trace("U123", "C456")

        # Trace conversation turn
        service.trace_conversation(
            user_id="U123",
            conversation_id="C456",
            user_message="Hello",
            bot_response="Hi",
        )

        # Should only create span once (in start_conversation_trace)
        assert mock_langfuse_client.start_span.call_count == 1
        # Should create generation for the turn
        assert mock_langfuse_client.start_generation.call_count == 1

    def test_trace_conversation_when_disabled(self, disabled_settings):
        """Test conversation tracing is no-op when disabled"""
        service = LangfuseService(disabled_settings)

        service.trace_conversation(
            user_id="U123",
            conversation_id="C456",
            user_message="Hello",
            bot_response="Hi",
        )


class TestLangfuseServiceRAGTrace:
    """Test create_rag_trace method"""

    @patch("shared.services.langfuse_service._langfuse_available", True)
    @patch("shared.services.langfuse_service.Langfuse")
    def test_create_rag_trace_success(
        self, mock_langfuse_class, valid_settings, mock_langfuse_client
    ):
        """Test creating a RAG trace"""
        mock_trace = MagicMock()
        mock_langfuse_client.start_trace.return_value = mock_trace
        mock_langfuse_class.return_value = mock_langfuse_client

        service = LangfuseService(valid_settings, environment="test")

        result = service.create_rag_trace(
            user_id="U123",
            conversation_id="C456",
            query="What is RAG?",
            metadata={"source": "slack"},
        )

        assert result == mock_trace
        mock_langfuse_client.start_trace.assert_called_once()
        call_kwargs = mock_langfuse_client.start_trace.call_args[1]
        assert call_kwargs["name"] == "rag_operation"
        assert call_kwargs["input"]["user_query"] == "What is RAG?"
        assert call_kwargs["metadata"]["user_id"] == "U123"
        assert call_kwargs["metadata"]["operation_type"] == "rag_query"

    def test_create_rag_trace_when_disabled(self, disabled_settings):
        """Test RAG trace creation returns None when disabled"""
        service = LangfuseService(disabled_settings)

        result = service.create_rag_trace(
            user_id="U123",
            conversation_id="C456",
            query="test",
        )

        assert result is None


class TestLangfuseServiceScoring:
    """Test score_response method"""

    def test_score_response_when_enabled(self, valid_settings):
        """Test scoring (currently not implemented but should not error)"""
        with patch("shared.services.langfuse_service._langfuse_available", True):
            with patch("shared.services.langfuse_service.Langfuse"):
                service = LangfuseService(valid_settings)

                # Should not raise error
                service.score_response(
                    score_name="quality",
                    value=0.95,
                    comment="Excellent response",
                    metadata={"test": "value"},
                )

    def test_score_response_when_disabled(self, disabled_settings):
        """Test scoring is no-op when disabled"""
        service = LangfuseService(disabled_settings)

        service.score_response(
            score_name="quality",
            value=0.95,
        )


class TestLangfuseServiceFlush:
    """Test flush method"""

    @patch("shared.services.langfuse_service._langfuse_available", True)
    @patch("shared.services.langfuse_service.Langfuse")
    def test_flush_success(
        self, mock_langfuse_class, valid_settings, mock_langfuse_client
    ):
        """Test successful flush"""
        mock_langfuse_class.return_value = mock_langfuse_client

        service = LangfuseService(valid_settings)
        service.flush()

        mock_langfuse_client.flush.assert_called_once()

    @patch("shared.services.langfuse_service._langfuse_available", True)
    @patch("shared.services.langfuse_service.Langfuse")
    def test_flush_with_exception(
        self, mock_langfuse_class, valid_settings, mock_langfuse_client
    ):
        """Test flush handles exceptions"""
        mock_langfuse_client.flush.side_effect = Exception("Flush error")
        mock_langfuse_class.return_value = mock_langfuse_client

        service = LangfuseService(valid_settings)
        # Should not raise exception
        service.flush()

    def test_flush_when_disabled(self, disabled_settings):
        """Test flush is no-op when disabled"""
        service = LangfuseService(disabled_settings)
        service.flush()


class TestLangfuseServicePromptTemplates:
    """Test get_prompt_template method"""

    @patch("shared.services.langfuse_service._langfuse_available", True)
    @patch("shared.services.langfuse_service.Langfuse")
    def test_get_prompt_template_success(
        self, mock_langfuse_class, valid_settings, mock_langfuse_client
    ):
        """Test successful prompt template retrieval"""
        mock_prompt = MagicMock()
        mock_prompt.prompt = "This is a test prompt template"
        mock_langfuse_client.get_prompt.return_value = mock_prompt
        mock_langfuse_class.return_value = mock_langfuse_client

        service = LangfuseService(valid_settings)

        result = service.get_prompt_template("test_template")

        assert result == "This is a test prompt template"
        mock_langfuse_client.get_prompt.assert_called_once_with("test_template")

    @patch("shared.services.langfuse_service._langfuse_available", True)
    @patch("shared.services.langfuse_service.Langfuse")
    def test_get_prompt_template_with_version(
        self, mock_langfuse_class, valid_settings, mock_langfuse_client
    ):
        """Test prompt template retrieval with specific version"""
        mock_prompt = MagicMock()
        mock_prompt.prompt = "Versioned prompt"
        mock_langfuse_client.get_prompt.return_value = mock_prompt
        mock_langfuse_class.return_value = mock_langfuse_client

        service = LangfuseService(valid_settings)

        result = service.get_prompt_template("test_template", version="v2")

        assert result == "Versioned prompt"
        mock_langfuse_client.get_prompt.assert_called_once_with(
            "test_template", version="v2"
        )

    @patch("shared.services.langfuse_service._langfuse_available", True)
    @patch("shared.services.langfuse_service.Langfuse")
    def test_get_prompt_template_not_found(
        self, mock_langfuse_class, valid_settings, mock_langfuse_client
    ):
        """Test prompt template not found returns None"""
        mock_langfuse_client.get_prompt.return_value = None
        mock_langfuse_class.return_value = mock_langfuse_client

        service = LangfuseService(valid_settings)

        result = service.get_prompt_template("nonexistent")

        assert result is None

    @patch("shared.services.langfuse_service._langfuse_available", True)
    @patch("shared.services.langfuse_service.Langfuse")
    def test_get_prompt_template_exception(
        self, mock_langfuse_class, valid_settings, mock_langfuse_client
    ):
        """Test prompt template retrieval handles exceptions"""
        mock_langfuse_client.get_prompt.side_effect = Exception("API error")
        mock_langfuse_class.return_value = mock_langfuse_client

        service = LangfuseService(valid_settings)

        result = service.get_prompt_template("test_template")

        assert result is None

    def test_get_prompt_template_when_disabled(self, disabled_settings):
        """Test prompt template retrieval returns None when disabled"""
        service = LangfuseService(disabled_settings)

        result = service.get_prompt_template("test_template")

        assert result is None


class TestLangfuseServiceLifetimeStats:
    """Test get_lifetime_stats async method"""

    @pytest.mark.asyncio
    @patch("shared.services.langfuse_service._langfuse_available", True)
    @patch("shared.services.langfuse_service.Langfuse")
    async def test_get_lifetime_stats_success(
        self, mock_langfuse_class, valid_settings, mock_langfuse_client
    ):
        """Test successful lifetime stats retrieval"""
        mock_langfuse_class.return_value = mock_langfuse_client

        service = LangfuseService(valid_settings)

        # Create mock responses for each API call
        responses = [
            # User messages response
            MagicMock(
                status=200,
                json=AsyncMock(return_value={"meta": {"totalItems": 50}}),
                __aenter__=AsyncMock(return_value=MagicMock(
                    status=200,
                    json=AsyncMock(return_value={"meta": {"totalItems": 50}})
                )),
                __aexit__=AsyncMock(return_value=None),
            ),
            # Observations response
            MagicMock(
                status=200,
                json=AsyncMock(return_value={"meta": {"totalItems": 200}}),
                __aenter__=AsyncMock(return_value=MagicMock(
                    status=200,
                    json=AsyncMock(return_value={"meta": {"totalItems": 200}})
                )),
                __aexit__=AsyncMock(return_value=None),
            ),
            # Sessions response
            MagicMock(
                status=200,
                json=AsyncMock(return_value={"meta": {"totalItems": 25}}),
                __aenter__=AsyncMock(return_value=MagicMock(
                    status=200,
                    json=AsyncMock(return_value={"meta": {"totalItems": 25}})
                )),
                __aexit__=AsyncMock(return_value=None),
            ),
        ]

        # Create session with responses
        response_iter = iter(responses)
        mock_session = MagicMock()
        mock_session.get = MagicMock(side_effect=lambda *args, **kwargs: next(response_iter))
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            stats = await service.get_lifetime_stats(start_date="2025-10-21")

        assert stats["total_traces"] == 50
        assert stats["total_observations"] == 200
        assert stats["unique_sessions"] == 25
        assert stats["start_date"] == "2025-10-21"
        assert "error" not in stats

    @pytest.mark.asyncio
    async def test_get_lifetime_stats_when_disabled(self, disabled_settings):
        """Test lifetime stats returns error when disabled"""
        service = LangfuseService(disabled_settings)

        stats = await service.get_lifetime_stats()

        assert stats["total_traces"] == 0
        assert stats["total_observations"] == 0
        assert stats["unique_sessions"] == 0
        assert "error" in stats
        assert "not enabled" in stats["error"]

    @pytest.mark.asyncio
    @patch("shared.services.langfuse_service._langfuse_available", True)
    @patch("shared.services.langfuse_service.Langfuse")
    async def test_get_lifetime_stats_api_error(
        self, mock_langfuse_class, valid_settings, mock_langfuse_client
    ):
        """Test lifetime stats handles API errors"""
        mock_langfuse_class.return_value = mock_langfuse_client

        service = LangfuseService(valid_settings)

        # Create error response
        error_response = MagicMock(
            status=500,
            text=AsyncMock(return_value="Internal server error"),
            __aenter__=AsyncMock(return_value=MagicMock(
                status=500,
                text=AsyncMock(return_value="Internal server error")
            )),
            __aexit__=AsyncMock(return_value=None),
        )

        # Create session with error response
        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=error_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            stats = await service.get_lifetime_stats()

        assert stats["total_traces"] == 0
        assert "error" in stats
        assert "500" in stats["error"]

    @pytest.mark.asyncio
    @patch("shared.services.langfuse_service._langfuse_available", True)
    @patch("shared.services.langfuse_service.Langfuse")
    async def test_get_lifetime_stats_exception(
        self, mock_langfuse_class, valid_settings, mock_langfuse_client
    ):
        """Test lifetime stats handles exceptions"""
        mock_langfuse_class.return_value = mock_langfuse_client

        service = LangfuseService(valid_settings)

        with patch("aiohttp.ClientSession", side_effect=Exception("Network error")):
            stats = await service.get_lifetime_stats()

        assert stats["total_traces"] == 0
        assert "error" in stats
        assert "Network error" in stats["error"]


class TestLangfuseServiceClose:
    """Test close async method"""

    @pytest.mark.asyncio
    @patch("shared.services.langfuse_service._langfuse_available", True)
    @patch("shared.services.langfuse_service.Langfuse")
    async def test_close_success(
        self, mock_langfuse_class, valid_settings, mock_langfuse_client
    ):
        """Test successful close"""
        mock_langfuse_class.return_value = mock_langfuse_client

        service = LangfuseService(valid_settings)
        await service.close()

        mock_langfuse_client.flush.assert_called_once()

    @pytest.mark.asyncio
    @patch("shared.services.langfuse_service._langfuse_available", True)
    @patch("shared.services.langfuse_service.Langfuse")
    async def test_close_with_exception(
        self, mock_langfuse_class, valid_settings, mock_langfuse_client
    ):
        """Test close handles exceptions"""
        mock_langfuse_client.flush.side_effect = Exception("Close error")
        mock_langfuse_class.return_value = mock_langfuse_client

        service = LangfuseService(valid_settings)
        # Should not raise exception
        await service.close()

    @pytest.mark.asyncio
    async def test_close_when_disabled(self, disabled_settings):
        """Test close is no-op when disabled"""
        service = LangfuseService(disabled_settings)
        await service.close()


class TestLangfuseServiceGlobalFunctions:
    """Test module-level global functions"""

    def test_initialize_and_get_langfuse_service(self, valid_settings):
        """Test initializing and getting global service instance"""
        with patch("shared.services.langfuse_service._langfuse_available", True):
            with patch("shared.services.langfuse_service.Langfuse"):
                # Initialize global service
                service = initialize_langfuse_service(valid_settings, environment="test")

                # Get global service
                retrieved_service = get_langfuse_service()

                assert retrieved_service is service
                assert retrieved_service.environment == "test"

    def test_get_langfuse_service_before_initialization(self):
        """Test getting service before initialization returns last initialized"""
        # Note: This tests the current behavior where the global is None
        # until explicitly set
        result = get_langfuse_service()
        # Result depends on whether previous tests set it
        # We just verify the function doesn't crash
        assert result is None or isinstance(result, LangfuseService)
