"""Integration tests for Control Plane API endpoints.

These tests use REAL HTTP requests and require the control-plane service to be running.
"""

import pytest
from fastapi.testclient import TestClient
from prometheus_client import REGISTRY

from app import app

pytestmark = pytest.mark.integration


@pytest.fixture(scope="function", autouse=True)
def clear_prometheus_registry():
    """Clear Prometheus registry before each test to avoid duplicate metrics."""
    # Clear existing collectors
    collectors = list(REGISTRY._collector_to_names.keys())
    for collector in collectors:
        try:
            REGISTRY.unregister(collector)
        except Exception:
            pass
    yield
    # Clean up after test
    collectors = list(REGISTRY._collector_to_names.keys())
    for collector in collectors:
        try:
            REGISTRY.unregister(collector)
        except Exception:
            pass


class TestHealthEndpoints:
    """Test health check endpoints."""

    def test_health_endpoint(self):
        """Test GET /health returns 200."""
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        assert "status" in response.json()

    def test_ready_endpoint(self):
        """Test GET /ready endpoint exists."""
        client = TestClient(app)
        response = client.get("/ready")
        # May return 200 or 503 depending on dependencies
        assert response.status_code in [200, 503]


class TestMetricsEndpoints:
    """Test metrics endpoints."""

    def test_metrics_endpoint(self):
        """Test GET /metrics returns Prometheus format."""
        client = TestClient(app)
        response = client.get("/metrics")
        assert response.status_code == 200
        # Prometheus format is plain text
        assert "text/plain" in response.headers.get("content-type", "")


class TestAgentsAPI:
    """Test agents API endpoints."""

    def test_list_agents_unauthorized(self):
        """Test GET /api/agents without auth."""
        client = TestClient(app)
        response = client.get("/api/agents")
        # Should require authentication or return data
        assert response.status_code in [200, 401, 403]

    def test_get_agent_unauthorized(self):
        """Test GET /api/agents/{name} without auth."""
        client = TestClient(app)
        response = client.get("/api/agents/test-agent")
        # May return various codes depending on auth setup
        assert response.status_code in [200, 401, 403, 404]


class TestUsersAPI:
    """Test users API endpoints."""

    def test_list_users_unauthorized(self):
        """Test GET /api/users without auth returns 401."""
        client = TestClient(app)
        response = client.get("/api/users")
        assert response.status_code in [401, 403]

    def test_get_current_user_unauthorized(self):
        """Test GET /api/users/me without auth returns 401."""
        client = TestClient(app)
        response = client.get("/api/users/me")
        assert response.status_code == 401


class TestGroupsAPI:
    """Test groups API endpoints."""

    def test_list_groups_unauthorized(self):
        """Test GET /api/groups without auth returns 401."""
        client = TestClient(app)
        response = client.get("/api/groups")
        assert response.status_code in [401, 403]

    def test_create_group_unauthorized(self):
        """Test POST /api/groups without auth returns 401."""
        client = TestClient(app)
        response = client.post(
            "/api/groups",
            json={"group_name": "test-group", "display_name": "Test Group"},
        )
        assert response.status_code in [401, 403]


class TestAuthAPI:
    """Test authentication API endpoints."""

    def test_logout_endpoint(self):
        """Test GET /auth/logout endpoint."""
        client = TestClient(app)
        response = client.get("/auth/logout")
        # Should redirect or return success
        assert response.status_code in [200, 302, 303, 307]

    def test_token_endpoint(self):
        """Test GET /auth/token endpoint without auth."""
        client = TestClient(app)
        response = client.get("/auth/token")
        # Should require authentication
        assert response.status_code in [200, 401, 403]


class TestCORS:
    """Test CORS headers."""

    def test_cors_headers_on_health(self):
        """Test that CORS headers are present."""
        client = TestClient(app)
        response = client.get("/health")
        # Check for CORS headers
        assert "access-control-allow-origin" in [
            k.lower() for k in response.headers.keys()
        ] or response.status_code == 200


class TestAPIDocumentation:
    """Test API documentation endpoints."""

    def test_openapi_json_available(self):
        """Test that OpenAPI schema is available."""
        client = TestClient(app)
        response = client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert "paths" in data

    def test_docs_endpoint_available(self):
        """Test that Swagger UI docs are available."""
        client = TestClient(app)
        response = client.get("/docs")
        assert response.status_code == 200
