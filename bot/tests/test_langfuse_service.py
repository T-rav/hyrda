"""Unit tests for Langfuse service with trace context support."""

from unittest.mock import Mock, patch

import pytest
from pydantic import SecretStr

from config.settings import LangfuseSettings
from services.langfuse_service import LangfuseService


@pytest.fixture
def mock_langfuse_settings():
    """Mock Langfuse settings."""
    return LangfuseSettings(
        enabled=True,
        public_key="pk-test-123",
        secret_key=SecretStr("sk-test-456"),
        host="https://cloud.langfuse.com",
        debug=False,
    )


@pytest.fixture
def mock_langfuse_client():
    """Mock Langfuse client."""
    client = Mock()

    # Mock observation
    mock_obs = Mock()
    mock_obs.id = "abcd1234567890ab"  # 16 hex chars
    mock_obs.trace_id = "1234567890abcdef1234567890abcdef"  # 32 hex chars
    mock_obs.end = Mock()

    client.start_observation.return_value = mock_obs
    client.start_generation.return_value = mock_obs
    client.start_span.return_value = mock_obs
    client.flush.return_value = None

    return client


class TestLangfuseServiceTraceContext:
    """Test trace context functionality in LangfuseService."""

    def test_create_trace_context_generates_trace_id(self, mock_langfuse_settings):
        """Test that create_trace_context generates a valid trace ID."""
        with patch("services.langfuse_service._langfuse_available", True):
            service = LangfuseService(mock_langfuse_settings)

            context = service.create_trace_context()

            assert "trace_id" in context
            assert len(context["trace_id"]) == 32  # 32 hex chars without dashes
            assert "-" not in context["trace_id"]

    def test_create_trace_context_with_parent(self, mock_langfuse_settings):
        """Test creating trace context with parent span ID."""
        with patch("services.langfuse_service._langfuse_available", True):
            service = LangfuseService(mock_langfuse_settings)

            parent_id = "abcd1234567890ab"
            context = service.create_trace_context(parent_span_id=parent_id)

            assert "trace_id" in context
            assert "parent_span_id" in context
            assert context["parent_span_id"] == parent_id

    def test_create_trace_context_with_existing_trace_id(self, mock_langfuse_settings):
        """Test creating trace context with existing trace ID."""
        with patch("services.langfuse_service._langfuse_available", True):
            service = LangfuseService(mock_langfuse_settings)

            existing_trace_id = "1234567890abcdef1234567890abcdef"
            context = service.create_trace_context(trace_id=existing_trace_id)

            assert context["trace_id"] == existing_trace_id

    def test_start_root_span_returns_ids(
        self, mock_langfuse_settings, mock_langfuse_client
    ):
        """Test that start_root_span returns trace_id and observation_id."""
        with (
            patch("services.langfuse_service._langfuse_available", True),
            patch(
                "services.langfuse_service.Langfuse", return_value=mock_langfuse_client
            ),
        ):
            service = LangfuseService(mock_langfuse_settings)
            service.client = mock_langfuse_client

            trace_id, obs_id = service.start_root_span(
                name="test_root",
                input_data={"query": "test"},
                metadata={"test": "value"},
            )

            assert trace_id is not None
            assert len(trace_id) == 32  # 32 hex chars
            assert obs_id == "abcd1234567890ab"  # 16 hex chars
            mock_langfuse_client.start_span.assert_called_once()


class TestLangfuseServiceTraceLLMCall:
    """Test trace_llm_call with trace context."""

    def test_trace_llm_call_without_context(
        self, mock_langfuse_settings, mock_langfuse_client
    ):
        """Test LLM call tracing without trace context."""
        with (
            patch("services.langfuse_service._langfuse_available", True),
            patch(
                "services.langfuse_service.Langfuse", return_value=mock_langfuse_client
            ),
        ):
            service = LangfuseService(mock_langfuse_settings)
            service.client = mock_langfuse_client

            obs_id = service.trace_llm_call(
                provider="openai",
                model="gpt-4",
                messages=[{"role": "user", "content": "test"}],
                response="response",
                usage={"input": 10, "output": 20, "total": 30},
            )

            assert obs_id == "abcd1234567890ab"
            mock_langfuse_client.start_generation.assert_called_once()

            # Verify no trace_context was passed
            call_kwargs = mock_langfuse_client.start_generation.call_args[1]
            assert "trace_context" not in call_kwargs

    def test_trace_llm_call_with_context(
        self, mock_langfuse_settings, mock_langfuse_client
    ):
        """Test LLM call tracing with trace context."""
        with (
            patch("services.langfuse_service._langfuse_available", True),
            patch(
                "services.langfuse_service.Langfuse", return_value=mock_langfuse_client
            ),
        ):
            service = LangfuseService(mock_langfuse_settings)
            service.client = mock_langfuse_client

            trace_context = {
                "trace_id": "1234567890abcdef1234567890abcdef",
                "parent_span_id": "fedcba0987654321",
            }

            obs_id = service.trace_llm_call(
                provider="anthropic",
                model="claude-3-5-sonnet",
                messages=[{"role": "user", "content": "test"}],
                response="response",
                trace_context=trace_context,
            )

            assert obs_id == "abcd1234567890ab"
            mock_langfuse_client.start_generation.assert_called_once()

            # Verify trace_context was passed
            call_kwargs = mock_langfuse_client.start_generation.call_args[1]
            assert "trace_context" in call_kwargs
            assert call_kwargs["trace_context"] == trace_context


class TestLangfuseServiceTraceRetrieval:
    """Test trace_retrieval with trace context."""

    def test_trace_retrieval_without_context(
        self, mock_langfuse_settings, mock_langfuse_client
    ):
        """Test retrieval tracing without trace context."""
        with (
            patch("services.langfuse_service._langfuse_available", True),
            patch(
                "services.langfuse_service.Langfuse", return_value=mock_langfuse_client
            ),
        ):
            service = LangfuseService(mock_langfuse_settings)
            service.client = mock_langfuse_client

            results = [
                {
                    "content": "test content",
                    "similarity": 0.9,
                    "metadata": {"file_name": "test.pdf"},
                }
            ]

            obs_id = service.trace_retrieval(
                query="test query",
                results=results,
                metadata={"vector_store": "qdrant"},
            )

            assert obs_id == "abcd1234567890ab"
            mock_langfuse_client.start_span.assert_called_once()

    def test_trace_retrieval_with_context(
        self, mock_langfuse_settings, mock_langfuse_client
    ):
        """Test retrieval tracing with trace context."""
        with (
            patch("services.langfuse_service._langfuse_available", True),
            patch(
                "services.langfuse_service.Langfuse", return_value=mock_langfuse_client
            ),
        ):
            service = LangfuseService(mock_langfuse_settings)
            service.client = mock_langfuse_client

            trace_context = {
                "trace_id": "1234567890abcdef1234567890abcdef",
                "parent_span_id": "fedcba0987654321",
            }

            results = [
                {
                    "content": "test content",
                    "similarity": 0.9,
                    "metadata": {"file_name": "test.pdf"},
                }
            ]

            obs_id = service.trace_retrieval(
                query="test query",
                results=results,
                trace_context=trace_context,
            )

            assert obs_id == "abcd1234567890ab"
            mock_langfuse_client.start_span.assert_called_once()

            # Verify trace_context was passed
            call_kwargs = mock_langfuse_client.start_span.call_args[1]
            assert "trace_context" in call_kwargs
            assert call_kwargs["trace_context"] == trace_context


class TestLangfuseServiceTraceToolExecution:
    """Test trace_tool_execution with trace context."""

    def test_trace_tool_execution_without_context(
        self, mock_langfuse_settings, mock_langfuse_client
    ):
        """Test tool execution tracing without trace context."""
        with (
            patch("services.langfuse_service._langfuse_available", True),
            patch(
                "services.langfuse_service.Langfuse", return_value=mock_langfuse_client
            ),
        ):
            service = LangfuseService(mock_langfuse_settings)
            service.client = mock_langfuse_client

            obs_id = service.trace_tool_execution(
                tool_name="web_search",
                tool_input={"query": "test"},
                tool_output={"results": ["result1", "result2"]},
            )

            assert obs_id == "abcd1234567890ab"
            mock_langfuse_client.start_span.assert_called_once()

    def test_trace_tool_execution_with_context(
        self, mock_langfuse_settings, mock_langfuse_client
    ):
        """Test tool execution tracing with trace context."""
        with (
            patch("services.langfuse_service._langfuse_available", True),
            patch(
                "services.langfuse_service.Langfuse", return_value=mock_langfuse_client
            ),
        ):
            service = LangfuseService(mock_langfuse_settings)
            service.client = mock_langfuse_client

            trace_context = {
                "trace_id": "1234567890abcdef1234567890abcdef",
                "parent_span_id": "fedcba0987654321",
            }

            obs_id = service.trace_tool_execution(
                tool_name="web_search",
                tool_input={"query": "test"},
                tool_output={"results": ["result1", "result2"]},
                trace_context=trace_context,
            )

            assert obs_id == "abcd1234567890ab"
            mock_langfuse_client.start_span.assert_called_once()

            # Verify trace_context was passed
            call_kwargs = mock_langfuse_client.start_span.call_args[1]
            assert "trace_context" in call_kwargs
            assert call_kwargs["trace_context"] == trace_context


class TestLangfuseServiceTraceConversation:
    """Test trace_conversation with trace context."""

    def test_trace_conversation_without_context(
        self, mock_langfuse_settings, mock_langfuse_client
    ):
        """Test conversation tracing without trace context."""
        with (
            patch("services.langfuse_service._langfuse_available", True),
            patch(
                "services.langfuse_service.Langfuse", return_value=mock_langfuse_client
            ),
        ):
            service = LangfuseService(mock_langfuse_settings)
            service.client = mock_langfuse_client
            service.current_trace = Mock()
            service.current_session_id = "conv-123"

            obs_id = service.trace_conversation(
                user_id="U123",
                conversation_id="conv-123",
                user_message="Hello",
                bot_response="Hi there!",
            )

            assert obs_id == "abcd1234567890ab"
            mock_langfuse_client.start_generation.assert_called_once()

    def test_trace_conversation_with_context(
        self, mock_langfuse_settings, mock_langfuse_client
    ):
        """Test conversation tracing with trace context."""
        with (
            patch("services.langfuse_service._langfuse_available", True),
            patch(
                "services.langfuse_service.Langfuse", return_value=mock_langfuse_client
            ),
        ):
            service = LangfuseService(mock_langfuse_settings)
            service.client = mock_langfuse_client
            service.current_trace = Mock()
            service.current_session_id = "conv-123"

            trace_context = {
                "trace_id": "1234567890abcdef1234567890abcdef",
                "parent_span_id": "fedcba0987654321",
            }

            obs_id = service.trace_conversation(
                user_id="U123",
                conversation_id="conv-123",
                user_message="Hello",
                bot_response="Hi there!",
                trace_context=trace_context,
            )

            assert obs_id == "abcd1234567890ab"
            mock_langfuse_client.start_generation.assert_called_once()

            # Verify trace_context was passed
            call_kwargs = mock_langfuse_client.start_generation.call_args[1]
            assert "trace_context" in call_kwargs
            assert call_kwargs["trace_context"] == trace_context


class TestLangfuseServiceHierarchy:
    """Test hierarchical trace building."""

    def test_root_and_child_trace_creation(
        self, mock_langfuse_settings, mock_langfuse_client
    ):
        """Test creating root span and child observations."""
        with (
            patch("services.langfuse_service._langfuse_available", True),
            patch(
                "services.langfuse_service.Langfuse", return_value=mock_langfuse_client
            ),
        ):
            service = LangfuseService(mock_langfuse_settings)
            service.client = mock_langfuse_client

            # Start root span
            trace_id, root_obs_id = service.start_root_span(
                name="conversation", input_data={"query": "test"}
            )

            assert trace_id is not None
            assert root_obs_id == "abcd1234567890ab"

            # Create child context
            child_context = service.create_trace_context(
                trace_id=trace_id, parent_span_id=root_obs_id
            )

            # Trace retrieval as child
            retrieval_obs_id = service.trace_retrieval(
                query="test query",
                results=[{"content": "test", "similarity": 0.9}],
                trace_context=child_context,
            )

            assert retrieval_obs_id == "abcd1234567890ab"

            # Create grandchild context
            grandchild_context = service.create_trace_context(
                trace_id=trace_id, parent_span_id=retrieval_obs_id
            )

            # Trace LLM call as grandchild
            llm_obs_id = service.trace_llm_call(
                provider="openai",
                model="gpt-4",
                messages=[{"role": "user", "content": "test"}],
                response="response",
                trace_context=grandchild_context,
            )

            assert llm_obs_id == "abcd1234567890ab"

            # Verify all were called
            assert mock_langfuse_client.start_span.call_count == 2  # root + retrieval
            assert mock_langfuse_client.start_generation.call_count == 1  # LLM call


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
