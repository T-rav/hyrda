"""
Integration Tests for Control Plane Groups API

Tests the API layer for:
- Authentication requirements
- Trace propagation

Mark: integration (run separately from unit tests)

Note: Validation tests requiring authenticated requests with database mocking
are tested in unit tests. This file focuses on API-level auth and tracing.
"""

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from app import create_app
from dependencies.auth import get_current_user
from utils.permissions import require_admin

# Mark all tests in this file as integration tests
pytestmark = pytest.mark.integration


@pytest.fixture
def app():
    """Create test app."""
    return create_app()


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def authenticated_client(app):
    """Create test client with auth bypassed for admin user.

    Overrides both get_current_user and require_admin to bypass auth.
    """
    mock_user = {
        "email": "admin@test.com",
        "name": "Test Admin",
        "is_admin": True,
        "picture": None,
    }

    # Mock must accept request parameter to match original signature
    async def mock_get_current_user(_request: Request):
        return mock_user

    async def mock_require_admin(_request: Request):
        return None  # Admin check passes

    app.dependency_overrides[get_current_user] = mock_get_current_user
    app.dependency_overrides[require_admin] = mock_require_admin
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


class TestGroupsAuthRequirements:
    """Test that groups API requires authentication."""

    def test_list_groups_requires_auth(self, client):
        """Test GET /api/groups requires authentication."""
        response = client.get("/api/groups")
        assert response.status_code in [401, 403]

    def test_create_group_requires_auth(self, client):
        """Test POST /api/groups requires authentication."""
        response = client.post(
            "/api/groups",
            json={"group_name": "new-group", "display_name": "New Group"},
        )
        assert response.status_code in [401, 403]

    def test_update_group_requires_auth(self, client):
        """Test PUT /api/groups/{name} requires authentication."""
        response = client.put(
            "/api/groups/test-group",
            json={"display_name": "Updated Name"},
        )
        assert response.status_code in [401, 403]

    def test_delete_group_requires_auth(self, client):
        """Test DELETE /api/groups/{name} requires authentication."""
        response = client.delete("/api/groups/test-group")
        assert response.status_code in [401, 403]

    def test_list_group_users_requires_auth(self, client):
        """Test GET /api/groups/{name}/users requires authentication."""
        response = client.get("/api/groups/test-group/users")
        assert response.status_code in [401, 403]

    def test_add_user_to_group_requires_auth(self, client):
        """Test POST /api/groups/{name}/users requires authentication."""
        response = client.post(
            "/api/groups/test-group/users",
            json={"user_email": "user@test.com"},
        )
        assert response.status_code in [401, 403]

    def test_list_group_agents_requires_auth(self, client):
        """Test GET /api/groups/{name}/agents requires authentication."""
        response = client.get("/api/groups/test-group/agents")
        assert response.status_code in [401, 403]

    def test_add_agent_to_group_requires_auth(self, client):
        """Test POST /api/groups/{name}/agents requires authentication."""
        response = client.post(
            "/api/groups/test-group/agents",
            json={"agent_name": "help"},
        )
        assert response.status_code in [401, 403]


class TestGroupsRequestValidation:
    """Test request validation for groups API."""

    def test_create_group_validates_missing_name(self, authenticated_client):
        """Test that group creation requires group_name."""
        response = authenticated_client.post(
            "/api/groups",
            json={"display_name": "No Name Group"},  # Missing group_name
        )
        # 400 from manual validation, 422 from Pydantic
        assert response.status_code in [400, 422]

    def test_create_group_validates_empty_name(self, authenticated_client):
        """Test that group creation rejects empty group_name."""
        response = authenticated_client.post(
            "/api/groups",
            json={"group_name": "", "display_name": "Empty Name"},
        )
        # Should fail validation or return error
        assert response.status_code in [400, 422, 500]

    def test_add_user_validates_missing_email(self, authenticated_client):
        """Test that adding user requires email or slack_id."""
        response = authenticated_client.post(
            "/api/groups/test-group/users",
            json={},  # Missing user identifier
        )
        assert response.status_code in [400, 422]

    def test_add_agent_validates_missing_name(self, authenticated_client):
        """Test that adding agent requires agent_name."""
        response = authenticated_client.post(
            "/api/groups/test-group/agents",
            json={},  # Missing agent_name
        )
        assert response.status_code in [400, 422]


class TestGroupsTracingHeaders:
    """Test trace propagation through Groups API."""

    def test_trace_id_returned_on_auth_error(self, client):
        """Test that X-Trace-Id is returned even on auth errors."""
        response = client.get("/api/groups")

        assert response.status_code in [401, 403]
        # Trace ID should be present due to TracingMiddleware
        assert "X-Trace-Id" in response.headers

    def test_incoming_trace_id_preserved_on_auth_error(self, client):
        """Test that incoming X-Trace-Id is preserved."""
        incoming_trace = "trace_groupsauth"

        response = client.get(
            "/api/groups",
            headers={"X-Trace-Id": incoming_trace},
        )

        assert response.status_code in [401, 403]
        assert response.headers.get("X-Trace-Id") == incoming_trace
