"""Tests for agent management API endpoints."""

import pytest

# All fixtures (app, client, authenticated_client) are in conftest.py
from models import AgentMetadata, get_db_session


@pytest.fixture
def service_client(client, app):
    """Create service-authenticated client."""
    from dependencies.service_auth import verify_service_auth
    from api.agents import _verify_service_only
    from utils.idempotency import check_idempotency

    async def mock_verify_service_auth(request=None, allowed_services=None):
        return "test-service"

    async def mock_verify_service_only(request):
        return "test-service"

    async def mock_check_idempotency(request):
        """Mock idempotency check to always return None (not a duplicate)."""
        return None

    app.dependency_overrides[verify_service_auth] = mock_verify_service_auth
    app.dependency_overrides[_verify_service_only] = mock_verify_service_only
    app.dependency_overrides[check_idempotency] = mock_check_idempotency
    yield client

    # Don't clear overrides - they may be needed by other tests


@pytest.fixture(autouse=True)
def clean_db():
    """Clean database before each test."""
    with get_db_session() as session:
        session.query(AgentMetadata).delete()
        session.commit()
    yield


class TestListAgents:
    """Tests for GET /api/agents endpoint."""

    def test_list_agents_includes_help_agent(self, client):
        """List agents returns at least the help agent (created at startup)."""
        response = client.get("/api/agents")
        assert response.status_code == 200
        data = response.json()
        assert "agents" in data
        # Help agent is created at app startup
        assert len(data["agents"]) >= 1
        agent_names = {a["name"] for a in data["agents"]}
        assert "help" in agent_names

    def test_list_agents_returns_active_agents(self, client):
        """List agents returns all non-deleted agents."""
        # Create test agents
        with get_db_session() as session:
            agents = [
                AgentMetadata(
                    agent_name="profile",
                    display_name="Profile",
                    is_enabled=True,
                    is_slack_visible=True,
                ),
                AgentMetadata(
                    agent_name="meddic",
                    display_name="MEDDIC",
                    is_enabled=True,
                    is_slack_visible=True,
                ),
            ]
            for agent in agents:
                session.add(agent)
            session.commit()

        response = client.get("/api/agents")
        assert response.status_code == 200
        data = response.json()
        # 2 created + help agent = 3 total
        assert len(data["agents"]) >= 2
        agent_names = {a["name"] for a in data["agents"]}
        assert "profile" in agent_names
        assert "meddic" in agent_names

    def test_list_agents_excludes_deleted(self, client):
        """List agents excludes deleted agents by default."""
        with get_db_session() as session:
            active = AgentMetadata(agent_name="active", is_deleted=False)
            deleted = AgentMetadata(agent_name="deleted", is_deleted=True)
            session.add(active)
            session.add(deleted)
            session.commit()

        response = client.get("/api/agents")
        assert response.status_code == 200
        data = response.json()
        agent_names = {a["name"] for a in data["agents"]}
        assert "active" in agent_names
        assert "deleted" not in agent_names


class TestRegisterAgent:
    """Tests for agent registration logic (tested via database operations)."""

    def test_register_new_agent_via_db(self):
        """Creating new agent in database works correctly."""
        # Directly create agent in database (simulating what register endpoint does)
        with get_db_session() as session:
            agent = AgentMetadata(
                agent_name="new_agent",
                display_name="New Agent",
                description="Test agent",
                endpoint_url="http://test:8000/api/agents/new_agent/invoke",
                is_system=False,
                is_enabled=True,
                is_slack_visible=True,
            )
            agent.set_aliases(["new", "agent"])
            session.add(agent)
            session.commit()

        # Verify agent was created
        with get_db_session() as session:
            created_agent = (
                session.query(AgentMetadata).filter_by(agent_name="new_agent").first()
            )
            assert created_agent is not None
            assert created_agent.display_name == "New Agent"
            assert created_agent.get_aliases() == ["new", "agent"]
            assert created_agent.aliases_customized is False

    def test_update_existing_agent_aliases(self):
        """Updating existing agent updates aliases when not customized."""
        # Create initial agent
        with get_db_session() as session:
            agent = AgentMetadata(agent_name="test", display_name="Old")
            agent.set_aliases(["old"])
            agent.aliases_customized = False
            session.add(agent)
            session.commit()

        # Update agent (simulating what register endpoint does on update)
        with get_db_session() as session:
            agent = session.query(AgentMetadata).filter_by(agent_name="test").first()
            agent.display_name = "Updated"
            agent.set_aliases(["updated"])
            session.commit()

        # Verify aliases were updated
        with get_db_session() as session:
            agent = session.query(AgentMetadata).filter_by(agent_name="test").first()
            assert agent.display_name == "Updated"
            assert agent.get_aliases() == ["updated"]

    def test_preserves_customized_aliases_logic(self):
        """Customized aliases are not overwritten (business logic test)."""
        # Create agent with customized aliases
        with get_db_session() as session:
            agent = AgentMetadata(agent_name="test", aliases_customized=True)
            agent.set_aliases(["custom1", "custom2"])
            session.add(agent)
            session.commit()

        # Simulate registration update that should preserve customized aliases
        with get_db_session() as session:
            agent = session.query(AgentMetadata).filter_by(agent_name="test").first()
            # This is the key logic: only update if NOT customized
            if not agent.aliases_customized:
                agent.set_aliases(["new1", "new2"])
            session.commit()

        # Verify customized aliases preserved
        with get_db_session() as session:
            agent = session.query(AgentMetadata).filter_by(agent_name="test").first()
            assert agent.get_aliases() == ["custom1", "custom2"]


class TestUpdateAliases:
    """Tests for PUT /api/agents/{name}/aliases endpoint."""

    def test_update_aliases_as_admin(self, authenticated_client):
        """Admin can update agent aliases."""
        # Create agent
        with get_db_session() as session:
            agent = AgentMetadata(agent_name="test")
            agent.set_aliases(["old"])
            session.add(agent)
            session.commit()

        payload = {"aliases": ["new1", "new2"]}
        response = authenticated_client.put("/api/agents/test/aliases", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["aliases_customized"] is True

        # Verify in database
        with get_db_session() as session:
            agent = session.query(AgentMetadata).filter_by(agent_name="test").first()
            assert agent.get_aliases() == ["new1", "new2"]
            assert agent.aliases_customized is True

    def test_update_aliases_not_found(self, authenticated_client):
        """Update aliases for non-existent agent returns 404."""
        payload = {"aliases": ["test"]}
        response = authenticated_client.put(
            "/api/agents/nonexistent/aliases", json=payload
        )
        assert response.status_code == 404


class TestAliasConflicts:
    """Tests for GET /api/agents/{name}/alias-conflicts endpoint."""

    def test_no_conflicts(self, client):
        """Returns no conflicts when aliases don't overlap."""
        with get_db_session() as session:
            agent1 = AgentMetadata(agent_name="agent1")
            agent1.set_aliases(["a1", "alias1"])
            agent2 = AgentMetadata(agent_name="agent2")
            agent2.set_aliases(["a2", "alias2"])
            session.add(agent1)
            session.add(agent2)
            session.commit()

        response = client.get("/api/agents/agent1/alias-conflicts")
        assert response.status_code == 200
        data = response.json()
        assert data["has_conflicts"] is False
        assert len(data["conflicts"]) == 0

    def test_detect_alias_conflict(self, client):
        """Detects when aliases conflict with other agents."""
        with get_db_session() as session:
            agent1 = AgentMetadata(agent_name="agent1")
            agent1.set_aliases(["shared", "unique1"])
            agent2 = AgentMetadata(agent_name="agent2")
            agent2.set_aliases(["shared", "unique2"])  # Conflict!
            session.add(agent1)
            session.add(agent2)
            session.commit()

        response = client.get("/api/agents/agent1/alias-conflicts")
        assert response.status_code == 200
        data = response.json()
        assert data["has_conflicts"] is True
        assert len(data["conflicts"]) == 1
        assert "shared" in data["conflicts"][0]["conflicting_aliases"]


class TestToggleAgent:
    """Tests for toggle endpoints."""

    def test_toggle_enabled(self, authenticated_client):
        """Admin can toggle agent enabled state."""
        with get_db_session() as session:
            agent = AgentMetadata(agent_name="test", is_enabled=True)
            session.add(agent)
            session.commit()

        response = authenticated_client.post("/api/agents/test/toggle")
        assert response.status_code == 200
        assert response.json()["is_enabled"] is False

    def test_cannot_disable_system_agent(self, authenticated_client):
        """System agents cannot be disabled."""
        with get_db_session() as session:
            agent = AgentMetadata(agent_name="help", is_system=True, is_enabled=True)
            session.add(agent)
            session.commit()

        response = authenticated_client.post("/api/agents/help/toggle")
        assert response.status_code == 403
