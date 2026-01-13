"""Pytest configuration for shared tests - enable tracing for OTel tests."""
import os

# Keep tracing ENABLED for shared tests since they test OTel utilities
# os.environ["OTEL_TRACES_ENABLED"] = "false"  # Commented out - shared tests need OTel
