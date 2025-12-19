"""Isolated test for OpenTelemetry span attributes.

This test is isolated in its own file to avoid state pollution from other
OpenTelemetry tests, particularly TestAddOtelHeaders which sets up a
TracerProvider that interferes with span creation.
"""

import pytest

from shared.utils.otel_http_client import OTEL_AVAILABLE, create_span


@pytest.fixture(autouse=True)
def ensure_fresh_otel_state():
    """Ensure OpenTelemetry state is fresh for this test.

    This test must run with a clean TracerProvider to properly test
    span attribute passing.
    """
    if not OTEL_AVAILABLE:
        yield
        return

    from opentelemetry import trace

    # Reset before test
    try:
        if hasattr(trace, "_reset_trace"):
            trace._reset_trace()
    except Exception:
        pass

    yield


@pytest.mark.skipif(not OTEL_AVAILABLE, reason="OpenTelemetry not installed")
def test_create_span_attributes_passed_to_tracer():
    """Test that attributes are correctly passed to tracer when OTel is available."""
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )

    # Setup tracing with in-memory exporter
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    # Create span with attributes
    attributes = {"http.method": "GET", "http.url": "http://example.com"}
    with create_span("http.request", attributes=attributes):
        pass

    # Verify span was created with attributes
    spans = exporter.get_finished_spans()
    assert len(spans) > 0

    # Verify attributes were set (converted to strings)
    span_attributes = spans[0].attributes
    assert span_attributes.get("http.method") == "GET"
    assert span_attributes.get("http.url") == "http://example.com"
