"""Tests for health check API endpoints (api/health.py)."""

from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def app():
    """Create FastAPI app for testing."""
    from fastapi import FastAPI

    from api.health import router

    app = FastAPI()
    app.include_router(router)

    return app


@pytest.fixture
def client_with_scheduler(app):
    """Create test client with mock scheduler."""
    mock_scheduler_service = Mock()
    mock_scheduler = Mock()
    mock_scheduler.running = True
    mock_scheduler_service.scheduler = mock_scheduler

    app.state.scheduler_service = mock_scheduler_service

    return TestClient(app)


@pytest.fixture
def client_without_scheduler(app):
    """Create test client without scheduler."""
    app.state.scheduler_service = None
    return TestClient(app)


@pytest.fixture
def client_scheduler_not_running(app):
    """Create test client with stopped scheduler."""
    mock_scheduler_service = Mock()
    mock_scheduler = Mock()
    mock_scheduler.running = False
    mock_scheduler_service.scheduler = mock_scheduler

    app.state.scheduler_service = mock_scheduler_service

    return TestClient(app)


@pytest.fixture
def client_scheduler_missing(app):
    """Create test client with scheduler service but no scheduler object."""
    mock_scheduler_service = Mock()
    mock_scheduler_service.scheduler = None

    app.state.scheduler_service = mock_scheduler_service

    return TestClient(app)


class TestHealthCheckEndpoint:
    """Test GET /health endpoint."""

    def test_health_check_scheduler_running(self, client_with_scheduler):
        """Test health check when scheduler is running."""
        response = client_with_scheduler.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["scheduler_running"] is True

    def test_health_check_scheduler_not_running(self, client_scheduler_not_running):
        """Test health check when scheduler is stopped."""
        response = client_scheduler_not_running.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["scheduler_running"] is False

    def test_health_check_no_scheduler_service(self, client_without_scheduler):
        """Test health check when scheduler service is not initialized."""
        response = client_without_scheduler.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["scheduler_running"] is False

    def test_health_check_scheduler_object_missing(self, client_scheduler_missing):
        """Test health check when scheduler service exists but scheduler object is None."""
        response = client_scheduler_missing.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["scheduler_running"] is False

    def test_health_check_returns_json(self, client_with_scheduler):
        """Test that health check returns JSON response."""
        response = client_with_scheduler.get("/health")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"

    def test_health_check_response_structure(self, client_with_scheduler):
        """Test that health check response has correct structure."""
        response = client_with_scheduler.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert "scheduler_running" in data
        assert isinstance(data["scheduler_running"], bool)


class TestHealthCheckAPIEndpoint:
    """Test GET /api/health endpoint (alternative path)."""

    def test_api_health_check_scheduler_running(self, client_with_scheduler):
        """Test /api/health endpoint when scheduler is running."""
        response = client_with_scheduler.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        assert data["scheduler_running"] is True

    def test_api_health_check_scheduler_not_running(self, client_scheduler_not_running):
        """Test /api/health endpoint when scheduler is stopped."""
        response = client_scheduler_not_running.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        assert data["scheduler_running"] is False

    def test_api_health_check_no_scheduler_service(self, client_without_scheduler):
        """Test /api/health endpoint when scheduler service is not initialized."""
        response = client_without_scheduler.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        assert data["scheduler_running"] is False

    def test_api_health_check_same_as_health(self, client_with_scheduler):
        """Test that /api/health returns same result as /health."""
        health_response = client_with_scheduler.get("/health")
        api_health_response = client_with_scheduler.get("/api/health")

        assert health_response.status_code == api_health_response.status_code
        assert health_response.json() == api_health_response.json()

    def test_api_health_check_returns_json(self, client_with_scheduler):
        """Test that /api/health returns JSON response."""
        response = client_with_scheduler.get("/api/health")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"


class TestHealthCheckEdgeCases:
    """Test edge cases and error conditions."""

    def test_health_check_multiple_calls(self, client_with_scheduler):
        """Test multiple health check calls return consistent results."""
        responses = [client_with_scheduler.get("/health") for _ in range(5)]

        for response in responses:
            assert response.status_code == 200
            assert response.json()["scheduler_running"] is True

    def test_both_endpoints_multiple_calls(self, client_with_scheduler):
        """Test alternating between both health endpoints."""
        for _ in range(3):
            response1 = client_with_scheduler.get("/health")
            response2 = client_with_scheduler.get("/api/health")

            assert response1.json() == response2.json()
            assert response1.status_code == response2.status_code
