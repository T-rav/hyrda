"""Tests for health check endpoints.

These tests verify that health endpoints work correctly and can be used
by Docker healthchecks and monitoring systems.
"""

import pytest
from fastapi.testclient import TestClient

from app import app


class TestHealthEndpoints:
    """Test health and readiness endpoints."""

    def test_health_endpoint_returns_200(self):
        """Test that /health returns 200 OK."""
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "healthy"

    def test_health_endpoint_structure(self):
        """Test that /health response has expected structure."""
        client = TestClient(app)
        response = client.get("/health")
        data = response.json()

        # Required fields
        assert "status" in data
        assert "timestamp" in data
        assert "service" in data

        # Service should be identified
        assert data["service"] == "control-plane"

    def test_ready_endpoint_exists(self):
        """Test that /ready endpoint exists."""
        client = TestClient(app)
        response = client.get("/ready")

        # Should return 200 or 503 depending on dependencies
        assert response.status_code in [200, 503]

    def test_metrics_endpoint_exists(self):
        """Test that /metrics endpoint exists for Prometheus."""
        client = TestClient(app)
        response = client.get("/metrics")
        assert response.status_code == 200

        # Should be Prometheus format (plain text)
        content_type = response.headers.get("content-type", "")
        assert "text/plain" in content_type or "text" in content_type

    def test_health_endpoint_no_auth_required(self):
        """Test that /health doesn't require authentication."""
        client = TestClient(app)
        # Don't provide any auth headers
        response = client.get("/health")
        # Health should always be accessible
        assert response.status_code == 200

    def test_health_endpoint_performance(self):
        """Test that /health responds quickly (< 1 second)."""
        import time

        client = TestClient(app)
        start = time.time()
        response = client.get("/health")
        duration = time.time() - start

        assert response.status_code == 200
        assert duration < 1.0, f"Health check took {duration:.2f}s, should be < 1s"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
