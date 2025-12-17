"""Pytest configuration - disable tracing during tests."""
import os
os.environ["OTEL_TRACES_ENABLED"] = "false"

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def reset_prometheus_registry():
    """Reset Prometheus registry between tests to avoid duplicate metric errors."""
    from prometheus_client import REGISTRY

    # Collect all collectors before test
    collectors_before = list(REGISTRY._collector_to_names.keys())

    yield

    # Clean up any new collectors added during test
    collectors_after = list(REGISTRY._collector_to_names.keys())
    for collector in collectors_after:
        if collector not in collectors_before:
            try:
                REGISTRY.unregister(collector)
            except Exception:
                pass  # Already unregistered or not in registry


@pytest.fixture
def client():
    """Provide a FastAPI test client for control-plane."""
    from app import app
    return TestClient(app)
