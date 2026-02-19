"""Integration tests for Control Plane API endpoints.

Tests verify exact HTTP status codes for unauthenticated requests, ensuring
auth enforcement and public endpoint behavior are correctly tested.
Authenticated happy-path tests live in dedicated test files (test_agents_api.py,
test_api_endpoints.py, test_service_accounts.py, etc.).
"""

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


@pytest.fixture
def unauthenticated_client(app):
    """Create a test client with no auth dependency overrides.

    Other test files use authenticated_client which sets dependency overrides
    on the session-scoped app and never clears them. This fixture temporarily
    clears those overrides to test actual unauthenticated behavior.
    """
    saved_overrides = dict(app.dependency_overrides)
    app.dependency_overrides.clear()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    app.dependency_overrides.update(saved_overrides)


class TestHealthEndpoints:
    """Test health check endpoints (public, no auth required)."""

    def test_health_endpoint(self, client):
        """Test GET /health returns 200 with status field."""
        response = client.get("/health")
        assert response.status_code == 200
        assert "status" in response.json()

    def test_ready_endpoint(self, client):
        """Test GET /ready returns 200 or 503 depending on dependency status."""
        response = client.get("/ready")
        # Legitimately variable: 200 if all deps healthy, 503 if not
        assert response.status_code in [200, 503]


class TestMetricsEndpoints:
    """Test metrics endpoints (public, no auth required)."""

    def test_metrics_endpoint(self, client):
        """Test GET /metrics returns Prometheus format."""
        response = client.get("/metrics")
        assert response.status_code == 200
        assert "text/plain" in response.headers.get("content-type", "")


class TestAgentsAPI:
    """Test agents API endpoints.

    /api/agents is a public endpoint for agent discovery (no auth required).
    """

    def test_list_agents_unauthenticated(self, client):
        """Test GET /api/agents returns 200 without auth (public endpoint)."""
        response = client.get("/api/agents")
        assert response.status_code == 200
        data = response.json()
        assert "agents" in data

    def test_get_agent_unauthenticated(self, client):
        """Test GET /api/agents/{name} returns 200 without auth (public endpoint)."""
        response = client.get("/api/agents/test-agent")
        assert response.status_code == 200


class TestUsersAPI:
    """Test users API endpoints (auth required)."""

    def test_list_users_unauthenticated(self, unauthenticated_client):
        """Test GET /api/users returns 401 without auth."""
        response = unauthenticated_client.get("/api/users")
        assert response.status_code == 401

    def test_get_current_user_unauthenticated(self, unauthenticated_client):
        """Test GET /api/users/me returns 401 without auth."""
        response = unauthenticated_client.get("/api/users/me")
        assert response.status_code == 401


class TestGroupsAPI:
    """Test groups API endpoints (auth required)."""

    def test_list_groups_unauthenticated(self, unauthenticated_client):
        """Test GET /api/groups returns 401 without auth."""
        response = unauthenticated_client.get("/api/groups")
        assert response.status_code == 401

    def test_create_group_unauthenticated(self, unauthenticated_client):
        """Test POST /api/groups returns 401 without auth."""
        response = unauthenticated_client.post(
            "/api/groups",
            json={"group_name": "test-group", "display_name": "Test Group"},
        )
        assert response.status_code == 401


class TestAuthAPI:
    """Test authentication API endpoints."""

    def test_logout_endpoint(self, client):
        """Test POST /auth/logout redirects to logged-out page.

        The logout endpoint is public (no auth required). It clears the session
        and redirects to /auth/logged-out which serves the logout HTML template.
        httpx TestClient follows redirects by default, so we get the final 200.
        """
        response = client.post("/auth/logout")
        assert response.status_code == 200

    def test_token_endpoint_unauthenticated(self, unauthenticated_client):
        """Test GET /auth/token returns 401 without session."""
        response = unauthenticated_client.get("/auth/token")
        assert response.status_code == 401


class TestCORS:
    """Test CORS headers."""

    def test_cors_headers_present_for_allowed_origin(self, client):
        """Test that CORS headers are set when Origin matches allowed origins."""
        response = client.get(
            "/health",
            headers={"Origin": "http://localhost:6001"},
        )
        assert response.status_code == 200
        assert (
            response.headers.get("access-control-allow-origin")
            == "http://localhost:6001"
        )

    def test_cors_preflight_request(self, client):
        """Test CORS preflight OPTIONS request for allowed origin."""
        response = client.options(
            "/api/agents",
            headers={
                "Origin": "http://localhost:6001",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Authorization",
            },
        )
        assert response.status_code == 200
        assert (
            response.headers.get("access-control-allow-origin")
            == "http://localhost:6001"
        )


class TestAPIDocumentation:
    """Test API documentation endpoints (public, no auth required)."""

    def test_openapi_json_available(self, client):
        """Test that OpenAPI schema is available."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert "paths" in data

    def test_docs_endpoint_available(self, client):
        """Test that Swagger UI docs are available."""
        response = client.get("/docs")
        assert response.status_code == 200
