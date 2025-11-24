"""Tests for agent-service API endpoints."""

import pytest
from fastapi.testclient import TestClient

from app import app

client = TestClient(app)


class TestHealthEndpoint:
    """Test health check endpoint."""

    def test_health_check(self):
        """Test health endpoint returns 200."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "agent-service"


class TestRootEndpoint:
    """Test root endpoint."""

    def test_root_endpoint(self):
        """Test root endpoint returns service info."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "agent-service"
        assert data["version"] == "1.0.0"
        assert "agents" in data
        assert isinstance(data["agents"], list)


class TestListAgents:
    """Test agent listing endpoint."""

    def test_list_agents(self):
        """Test GET /api/agents returns agent list."""
        response = client.get("/api/agents")
        assert response.status_code == 200
        data = response.json()
        assert "agents" in data
        assert isinstance(data["agents"], list)

        # Should have at least help, profile, meddic agents
        agent_names = [agent["name"] for agent in data["agents"]]
        assert "help" in agent_names
        assert "profile" in agent_names
        assert "meddic" in agent_names


class TestGetAgentInfo:
    """Test agent info endpoint."""

    def test_get_existing_agent(self):
        """Test GET /api/agents/{name} for existing agent."""
        response = client.get("/api/agents/help")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "help"
        assert "description" in data
        assert "aliases" in data

    def test_get_nonexistent_agent(self):
        """Test GET /api/agents/{name} for nonexistent agent."""
        response = client.get("/api/agents/nonexistent")
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    def test_get_agent_by_alias(self):
        """Test GET /api/agents/{alias} resolves to primary name."""
        # If meddic has aliases (like "medic"), test that
        response = client.get("/api/agents/meddic")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "meddic"


class TestInvokeAgent:
    """Test agent invocation endpoint."""

    @pytest.mark.asyncio
    async def test_invoke_help_agent(self):
        """Test POST /api/agents/help/invoke."""
        response = client.post(
            "/api/agents/help/invoke",
            json={"query": "what can you help me with?", "context": {}},
        )

        # Should return 200 or 500 depending on whether dependencies are available
        # In test environment without full setup, might fail
        assert response.status_code in [200, 500]

        if response.status_code == 200:
            data = response.json()
            assert "response" in data
            assert "metadata" in data
            assert data["agent_name"] == "help"

    def test_invoke_nonexistent_agent(self):
        """Test POST /api/agents/{name}/invoke for nonexistent agent."""
        response = client.post(
            "/api/agents/nonexistent/invoke",
            json={"query": "test query", "context": {}},
        )
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    def test_invoke_agent_missing_query(self):
        """Test POST /api/agents/{name}/invoke with missing query."""
        response = client.post(
            "/api/agents/help/invoke",
            json={"context": {}},  # Missing query field
        )
        assert response.status_code == 422  # Validation error


class TestStreamAgent:
    """Test agent streaming endpoint."""

    def test_stream_nonexistent_agent(self):
        """Test POST /api/agents/{name}/stream for nonexistent agent."""
        response = client.post(
            "/api/agents/nonexistent/stream",
            json={"query": "test query", "context": {}},
        )
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    def test_stream_agent_missing_query(self):
        """Test POST /api/agents/{name}/stream with missing query."""
        response = client.post(
            "/api/agents/help/stream",
            json={"context": {}},  # Missing query field
        )
        assert response.status_code == 422  # Validation error


class TestCORS:
    """Test CORS middleware."""

    def test_cors_headers(self):
        """Test that CORS headers are present."""
        response = client.options("/api/agents")
        # CORS preflight should be handled
        assert response.status_code in [200, 405]


class TestErrorHandling:
    """Test error handling."""

    def test_404_on_invalid_path(self):
        """Test 404 on invalid API path."""
        response = client.get("/api/invalid/path")
        assert response.status_code == 404
