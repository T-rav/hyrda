"""Integration tests for cross-service trace propagation.

Tests that Langfuse trace context propagates correctly across:
- Bot Service → Agent Service → RAG Service
- Creating unified waterfall traces in Langfuse
"""

from unittest.mock import Mock, patch

import pytest

from services.langfuse_service import LangfuseService
from utils.trace_propagation import (
    add_trace_headers_to_request,
    create_trace_headers,
    extract_trace_context,
)


class TestTraceHeaderCreation:
    """Test trace header creation from context."""

    def test_create_headers_with_full_context(self):
        """Test creating headers with trace_id and parent_span_id."""
        trace_context = {
            "trace_id": "abcd1234567890abcdef1234567890ab",
            "parent_span_id": "fedcba0987654321",
        }

        headers = create_trace_headers(trace_context)

        assert "X-Langfuse-Trace-ID" in headers
        assert headers["X-Langfuse-Trace-ID"] == "abcd1234567890abcdef1234567890ab"
        assert "X-Langfuse-Parent-Span-ID" in headers
        assert headers["X-Langfuse-Parent-Span-ID"] == "fedcba0987654321"

    def test_create_headers_with_trace_id_only(self):
        """Test creating headers with only trace_id."""
        trace_context = {"trace_id": "abcd1234567890abcdef1234567890ab"}

        headers = create_trace_headers(trace_context)

        assert "X-Langfuse-Trace-ID" in headers
        assert "X-Langfuse-Parent-Span-ID" not in headers

    def test_create_headers_with_none_context(self):
        """Test creating headers with None context."""
        headers = create_trace_headers(None)

        assert headers == {}


class TestTraceHeaderExtraction:
    """Test trace context extraction from headers."""

    def test_extract_context_with_both_headers(self):
        """Test extracting context when both headers present."""
        headers = {
            "X-Langfuse-Trace-ID": "abcd1234567890abcdef1234567890ab",
            "X-Langfuse-Parent-Span-ID": "fedcba0987654321",
        }

        context = extract_trace_context(headers)

        assert context is not None
        assert context["trace_id"] == "abcd1234567890abcdef1234567890ab"
        assert context["parent_span_id"] == "fedcba0987654321"

    def test_extract_context_with_trace_id_only(self):
        """Test extracting context with only trace_id header."""
        headers = {"X-Langfuse-Trace-ID": "abcd1234567890abcdef1234567890ab"}

        context = extract_trace_context(headers)

        assert context is not None
        assert context["trace_id"] == "abcd1234567890abcdef1234567890ab"
        assert "parent_span_id" not in context

    def test_extract_context_case_insensitive(self):
        """Test that header extraction is case-insensitive."""
        headers = {
            "x-langfuse-trace-id": "abcd1234567890abcdef1234567890ab",
            "X-LANGFUSE-PARENT-SPAN-ID": "fedcba0987654321",
        }

        context = extract_trace_context(headers)

        assert context is not None
        assert context["trace_id"] == "abcd1234567890abcdef1234567890ab"
        assert context["parent_span_id"] == "fedcba0987654321"

    def test_extract_context_with_no_headers(self):
        """Test extracting context when no trace headers present."""
        headers = {"Content-Type": "application/json"}

        context = extract_trace_context(headers)

        assert context is None

    def test_extract_context_with_none_headers(self):
        """Test extracting context with None headers."""
        context = extract_trace_context(None)

        assert context is None


class TestTraceHeaderAddition:
    """Test adding trace headers to requests."""

    def test_add_headers_to_existing_request(self):
        """Test adding trace headers to existing headers."""
        existing_headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer token",
        }
        trace_context = {
            "trace_id": "abcd1234567890abcdef1234567890ab",
            "parent_span_id": "fedcba0987654321",
        }

        headers = add_trace_headers_to_request(existing_headers, trace_context)

        # Should have original headers
        assert headers["Content-Type"] == "application/json"
        assert headers["Authorization"] == "Bearer token"
        # Should have trace headers
        assert headers["X-Langfuse-Trace-ID"] == "abcd1234567890abcdef1234567890ab"
        assert headers["X-Langfuse-Parent-Span-ID"] == "fedcba0987654321"

    def test_add_headers_to_empty_request(self):
        """Test adding trace headers to empty headers dict."""
        trace_context = {"trace_id": "abcd1234567890abcdef1234567890ab"}

        headers = add_trace_headers_to_request({}, trace_context)

        assert headers["X-Langfuse-Trace-ID"] == "abcd1234567890abcdef1234567890ab"

    def test_add_headers_with_none_existing(self):
        """Test adding trace headers when existing headers is None."""
        trace_context = {"trace_id": "abcd1234567890abcdef1234567890ab"}

        headers = add_trace_headers_to_request(None, trace_context)

        assert headers["X-Langfuse-Trace-ID"] == "abcd1234567890abcdef1234567890ab"


class TestCrossServiceScenarios:
    """Test realistic cross-service trace propagation scenarios."""

    def test_bot_to_agent_service_propagation(self):
        """Test trace propagation from bot to agent-service."""
        # Step 1: Bot service creates root span
        with (
            patch("services.langfuse_service._langfuse_available", True),
            patch("services.langfuse_service.Langfuse") as mock_langfuse,
        ):
            mock_client = Mock()
            mock_obs = Mock()
            mock_obs.id = "root12345678901"  # 16 hex
            mock_obs.trace_id = "abcd1234567890abcdef1234567890ab"  # 32 hex
            mock_client.start_span.return_value = mock_obs
            mock_langfuse.return_value = mock_client

            from pydantic import SecretStr

            from config.settings import LangfuseSettings

            settings = LangfuseSettings(
                enabled=True,
                public_key="pk-test",
                secret_key=SecretStr("sk-test"),
                host="https://cloud.langfuse.com",
                debug=False,
            )
            service = LangfuseService(settings)
            service.client = mock_client

            # Create root span for bot message
            trace_id, root_obs_id = service.start_root_span(
                name="slack_message",
                input_data={"message": "test message"},
            )

            # Step 2: Bot creates headers for agent-service call
            trace_context = {"trace_id": trace_id, "parent_span_id": root_obs_id}
            headers = create_trace_headers(trace_context)

            # Verify headers are created correctly
            assert "X-Langfuse-Trace-ID" in headers
            assert "X-Langfuse-Parent-Span-ID" in headers
            assert headers["X-Langfuse-Trace-ID"] == trace_id
            assert headers["X-Langfuse-Parent-Span-ID"] == root_obs_id

            # Step 3: Agent service extracts trace context
            extracted_context = extract_trace_context(headers)

            # Verify context is extracted correctly
            assert extracted_context is not None
            assert extracted_context["trace_id"] == trace_id
            assert extracted_context["parent_span_id"] == root_obs_id

    def test_agent_to_rag_service_propagation(self):
        """Test trace propagation from agent-service to rag-service."""
        # Incoming trace context from bot service
        incoming_trace_id = "abcd1234567890abcdef1234567890ab"
        incoming_parent_id = "root12345678901"

        # Step 1: Agent service receives request with trace headers
        incoming_headers = {
            "X-Langfuse-Trace-ID": incoming_trace_id,
            "X-Langfuse-Parent-Span-ID": incoming_parent_id,
        }

        # Extract context
        agent_trace_context = extract_trace_context(incoming_headers)
        assert agent_trace_context["trace_id"] == incoming_trace_id

        # Step 2: Agent service does work and creates its own observation
        agent_obs_id = "agent1234567890a"  # Agent's observation ID

        # Step 3: Agent calls RAG service, passing updated context
        rag_trace_context = {
            "trace_id": agent_trace_context["trace_id"],  # Same trace
            "parent_span_id": agent_obs_id,  # Agent obs as parent
        }
        rag_headers = create_trace_headers(rag_trace_context)

        # Verify RAG service receives correct headers
        assert rag_headers["X-Langfuse-Trace-ID"] == incoming_trace_id
        assert rag_headers["X-Langfuse-Parent-Span-ID"] == agent_obs_id

        # Step 4: RAG service extracts context
        rag_extracted_context = extract_trace_context(rag_headers)

        # Verify all services share same trace_id
        assert rag_extracted_context["trace_id"] == incoming_trace_id
        # But parent changes at each level
        assert rag_extracted_context["parent_span_id"] == agent_obs_id

    def test_standalone_service_creates_root_span(self):
        """Test that standalone service call creates its own root span."""
        # No incoming trace headers (standalone entry)
        incoming_headers = {"Content-Type": "application/json"}

        # Extract context (should be None)
        trace_context = extract_trace_context(incoming_headers)
        assert trace_context is None

        # Service should create root span
        with (
            patch("services.langfuse_service._langfuse_available", True),
            patch("services.langfuse_service.Langfuse") as mock_langfuse,
        ):
            mock_client = Mock()
            mock_obs = Mock()
            mock_obs.id = "standalone123456"
            mock_obs.trace_id = "standalone12345678901234567890123"
            mock_client.start_span.return_value = mock_obs
            mock_langfuse.return_value = mock_client

            from pydantic import SecretStr

            from config.settings import LangfuseSettings

            settings = LangfuseSettings(
                enabled=True,
                public_key="pk-test",
                secret_key=SecretStr("sk-test"),
                host="https://cloud.langfuse.com",
                debug=False,
            )
            service = LangfuseService(settings)
            service.client = mock_client

            # Create root span for standalone entry
            trace_id, root_obs_id = service.start_root_span(
                name="rag_query_direct",
                input_data={"query": "test"},
            )

            # Verify new trace was created
            assert trace_id is not None
            assert root_obs_id is not None
            assert len(trace_id) >= 23  # At least 23 chars for trace ID
            assert len(root_obs_id) >= 15  # At least 15 chars for obs ID


class TestEndToEndWaterfall:
    """Test complete end-to-end waterfall scenario."""

    def test_complete_bot_agent_rag_waterfall(self):
        """Test complete trace propagation: Bot → Agent → RAG."""
        with (
            patch("services.langfuse_service._langfuse_available", True),
            patch("services.langfuse_service.Langfuse") as mock_langfuse,
        ):
            mock_client = Mock()

            # Mock observations for each service
            bot_obs = Mock()
            bot_obs.id = "bot1234567890ab"
            bot_obs.trace_id = "trace12345678901234567890123456"

            agent_obs = Mock()
            agent_obs.id = "agent123456789"
            agent_obs.trace_id = "trace12345678901234567890123456"

            rag_obs = Mock()
            rag_obs.id = "rag1234567890a"
            rag_obs.trace_id = "trace12345678901234567890123456"

            mock_client.start_span.side_effect = [bot_obs, agent_obs, rag_obs]
            mock_langfuse.return_value = mock_client

            from pydantic import SecretStr

            from config.settings import LangfuseSettings

            settings = LangfuseSettings(
                enabled=True,
                public_key="pk-test",
                secret_key=SecretStr("sk-test"),
                host="https://cloud.langfuse.com",
                debug=False,
            )
            service = LangfuseService(settings)
            service.client = mock_client

            # Step 1: Bot creates root span
            bot_trace_id, bot_obs_id = service.start_root_span(
                name="slack_message", input_data={"message": "test"}
            )

            # Step 2: Bot calls agent with trace headers
            bot_to_agent_headers = create_trace_headers(
                {"trace_id": bot_trace_id, "parent_span_id": bot_obs_id}
            )

            # Step 3: Agent extracts context
            agent_context = extract_trace_context(bot_to_agent_headers)
            assert agent_context["trace_id"] == bot_trace_id

            # Agent creates its own span
            agent_trace_id, agent_obs_id = service.start_root_span(
                name="agent_exec", input_data={"agent": "test"}
            )

            # Step 4: Agent calls RAG with trace headers
            agent_to_rag_headers = create_trace_headers(
                {"trace_id": bot_trace_id, "parent_span_id": agent_obs_id}
            )

            # Step 5: RAG extracts context
            rag_context = extract_trace_context(agent_to_rag_headers)
            assert rag_context["trace_id"] == bot_trace_id

            # Verify all services share same trace_id
            assert bot_trace_id == agent_context["trace_id"]
            assert bot_trace_id == rag_context["trace_id"]

            # Verify parent hierarchy
            assert agent_context["parent_span_id"] == bot_obs_id
            assert rag_context["parent_span_id"] == agent_obs_id


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
