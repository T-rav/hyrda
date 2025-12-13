"""OpenTelemetry distributed tracing (swappable backend).

This module provides OpenTelemetry tracing with automatic span creation.
Backend can be swapped via environment variables:
- OTEL_EXPORTER_OTLP_ENDPOINT: Jaeger, Datadog, New Relic, etc.
- OTEL_SERVICE_NAME: Service name for traces

Supports:
- Local: Jaeger (default)
- Cloud: Datadog, New Relic, Honeycomb, AWS X-Ray, etc.
"""

import logging
import os
from contextlib import contextmanager
from typing import Any

logger = logging.getLogger(__name__)

# Try to import OpenTelemetry
try:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import SERVICE_NAME, Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    OTEL_AVAILABLE = True
except ImportError:
    logger.warning("OpenTelemetry not installed - distributed tracing disabled")
    OTEL_AVAILABLE = False
    trace = None  # type: ignore


class OpenTelemetryTracing:
    """OpenTelemetry tracing with swappable backends."""

    def __init__(self, service_name: str):
        """Initialize OpenTelemetry tracing.

        Args:
            service_name: Name of this service
        """
        self.service_name = service_name
        self.enabled = OTEL_AVAILABLE and self._should_enable()

        if not self.enabled:
            logger.info(f"OpenTelemetry tracing disabled for {service_name}")
            return

        # Get OTLP endpoint from environment
        # Default: Jaeger (localhost:4317)
        # Can override for Datadog, New Relic, etc.
        otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://jaeger:4317")

        # Create resource with service name
        resource = Resource(attributes={SERVICE_NAME: service_name})

        # Create tracer provider
        provider = TracerProvider(resource=resource)

        # Add OTLP exporter (works with Jaeger, Datadog, New Relic, etc.)
        otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

        # Set global tracer provider
        trace.set_tracer_provider(provider)

        # Get tracer for this service
        self.tracer = trace.get_tracer(service_name)

        logger.info(f"OpenTelemetry initialized: {service_name} -> {otlp_endpoint}")

    def _should_enable(self) -> bool:
        """Check if tracing should be enabled.

        Returns:
            True if tracing should be enabled
        """
        # Disable if explicitly set to false
        if os.getenv("OTEL_TRACES_ENABLED", "true").lower() == "false":
            return False

        return True

    @contextmanager
    def start_span(self, name: str, attributes: dict[str, Any] | None = None):
        """Create a span context manager.

        Args:
            name: Span name
            attributes: Optional span attributes

        Yields:
            Span context
        """
        if not self.enabled or not self.tracer:
            yield None
            return

        with self.tracer.start_as_current_span(name) as span:
            if attributes:
                for key, value in attributes.items():
                    span.set_attribute(key, str(value))
            yield span

    def get_trace_id(self) -> str | None:
        """Get current trace ID.

        Returns:
            Trace ID as hex string, or None if no active span
        """
        if not self.enabled or not trace:
            return None

        span = trace.get_current_span()
        if span and span.get_span_context().is_valid:
            return format(span.get_span_context().trace_id, "032x")
        return None


# Global instances (lazy initialized)
_tracers: dict[str, OpenTelemetryTracing] = {}


def get_tracer(service_name: str) -> OpenTelemetryTracing:
    """Get or create OpenTelemetry tracer for a service.

    Args:
        service_name: Service name

    Returns:
        OpenTelemetryTracing instance
    """
    if service_name not in _tracers:
        _tracers[service_name] = OpenTelemetryTracing(service_name)
    return _tracers[service_name]


def instrument_fastapi(app: Any, service_name: str) -> None:
    """Instrument FastAPI app with OpenTelemetry.

    Args:
        app: FastAPI application
        service_name: Service name for traces
    """
    if not OTEL_AVAILABLE:
        logger.warning("OpenTelemetry not available - skipping FastAPI instrumentation")
        return

    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        # Initialize tracer
        get_tracer(service_name)

        # Instrument FastAPI
        FastAPIInstrumentor.instrument_app(app)

        logger.info(f"FastAPI instrumented with OpenTelemetry: {service_name}")
    except Exception as e:
        logger.error(f"Failed to instrument FastAPI: {e}")


# Backend-specific configuration examples (via environment variables):
#
# Jaeger (local):
#   OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4317
#
# Datadog:
#   OTEL_EXPORTER_OTLP_ENDPOINT=https://trace-agent.datadoghq.com:4317
#   DD_API_KEY=your_key
#
# New Relic:
#   OTEL_EXPORTER_OTLP_ENDPOINT=https://otlp.nr-data.net:4317
#   OTEL_EXPORTER_OTLP_HEADERS=api-key=your_key
#
# Honeycomb:
#   OTEL_EXPORTER_OTLP_ENDPOINT=https://api.honeycomb.io:443
#   OTEL_EXPORTER_OTLP_HEADERS=x-honeycomb-team=your_key
#
# AWS X-Ray:
#   OTEL_EXPORTER_OTLP_ENDPOINT=http://xray-daemon:2000
#
# Disable tracing:
#   OTEL_TRACES_ENABLED=false
