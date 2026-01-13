"""Distributed tracing utilities for request correlation across services.

Provides correlation ID generation and propagation for tracing requests
across the entire system: Slack → Bot → Agent-Service → Control-Plane.

Correlation IDs allow you to:
- Track requests across service boundaries
- Debug issues by following the complete request flow
- Monitor end-to-end latency
- Generate request flow diagrams

Example Flow:
1. Slack message received → Generate trace_id
2. Bot processes message → Log with trace_id
3. Bot calls Agent-Service → Pass trace_id in X-Trace-Id header
4. Agent-Service processes → Log with same trace_id
5. All logs can be filtered by trace_id to see complete flow
"""

import logging
import uuid
from contextvars import ContextVar
from typing import Any

logger = logging.getLogger(__name__)

# Context variable to store trace ID for the current request
# This is thread-safe and async-safe
_trace_id_context: ContextVar[str | None] = ContextVar("trace_id", default=None)
_parent_trace_id_context: ContextVar[str | None] = ContextVar(
    "parent_trace_id", default=None
)


def generate_trace_id() -> str:
    """Generate a new unique trace ID.

    Returns:
        Trace ID in format: trace_XXXXXXXX (8 hex chars)

    Example:
        >>> trace_id = generate_trace_id()
        >>> print(trace_id)
        trace_a1b2c3d4
    """
    return f"trace_{uuid.uuid4().hex[:8]}"


def set_trace_id(trace_id: str | None) -> None:
    """Set the trace ID for the current request context.

    Args:
        trace_id: Trace ID to set (or None to clear)

    Example:
        >>> set_trace_id("trace_12345678")
        >>> logger.info("Processing request")  # Will include trace_id in logs
    """
    _trace_id_context.set(trace_id)


def get_trace_id() -> str | None:
    """Get the current trace ID from request context.

    Returns:
        Current trace ID or None if not set

    Example:
        >>> trace_id = get_trace_id()
        >>> if trace_id:
        ...     print(f"Current trace: {trace_id}")
    """
    return _trace_id_context.get()


def set_parent_trace_id(parent_trace_id: str | None) -> None:
    """Set the parent trace ID (for service-to-service calls).

    Args:
        parent_trace_id: Parent trace ID from calling service

    Example:
        >>> set_parent_trace_id("trace_87654321")
    """
    _parent_trace_id_context.set(parent_trace_id)


def get_parent_trace_id() -> str | None:
    """Get the parent trace ID.

    Returns:
        Parent trace ID or None if not set
    """
    return _parent_trace_id_context.get()


def get_or_create_trace_id() -> str:
    """Get current trace ID or create a new one if not set.

    Returns:
        Trace ID (existing or newly generated)

    Example:
        >>> trace_id = get_or_create_trace_id()
        >>> # Always returns a valid trace_id
    """
    trace_id = get_trace_id()
    if not trace_id:
        trace_id = generate_trace_id()
        set_trace_id(trace_id)
    return trace_id


def extract_trace_id_from_headers(headers: dict[str, str]) -> str | None:
    """Extract trace ID from HTTP headers.

    Checks for X-Trace-Id header (case-insensitive).

    Args:
        headers: HTTP headers dictionary

    Returns:
        Trace ID if found, None otherwise

    Example:
        >>> headers = {"X-Trace-Id": "trace_12345678"}
        >>> trace_id = extract_trace_id_from_headers(headers)
        >>> print(trace_id)
        trace_12345678
    """
    # Check various header name variations
    for key, value in headers.items():
        if key.lower() == "x-trace-id":
            return value
    return None


def add_trace_id_to_headers(
    headers: dict[str, str], trace_id: str | None = None
) -> dict[str, str]:
    """Add trace ID to HTTP headers for propagation.

    Args:
        headers: Existing headers dictionary
        trace_id: Trace ID to add (uses current context if not provided)

    Returns:
        Updated headers with X-Trace-Id

    Example:
        >>> headers = {"Content-Type": "application/json"}
        >>> headers = add_trace_id_to_headers(headers)
        >>> print(headers["X-Trace-Id"])
        trace_12345678
    """
    if trace_id is None:
        trace_id = get_or_create_trace_id()

    headers["X-Trace-Id"] = trace_id
    return headers


class TraceContext:
    """Context manager for request tracing.

    Automatically sets and clears trace ID for a block of code.

    Example:
        >>> with TraceContext("trace_12345678"):
        ...     logger.info("Processing")  # Logs include trace_id
        ...     # All logs in this block will have the trace_id
    """

    def __init__(self, trace_id: str | None = None, parent_trace_id: str | None = None):
        """Initialize trace context.

        Args:
            trace_id: Trace ID to set (generates new one if None)
            parent_trace_id: Parent trace ID for service-to-service calls
        """
        self.trace_id = trace_id or generate_trace_id()
        self.parent_trace_id = parent_trace_id
        self.previous_trace_id = None
        self.previous_parent_trace_id = None

    def __enter__(self):
        """Enter context - set trace ID."""
        self.previous_trace_id = get_trace_id()
        self.previous_parent_trace_id = get_parent_trace_id()

        set_trace_id(self.trace_id)
        if self.parent_trace_id:
            set_parent_trace_id(self.parent_trace_id)

        return self.trace_id

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context - restore previous trace ID."""
        set_trace_id(self.previous_trace_id)
        set_parent_trace_id(self.previous_parent_trace_id)


def get_trace_info() -> dict[str, Any]:
    """Get current trace information for logging.

    Returns:
        Dictionary with trace_id and parent_trace_id (if set)

    Example:
        >>> info = get_trace_info()
        >>> logger.info("Processing request", extra=info)
    """
    info = {}

    trace_id = get_trace_id()
    if trace_id:
        info["trace_id"] = trace_id

    parent_trace_id = get_parent_trace_id()
    if parent_trace_id:
        info["parent_trace_id"] = parent_trace_id

    return info


class TraceLogger:
    """Logger wrapper that automatically includes trace information.

    Example:
        >>> logger = TraceLogger(__name__)
        >>> with TraceContext("trace_12345678"):
        ...     logger.info("Processing request")
        ...     # Logs: [trace_12345678] Processing request
    """

    def __init__(self, logger_name: str):
        """Initialize trace logger.

        Args:
            logger_name: Name for the underlying logger
        """
        self.logger = logging.getLogger(logger_name)

    def _log_with_trace(self, level: int, msg: str, *args, **kwargs):
        """Log message with trace information."""
        trace_id = get_trace_id()
        parent_trace_id = get_parent_trace_id()

        # Add trace info to message
        if trace_id:
            if parent_trace_id:
                msg = f"[{trace_id}←{parent_trace_id}] {msg}"
            else:
                msg = f"[{trace_id}] {msg}"

        # Add trace info to extra for structured logging
        extra = kwargs.get("extra", {})
        extra.update(get_trace_info())
        kwargs["extra"] = extra

        self.logger.log(level, msg, *args, **kwargs)

    def debug(self, msg: str, *args, **kwargs):
        """Log debug message with trace info."""
        self._log_with_trace(logging.DEBUG, msg, *args, **kwargs)

    def info(self, msg: str, *args, **kwargs):
        """Log info message with trace info."""
        self._log_with_trace(logging.INFO, msg, *args, **kwargs)

    def warning(self, msg: str, *args, **kwargs):
        """Log warning message with trace info."""
        self._log_with_trace(logging.WARNING, msg, *args, **kwargs)

    def error(self, msg: str, *args, **kwargs):
        """Log error message with trace info."""
        self._log_with_trace(logging.ERROR, msg, *args, **kwargs)

    def critical(self, msg: str, *args, **kwargs):
        """Log critical message with trace info."""
        self._log_with_trace(logging.CRITICAL, msg, *args, **kwargs)


def format_trace_summary(
    service: str,
    action: str,
    duration_ms: float | None = None,
    status: str = "success",
) -> str:
    """Format a trace summary log message.

    Args:
        service: Service name (e.g., "bot", "agent-service")
        action: Action performed (e.g., "slack_message", "agent_invoke")
        duration_ms: Duration in milliseconds
        status: Status (success/error/timeout)

    Returns:
        Formatted trace summary string

    Example:
        >>> msg = format_trace_summary("bot", "slack_message", 150.5, "success")
        >>> print(msg)
        [bot] slack_message | duration=150.5ms | status=success
    """
    parts = [f"[{service}]", action]

    if duration_ms is not None:
        parts.append(f"duration={duration_ms:.1f}ms")

    parts.append(f"status={status}")

    return " | ".join(parts)
