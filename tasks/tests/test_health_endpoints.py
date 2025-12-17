"""Tests for health check endpoints.

These tests verify that health endpoints work correctly for Docker healthchecks.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock


@pytest.fixture
def client(monkeypatch):
    """Create test client for FastAPI app with test configuration."""
    import os

    # Set test database URLs to avoid MySQL connection
    monkeypatch.setenv("TASK_DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("DATA_DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv("SERVER_BASE_URL", "http://localhost:5001")

    from app import app

    # Mock scheduler_service on app.state to prevent startup errors
    mock_scheduler = Mock()
    mock_scheduler.scheduler = Mock()
    mock_scheduler.scheduler.running = True
    app.state.scheduler_service = mock_scheduler

    with TestClient(app) as test_client:
        yield test_client

    # Cleanup
    if hasattr(app.state, "scheduler_service"):
        delattr(app.state, "scheduler_service")


class TestHealthEndpoints:
    """Test health and readiness endpoints."""

    def test_health_endpoint_returns_200(self, client):
        """Test that /health returns 200 OK."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data is not None
        # Tasks health endpoint returns scheduler_running status
        assert "scheduler_running" in data

    def test_health_endpoint_structure(self, client):
        """Test that /health response has expected structure."""
        response = client.get("/health")
        data = response.json()

        # Should have scheduler_running field
        assert "scheduler_running" in data
        assert isinstance(data["scheduler_running"], bool)

    def test_health_endpoint_no_auth_required(self, client):
        """Test that /health doesn't require authentication."""
        # Don't provide any auth headers
        response = client.get("/health")
        # Health should always be accessible
        assert response.status_code == 200

    def test_health_endpoint_performance(self, client):
        """Test that /health responds quickly (< 1 second)."""
        import time

        start = time.time()
        response = client.get("/health")
        duration = time.time() - start

        assert response.status_code == 200
        assert duration < 1.0, f"Health check took {duration:.2f}s, should be < 1s"

    def test_ready_endpoint_if_exists(self, client):
        """Test /ready endpoint if it exists."""
        response = client.get("/ready")

        # May not exist, but if it does, should return 200 or 503
        if response.status_code != 404:
            assert response.status_code in [200, 503]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
