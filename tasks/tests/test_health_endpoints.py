"""Tests for health check endpoints.

These tests verify that health endpoints work correctly for Docker healthchecks.
"""

import pytest
from flask import Flask


@pytest.fixture
def client():
    """Create test client for Flask app."""
    from app import create_app

    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


class TestHealthEndpoints:
    """Test health and readiness endpoints."""

    def test_health_endpoint_returns_200(self, client):
        """Test that /health returns 200 OK."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.get_json()
        assert data is not None
        assert "status" in data
        assert data["status"] in ["healthy", "ok"]

    def test_health_endpoint_structure(self, client):
        """Test that /health response has expected structure."""
        response = client.get("/health")
        data = response.get_json()

        # Should have status field at minimum
        assert "status" in data

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
