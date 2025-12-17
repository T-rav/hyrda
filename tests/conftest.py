"""Pytest configuration for tasks service tests."""

import os

# Disable OpenTelemetry tracing during tests to prevent jaeger connection errors
os.environ["OTEL_TRACES_ENABLED"] = "false"
