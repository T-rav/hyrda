"""Pytest configuration and shared fixtures for RAG service tests."""

import pytest
from fastapi.testclient import TestClient


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
