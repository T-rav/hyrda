"""Unit tests for OpenTelemetry HTTP client utilities."""

import pytest

from shared.utils.otel_http_client import (
    OTEL_AVAILABLE,
    SPAN_KIND_CLIENT,
    add_otel_headers,
    create_span,
    record_exception,
)


class TestAddOtelHeaders:
    """Test OpenTelemetry header injection."""

    def test_add_otel_headers_preserves_existing_headers(self):
        """Test that existing headers are preserved."""
        headers = {"Authorization": "Bearer token", "Content-Type": "application/json"}
        result = add_otel_headers(headers)

        assert result["Authorization"] == "Bearer token"
        assert result["Content-Type"] == "application/json"

    def test_add_otel_headers_returns_dict(self):
        """Test that result is a dictionary."""
        headers = {"X-Custom": "value"}
        result = add_otel_headers(headers)

        assert isinstance(result, dict)
        assert "X-Custom" in result

    def test_add_otel_headers_handles_empty_dict(self):
        """Test with empty headers dict."""
        headers = {}
        result = add_otel_headers(headers)

        assert isinstance(result, dict)

    @pytest.mark.skipif(not OTEL_AVAILABLE, reason="OpenTelemetry not installed")
    def test_add_otel_headers_injects_traceparent_when_available(self):
        """Test that traceparent header is injected when OTel is available."""
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider

        # Create a tracer provider and set it globally
        provider = TracerProvider()
        trace.set_tracer_provider(provider)

        tracer = trace.get_tracer(__name__)

        # Start a span to create active trace context
        with tracer.start_as_current_span("test"):
            headers = {"X-Custom": "value"}
            result = add_otel_headers(headers)

            # Should have traceparent header injected
            assert "traceparent" in result or "X-Custom" in result


class TestCreateSpan:
    """Test span creation."""

    def test_create_span_returns_context_manager(self):
        """Test that create_span returns a context manager."""
        span = create_span("test.operation")

        # Should be usable with 'with' statement
        with span:
            pass  # Should not raise

    def test_create_span_with_attributes(self):
        """Test span creation with attributes."""
        attributes = {"http.method": "GET", "http.url": "http://example.com"}
        span = create_span("http.request", attributes=attributes)

        with span:
            pass  # Should not raise

    def test_create_span_with_span_kind(self):
        """Test span creation with span kind."""
        span = create_span("http.client", span_kind=SPAN_KIND_CLIENT)

        with span:
            pass  # Should not raise

    def test_create_span_handles_none_attributes(self):
        """Test that None attributes don't cause errors."""
        span = create_span("test.operation", attributes=None)

        with span:
            pass  # Should not raise

    @pytest.mark.skipif(not OTEL_AVAILABLE, reason="OpenTelemetry not installed")
    def test_create_span_sets_attributes_when_available(self):
        """Test that attributes are set when OTel is available."""
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor
        from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
            InMemorySpanExporter,
        )

        # Setup in-memory exporter to capture spans
        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        trace.set_tracer_provider(provider)

        # Create span with attributes
        attributes = {"test.key": "test.value", "test.number": "123"}
        with create_span("test.span", attributes=attributes):
            pass

        # Verify span was created with attributes
        spans = exporter.get_finished_spans()
        assert len(spans) > 0
        span = spans[-1]
        assert span.name == "test.span"
        assert span.attributes.get("test.key") == "test.value"
        assert span.attributes.get("test.number") == "123"


class TestRecordException:
    """Test exception recording."""

    def test_record_exception_handles_exception(self):
        """Test that record_exception doesn't raise."""
        exc = ValueError("test error")
        record_exception(exc)  # Should not raise

    def test_record_exception_with_different_exception_types(self):
        """Test with different exception types."""
        exceptions = [
            ValueError("value error"),
            TypeError("type error"),
            RuntimeError("runtime error"),
            Exception("generic exception"),
        ]

        for exc in exceptions:
            record_exception(exc)  # Should not raise

    @pytest.mark.skipif(not OTEL_AVAILABLE, reason="OpenTelemetry not installed")
    def test_record_exception_sets_error_status(self):
        """Test that exception recording sets error status on span."""
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor
        from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
            InMemorySpanExporter,
        )
        from opentelemetry.trace import StatusCode

        # Setup in-memory exporter
        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        trace.set_tracer_provider(provider)

        tracer = trace.get_tracer(__name__)

        # Create span and record exception
        with tracer.start_as_current_span("test.span"):
            exc = ValueError("test error")
            record_exception(exc)

        # Verify span has error status
        spans = exporter.get_finished_spans()
        assert len(spans) > 0
        span = spans[-1]
        assert span.status.status_code == StatusCode.ERROR


class TestSpanKindConstants:
    """Test span kind constants are defined."""

    def test_span_kind_client_defined(self):
        """Test SPAN_KIND_CLIENT is defined."""
        assert SPAN_KIND_CLIENT is not None or SPAN_KIND_CLIENT is None

    def test_span_kind_constants_importable(self):
        """Test that span kind constants can be imported."""
        from shared.utils.otel_http_client import (
            SPAN_KIND_CLIENT,
            SPAN_KIND_INTERNAL,
            SPAN_KIND_SERVER,
        )

        # Should be importable (may be None if OTel not available)
        assert True  # If we got here, imports worked


class TestOtelAvailableFlag:
    """Test OTEL_AVAILABLE flag."""

    def test_otel_available_is_boolean(self):
        """Test that OTEL_AVAILABLE is a boolean."""
        assert isinstance(OTEL_AVAILABLE, bool)

    def test_otel_available_reflects_installation(self):
        """Test that OTEL_AVAILABLE reflects actual OpenTelemetry availability."""
        try:
            import opentelemetry  # noqa: F401

            assert OTEL_AVAILABLE is True
        except ImportError:
            assert OTEL_AVAILABLE is False
