"""Pytest configuration and shared fixtures for RAG service tests."""

import pytest
from fastapi.testclient import TestClient
from prometheus_client import REGISTRY


@pytest.fixture(autouse=True)
def clear_prometheus_registry():
    """Clear Prometheus registry before each test to prevent pollution."""
    # Get all collectors
    collectors = list(REGISTRY._collector_to_names.keys())

    # Unregister all except default collectors (process, platform, gc)
    for collector in collectors:
        try:
            # Don't unregister default collectors
            if not any(name.startswith(('python_', 'process_', 'platform_'))
                      for name in REGISTRY._collector_to_names.get(collector, [])):
                REGISTRY.unregister(collector)
        except Exception:
            pass  # Collector already unregistered or is a default collector

    yield

    # Cleanup after test
    collectors = list(REGISTRY._collector_to_names.keys())
    for collector in collectors:
        try:
            if not any(name.startswith(('python_', 'process_', 'platform_'))
                      for name in REGISTRY._collector_to_names.get(collector, [])):
                REGISTRY.unregister(collector)
        except Exception:
            pass


@pytest.fixture(autouse=True)
def mock_env(monkeypatch):
    """Mock environment variables for all tests."""
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_MODEL", "gpt-4")
    monkeypatch.setenv("LLM_API_KEY", "test-api-key-for-testing")
    monkeypatch.setenv("VECTOR_PROVIDER", "qdrant")
    monkeypatch.setenv("VECTOR_HOST", "localhost")
    monkeypatch.setenv("VECTOR_PORT", "6333")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "openai")
    monkeypatch.setenv("EMBEDDING_MODEL", "text-embedding-3-small")


@pytest.fixture
def test_app():
    """Create test FastAPI application."""
    from app import app

    return app


@pytest.fixture
def test_client(test_app):
    """Create test client."""
    with TestClient(test_app) as client:
        yield client


@pytest.fixture
def mock_service_token():
    """Mock service token for testing."""
    return "test-service-token-12345"


@pytest.fixture
def auth_headers(mock_service_token):
    """Create authentication headers for testing."""
    return {
        "X-Service-Token": mock_service_token,
        "Content-Type": "application/json",
    }
