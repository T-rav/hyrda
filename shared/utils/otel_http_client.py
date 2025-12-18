"""OpenTelemetry-instrumented HTTP client for cross-service tracing.

Automatically propagates trace context across service boundaries.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Try to import OpenTelemetry
try:
    from opentelemetry import trace
    from opentelemetry.propagate import inject
    from opentelemetry.trace import Status, StatusCode

    OTEL_AVAILABLE = True
except ImportError:
    logger.warning("OpenTelemetry not installed - trace propagation disabled")
    OTEL_AVAILABLE = False
    trace = None  # type: ignore


def add_otel_headers(headers: dict[str, str]) -> dict[str, str]:
    """Add OpenTelemetry trace context to HTTP headers.

    This propagates the current trace context to downstream services,
    enabling end-to-end distributed tracing.

    Args:
        headers: Existing HTTP headers

    Returns:
        Headers with trace context injected
    """
    if not OTEL_AVAILABLE or not trace:
        return headers

    # Create mutable copy
    headers_copy = dict(headers)

    # Inject current trace context into headers
    # This adds traceparent/tracestate headers per W3C Trace Context spec
    inject(headers_copy)

    return headers_copy


def create_span(
    name: str,
    attributes: dict[str, Any] | None = None,
    span_kind: Any = None,
):
    """Create an OpenTelemetry span with optional attributes.

    Args:
        name: Span name (e.g., "http.client.request")
        attributes: Optional span attributes
        span_kind: Optional span kind (CLIENT, SERVER, INTERNAL, etc.)

    Returns:
        Context manager for span
    """
    if not OTEL_AVAILABLE or not trace:
        # Return no-op context manager
        from contextlib import nullcontext

        return nullcontext()

    tracer = trace.get_tracer(__name__)

    # Create span with attributes from the start
    span_attributes = {k: str(v) for k, v in attributes.items()} if attributes else None

    if span_kind is not None:
        return tracer.start_as_current_span(name, kind=span_kind, attributes=span_attributes)
    else:
        return tracer.start_as_current_span(name, attributes=span_attributes)


def record_exception(exception: Exception) -> None:
    """Record an exception in the current span.

    Args:
        exception: Exception to record
    """
    if not OTEL_AVAILABLE or not trace:
        return

    span = trace.get_current_span()
    if span and span.is_recording():
        span.record_exception(exception)
        span.set_status(Status(StatusCode.ERROR, str(exception)))


# Span kinds
try:
    from opentelemetry.trace import SpanKind

    SPAN_KIND_CLIENT = SpanKind.CLIENT
    SPAN_KIND_SERVER = SpanKind.SERVER
    SPAN_KIND_INTERNAL = SpanKind.INTERNAL
except ImportError:
    SPAN_KIND_CLIENT = None
    SPAN_KIND_SERVER = None
    SPAN_KIND_INTERNAL = None
