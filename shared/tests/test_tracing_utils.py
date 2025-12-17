"""Unit tests for distributed tracing utilities."""

import logging
from unittest.mock import MagicMock, patch

import pytest

from shared.utils.tracing import (
    TraceContext,
    TraceLogger,
    add_trace_id_to_headers,
    extract_trace_id_from_headers,
    format_trace_summary,
    generate_trace_id,
    get_or_create_trace_id,
    get_parent_trace_id,
    get_trace_id,
    get_trace_info,
    set_parent_trace_id,
    set_trace_id,
)


class TestGenerateTraceId:
    """Test trace ID generation."""

    def test_generate_trace_id_format(self):
        """Test that generated trace ID has correct format."""
        trace_id = generate_trace_id()

        assert trace_id.startswith("trace_")
        assert len(trace_id) == 14  # "trace_" (6) + 8 hex chars

    def test_generate_trace_id_unique(self):
        """Test that generated trace IDs are unique."""
        trace_ids = {generate_trace_id() for _ in range(100)}

        # All 100 should be unique
        assert len(trace_ids) == 100

    def test_generate_trace_id_hex_chars(self):
        """Test that trace ID contains only valid hex characters."""
        trace_id = generate_trace_id()
        hex_part = trace_id.replace("trace_", "")

        # Should only contain 0-9, a-f
        assert all(c in "0123456789abcdef" for c in hex_part)


class TestTraceIdContext:
    """Test trace ID context variable operations."""

    def test_set_and_get_trace_id(self):
        """Test setting and getting trace ID."""
        test_trace_id = "trace_12345678"
        set_trace_id(test_trace_id)

        assert get_trace_id() == test_trace_id

        # Clean up
        set_trace_id(None)

    def test_set_trace_id_none(self):
        """Test setting trace ID to None."""
        set_trace_id("trace_test")
        set_trace_id(None)

        assert get_trace_id() is None

    def test_get_trace_id_when_not_set(self):
        """Test getting trace ID when not set returns None."""
        set_trace_id(None)

        assert get_trace_id() is None

    def test_set_and_get_parent_trace_id(self):
        """Test setting and getting parent trace ID."""
        test_parent_id = "trace_parent123"
        set_parent_trace_id(test_parent_id)

        assert get_parent_trace_id() == test_parent_id

        # Clean up
        set_parent_trace_id(None)

    def test_set_parent_trace_id_none(self):
        """Test setting parent trace ID to None."""
        set_parent_trace_id("trace_parent")
        set_parent_trace_id(None)

        assert get_parent_trace_id() is None

    def test_get_parent_trace_id_when_not_set(self):
        """Test getting parent trace ID when not set returns None."""
        set_parent_trace_id(None)

        assert get_parent_trace_id() is None


class TestGetOrCreateTraceId:
    """Test get or create trace ID functionality."""

    def test_get_or_create_returns_existing(self):
        """Test that existing trace ID is returned."""
        existing_id = "trace_existing"
        set_trace_id(existing_id)

        trace_id = get_or_create_trace_id()

        assert trace_id == existing_id

        # Clean up
        set_trace_id(None)

    def test_get_or_create_creates_new(self):
        """Test that new trace ID is created when not set."""
        set_trace_id(None)

        trace_id = get_or_create_trace_id()

        assert trace_id is not None
        assert trace_id.startswith("trace_")
        assert get_trace_id() == trace_id  # Should be set in context

        # Clean up
        set_trace_id(None)

    def test_get_or_create_sets_context(self):
        """Test that created trace ID is set in context."""
        set_trace_id(None)

        trace_id = get_or_create_trace_id()

        assert get_trace_id() == trace_id

        # Clean up
        set_trace_id(None)


class TestExtractTraceIdFromHeaders:
    """Test trace ID extraction from HTTP headers."""

    def test_extract_trace_id_standard_case(self):
        """Test extracting trace ID with standard header name."""
        headers = {"X-Trace-Id": "trace_12345678"}

        trace_id = extract_trace_id_from_headers(headers)

        assert trace_id == "trace_12345678"

    def test_extract_trace_id_lowercase(self):
        """Test extracting trace ID with lowercase header name."""
        headers = {"x-trace-id": "trace_lowercase"}

        trace_id = extract_trace_id_from_headers(headers)

        assert trace_id == "trace_lowercase"

    def test_extract_trace_id_mixed_case(self):
        """Test extracting trace ID with mixed case header name."""
        headers = {"X-TrAcE-Id": "trace_mixedcase"}

        trace_id = extract_trace_id_from_headers(headers)

        assert trace_id == "trace_mixedcase"

    def test_extract_trace_id_not_found(self):
        """Test extracting trace ID when header is not present."""
        headers = {"Content-Type": "application/json"}

        trace_id = extract_trace_id_from_headers(headers)

        assert trace_id is None

    def test_extract_trace_id_empty_headers(self):
        """Test extracting trace ID from empty headers."""
        headers = {}

        trace_id = extract_trace_id_from_headers(headers)

        assert trace_id is None

    def test_extract_trace_id_multiple_headers(self):
        """Test extracting trace ID among multiple headers."""
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer token",
            "X-Trace-Id": "trace_found",
            "X-Request-Id": "req_123",
        }

        trace_id = extract_trace_id_from_headers(headers)

        assert trace_id == "trace_found"


class TestAddTraceIdToHeaders:
    """Test adding trace ID to HTTP headers."""

    def test_add_trace_id_to_headers_with_explicit_id(self):
        """Test adding explicit trace ID to headers."""
        headers = {"Content-Type": "application/json"}
        trace_id = "trace_explicit"

        result = add_trace_id_to_headers(headers, trace_id)

        assert result["X-Trace-Id"] == trace_id
        assert result["Content-Type"] == "application/json"

    def test_add_trace_id_to_headers_from_context(self):
        """Test adding trace ID from context."""
        set_trace_id("trace_context")
        headers = {"Content-Type": "application/json"}

        result = add_trace_id_to_headers(headers)

        assert result["X-Trace-Id"] == "trace_context"

        # Clean up
        set_trace_id(None)

    def test_add_trace_id_to_headers_creates_new(self):
        """Test that new trace ID is created if not in context."""
        set_trace_id(None)
        headers = {}

        result = add_trace_id_to_headers(headers)

        assert "X-Trace-Id" in result
        assert result["X-Trace-Id"].startswith("trace_")

        # Clean up
        set_trace_id(None)

    def test_add_trace_id_to_headers_preserves_existing(self):
        """Test that existing headers are preserved."""
        headers = {
            "Authorization": "Bearer token",
            "Content-Type": "application/json",
            "X-Custom": "value",
        }

        result = add_trace_id_to_headers(headers, "trace_12345678")

        assert result["Authorization"] == "Bearer token"
        assert result["Content-Type"] == "application/json"
        assert result["X-Custom"] == "value"
        assert result["X-Trace-Id"] == "trace_12345678"

    def test_add_trace_id_to_headers_empty_dict(self):
        """Test adding trace ID to empty headers dict."""
        headers = {}

        result = add_trace_id_to_headers(headers, "trace_empty")

        assert result["X-Trace-Id"] == "trace_empty"


class TestTraceContext:
    """Test TraceContext context manager."""

    def test_trace_context_sets_trace_id(self):
        """Test that TraceContext sets trace ID."""
        trace_id = "trace_test"

        with TraceContext(trace_id):
            assert get_trace_id() == trace_id

    def test_trace_context_generates_trace_id(self):
        """Test that TraceContext generates trace ID if not provided."""
        with TraceContext() as trace_id:
            assert trace_id is not None
            assert trace_id.startswith("trace_")
            assert get_trace_id() == trace_id

    def test_trace_context_restores_previous_trace_id(self):
        """Test that TraceContext restores previous trace ID."""
        set_trace_id("trace_original")

        with TraceContext("trace_nested"):
            assert get_trace_id() == "trace_nested"

        assert get_trace_id() == "trace_original"

        # Clean up
        set_trace_id(None)

    def test_trace_context_restores_none(self):
        """Test that TraceContext restores None if no previous trace ID."""
        set_trace_id(None)

        with TraceContext("trace_temp"):
            assert get_trace_id() == "trace_temp"

        assert get_trace_id() is None

    def test_trace_context_sets_parent_trace_id(self):
        """Test that TraceContext sets parent trace ID."""
        with TraceContext("trace_child", parent_trace_id="trace_parent"):
            assert get_trace_id() == "trace_child"
            assert get_parent_trace_id() == "trace_parent"

    def test_trace_context_restores_parent_trace_id(self):
        """Test that TraceContext restores previous parent trace ID."""
        set_parent_trace_id("trace_original_parent")

        with TraceContext("trace_child", parent_trace_id="trace_nested_parent"):
            assert get_parent_trace_id() == "trace_nested_parent"

        assert get_parent_trace_id() == "trace_original_parent"

        # Clean up
        set_parent_trace_id(None)

    def test_trace_context_nested(self):
        """Test nested TraceContext calls."""
        with TraceContext("trace_outer"):
            assert get_trace_id() == "trace_outer"

            with TraceContext("trace_inner"):
                assert get_trace_id() == "trace_inner"

            assert get_trace_id() == "trace_outer"

    def test_trace_context_exception_handling(self):
        """Test that TraceContext restores state even on exception."""
        set_trace_id("trace_original")

        try:
            with TraceContext("trace_temp"):
                assert get_trace_id() == "trace_temp"
                raise ValueError("Test exception")
        except ValueError:
            pass

        assert get_trace_id() == "trace_original"

        # Clean up
        set_trace_id(None)


class TestGetTraceInfo:
    """Test trace information retrieval."""

    def test_get_trace_info_with_trace_id(self):
        """Test getting trace info when trace ID is set."""
        set_trace_id("trace_12345678")
        set_parent_trace_id(None)

        info = get_trace_info()

        assert info == {"trace_id": "trace_12345678"}

        # Clean up
        set_trace_id(None)

    def test_get_trace_info_with_parent_trace_id(self):
        """Test getting trace info with parent trace ID."""
        set_trace_id("trace_child")
        set_parent_trace_id("trace_parent")

        info = get_trace_info()

        assert info == {"trace_id": "trace_child", "parent_trace_id": "trace_parent"}

        # Clean up
        set_trace_id(None)
        set_parent_trace_id(None)

    def test_get_trace_info_empty(self):
        """Test getting trace info when nothing is set."""
        set_trace_id(None)
        set_parent_trace_id(None)

        info = get_trace_info()

        assert info == {}

    def test_get_trace_info_only_parent(self):
        """Test getting trace info with only parent trace ID."""
        set_trace_id(None)
        set_parent_trace_id("trace_parent")

        info = get_trace_info()

        assert info == {"parent_trace_id": "trace_parent"}

        # Clean up
        set_parent_trace_id(None)


class TestTraceLogger:
    """Test TraceLogger wrapper."""

    @pytest.fixture
    def mock_logger(self):
        """Create a mock logger for testing."""
        with patch("logging.getLogger") as mock_get_logger:
            mock_log = MagicMock()
            mock_get_logger.return_value = mock_log
            yield mock_log

    def test_trace_logger_initialization(self, mock_logger):
        """Test TraceLogger initialization."""
        logger = TraceLogger("test_logger")

        assert logger.logger == mock_logger

    def test_trace_logger_debug_with_trace_id(self, mock_logger):
        """Test debug logging with trace ID."""
        set_trace_id("trace_debug")
        logger = TraceLogger("test")

        logger.debug("Test message")

        mock_logger.log.assert_called_once()
        args, kwargs = mock_logger.log.call_args
        assert args[0] == logging.DEBUG
        assert "[trace_debug]" in args[1]
        assert "Test message" in args[1]
        assert kwargs["extra"]["trace_id"] == "trace_debug"

        # Clean up
        set_trace_id(None)

    def test_trace_logger_info_with_trace_id(self, mock_logger):
        """Test info logging with trace ID."""
        set_trace_id("trace_info")
        logger = TraceLogger("test")

        logger.info("Info message")

        mock_logger.log.assert_called_once()
        args, kwargs = mock_logger.log.call_args
        assert args[0] == logging.INFO
        assert "[trace_info]" in args[1]
        assert "Info message" in args[1]

        # Clean up
        set_trace_id(None)

    def test_trace_logger_warning_with_trace_id(self, mock_logger):
        """Test warning logging with trace ID."""
        set_trace_id("trace_warn")
        logger = TraceLogger("test")

        logger.warning("Warning message")

        mock_logger.log.assert_called_once()
        args, kwargs = mock_logger.log.call_args
        assert args[0] == logging.WARNING
        assert "[trace_warn]" in args[1]

        # Clean up
        set_trace_id(None)

    def test_trace_logger_error_with_trace_id(self, mock_logger):
        """Test error logging with trace ID."""
        set_trace_id("trace_error")
        logger = TraceLogger("test")

        logger.error("Error message")

        mock_logger.log.assert_called_once()
        args, kwargs = mock_logger.log.call_args
        assert args[0] == logging.ERROR
        assert "[trace_error]" in args[1]

        # Clean up
        set_trace_id(None)

    def test_trace_logger_critical_with_trace_id(self, mock_logger):
        """Test critical logging with trace ID."""
        set_trace_id("trace_critical")
        logger = TraceLogger("test")

        logger.critical("Critical message")

        mock_logger.log.assert_called_once()
        args, kwargs = mock_logger.log.call_args
        assert args[0] == logging.CRITICAL
        assert "[trace_critical]" in args[1]

        # Clean up
        set_trace_id(None)

    def test_trace_logger_with_parent_trace_id(self, mock_logger):
        """Test logging with parent trace ID."""
        set_trace_id("trace_child")
        set_parent_trace_id("trace_parent")
        logger = TraceLogger("test")

        logger.info("Message")

        mock_logger.log.assert_called_once()
        args, kwargs = mock_logger.log.call_args
        assert "[trace_child←trace_parent]" in args[1]
        assert kwargs["extra"]["trace_id"] == "trace_child"
        assert kwargs["extra"]["parent_trace_id"] == "trace_parent"

        # Clean up
        set_trace_id(None)
        set_parent_trace_id(None)

    def test_trace_logger_without_trace_id(self, mock_logger):
        """Test logging without trace ID."""
        set_trace_id(None)
        set_parent_trace_id(None)
        logger = TraceLogger("test")

        logger.info("Message without trace")

        mock_logger.log.assert_called_once()
        args, kwargs = mock_logger.log.call_args
        assert args[1] == "Message without trace"
        assert "trace_id" not in kwargs["extra"]

    def test_trace_logger_preserves_extra_kwargs(self, mock_logger):
        """Test that existing extra kwargs are preserved."""
        set_trace_id("trace_test")
        logger = TraceLogger("test")

        logger.info("Message", extra={"custom_key": "custom_value"})

        mock_logger.log.assert_called_once()
        args, kwargs = mock_logger.log.call_args
        assert kwargs["extra"]["trace_id"] == "trace_test"
        assert kwargs["extra"]["custom_key"] == "custom_value"

        # Clean up
        set_trace_id(None)

    def test_trace_logger_with_args(self, mock_logger):
        """Test logging with positional args."""
        set_trace_id("trace_args")
        logger = TraceLogger("test")

        logger.info("Message with %s", "args")

        mock_logger.log.assert_called_once()
        args, kwargs = mock_logger.log.call_args
        assert "[trace_args]" in args[1]
        assert "Message with %s" in args[1]
        assert args[2] == "args"

        # Clean up
        set_trace_id(None)


class TestFormatTraceSummary:
    """Test trace summary formatting."""

    def test_format_trace_summary_basic(self):
        """Test basic trace summary formatting."""
        result = format_trace_summary("bot", "slack_message")

        assert result == "[bot] | slack_message | status=success"

    def test_format_trace_summary_with_duration(self):
        """Test trace summary with duration."""
        result = format_trace_summary("bot", "slack_message", duration_ms=150.5)

        assert result == "[bot] | slack_message | duration=150.5ms | status=success"

    def test_format_trace_summary_with_status(self):
        """Test trace summary with custom status."""
        result = format_trace_summary("agent-service", "agent_invoke", status="error")

        assert result == "[agent-service] | agent_invoke | status=error"

    def test_format_trace_summary_complete(self):
        """Test trace summary with all parameters."""
        result = format_trace_summary(
            "control-plane", "auth_check", duration_ms=25.3, status="timeout"
        )

        assert (
            result == "[control-plane] | auth_check | duration=25.3ms | status=timeout"
        )

    def test_format_trace_summary_zero_duration(self):
        """Test trace summary with zero duration."""
        result = format_trace_summary("bot", "cache_hit", duration_ms=0.0)

        assert result == "[bot] | cache_hit | duration=0.0ms | status=success"

    def test_format_trace_summary_large_duration(self):
        """Test trace summary with large duration."""
        result = format_trace_summary("bot", "slow_operation", duration_ms=5432.1)

        assert result == "[bot] | slow_operation | duration=5432.1ms | status=success"

    def test_format_trace_summary_different_services(self):
        """Test trace summary for different services."""
        services = ["bot", "agent-service", "control-plane", "tasks"]

        for service in services:
            result = format_trace_summary(service, "test_action")
            assert f"[{service}]" in result

    def test_format_trace_summary_different_statuses(self):
        """Test trace summary for different statuses."""
        statuses = ["success", "error", "timeout", "partial"]

        for status in statuses:
            result = format_trace_summary("bot", "action", status=status)
            assert f"status={status}" in result
