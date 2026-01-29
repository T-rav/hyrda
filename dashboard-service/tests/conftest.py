"""Pytest configuration - disable tracing during tests."""

import os

os.environ["OTEL_TRACES_ENABLED"] = "false"
