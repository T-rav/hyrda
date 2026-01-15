"""Tests for agent management API endpoints."""

import json
import pytest
from models import AgentMetadata, get_db_session


@pytest.fixture
def sample_agents(db_session):
    """Create sample agents for testing."""
    agents = [
        AgentMetadata(
            agent_name="profile",
            display_name="Company Profile",
            description="Generate company profiles",
            is_enabled=True,
            is_slack_visible=True,
            is_system=False,
            is_deleted=False,
        ),
        AgentMetadata(
            agent_name="meddic",
            display_name="MEDDIC Coach",
            description="Deal coaching",
            is_enabled=True,
            is_slack_visible=True,
            is_system=False,
            is_deleted=False,
        ),
        AgentMetadata(
            agent_name="help",
            display_name="Help Agent",
            description="List agents",
            is_enabled=True,
            is_slack_visible=True,
            is_system=True,  # System agent
            is_deleted=False,
        ),
    ]

    # Set aliases
    agents[0].set_aliases(["profile", "company profile"])
    agents[1].set_aliases(["meddic", "medic", "meddpicc"])
    agents[2].set_aliases(["help", "agents"])

    for agent in agents:
        db_session.add(agent)
    db_session.commit()

    return agents


class TestListAgents:
    """Tests for GET /api/agents endpoint."""

    def test_list_agents_returns_all_active(self, authenticated_client, sample_agents):
        """List agents should return all non-deleted agents."""
        response = authenticated_client.get("/api/agents")
        assert response.status_code == 200

        data = response.json()
        assert "agents" in data
        assert len(data["agents"]) == 3

        agent_names = {a["name"] for a in data["agents"]}
        assert "profile" in agent_names
        assert "meddic" in agent_names
        assert "help" in agent_names

    def test_list_agents_excludes_deleted_by_default(self, authenticated_client, db_session, sample_agents):
        """List agents should exclude deleted agents by default."""
        # Delete one agent
        agent = db_session.query(AgentMetadata).filter_by(agent_name="meddic").first()
        agent.is_deleted = True
        db_session.commit()

        response = authenticated_client.get("/api/agents")
        assert response.status_code == 200

        data = response.json()
        agent_names = {a["name"] for a in data["agents"]}
        assert "meddic" not in agent_names
        assert len(data["agents"]) == 2

    def test_list_agents_includes_deleted_when_requested(self, authenticated_client, db_session, sample_agents):
        """List agents with include_deleted=true should return deleted agents."""
        # Delete one agent
        agent = db_session.query(AgentMetadata).filter_by(agent_name="meddic").first()
        agent.is_deleted = True
        db_session.commit()

        response = authenticated_client.get("/api/agents?include_deleted=true")
        assert response.status_code == 200

        data = response.json()
        assert len(data["agents"]) == 3

        # Find deleted agent
        meddic = next(a for a in data["agents"] if a["name"] == "meddic")
        assert meddic["is_deleted"] is True


class TestRegisterAgent:
    """Tests for POST /api/agents/register endpoint."""

    def test_register_new_agent_with_aliases(self, service_authenticated_client):
        """Register new agent with aliases should create agent."""
        payload = {
            "name": "new_agent",
            "display_name": "New Agent",
            "description": "A new agent",
            "aliases": ["new", "agent", "new agent"],
            "is_system": False,
            "endpoint_url": "http://agent_service:8000/api/agents/new_agent/invoke",
        }

        response = service_authenticated_client.post(
            "/api/agents/register",
            json=payload,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert data["action"] == "created"

        # Verify in database
        with get_db_session() as session:
            agent = session.query(AgentMetadata).filter_by(agent_name="new_agent").first()
            assert agent is not None
            assert agent.get_aliases() == ["new", "agent", "new agent"]
            assert agent.aliases_customized is False

    def test_register_updates_existing_agent(self, service_authenticated_client, sample_agents):
        """Re-registering existing agent should update metadata."""
        payload = {
            "name": "profile",
            "display_name": "Updated Profile",
            "description": "Updated description",
            "aliases": ["profile", "updated"],
            "is_system": False,
            "endpoint_url": "http://agent_service:8000/api/agents/profile/invoke",
        }

        response = service_authenticated_client.post(
            "/api/agents/register",
            json=payload,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["action"] == "updated"

        # Verify aliases were updated
        with get_db_session() as session:
            agent = session.query(AgentMetadata).filter_by(agent_name="profile").first()
            assert agent.display_name == "Updated Profile"
            assert agent.get_aliases() == ["profile", "updated"]

    def test_register_preserves_customized_aliases(self, service_authenticated_client, db_session, sample_agents):
        """Re-registering should preserve admin-customized aliases."""
        # Mark aliases as customized
        agent = db_session.query(AgentMetadata).filter_by(agent_name="profile").first()
        agent.set_aliases(["custom1", "custom2"])
        agent.aliases_customized = True
        db_session.commit()

        payload = {
            "name": "profile",
            "display_name": "Updated Profile",
            "description": "Updated description",
            "aliases": ["profile", "new_default"],  # Try to overwrite
            "is_system": False,
            "endpoint_url": "http://agent_service:8000/api/agents/profile/invoke",
        }

        response = service_authenticated_client.post(
            "/api/agents/register",
            json=payload,
        )
        assert response.status_code == 200

        # Verify customized aliases were preserved
        with get_db_session() as session:
            agent = session.query(AgentMetadata).filter_by(agent_name="profile").first()
            assert agent.get_aliases() == ["custom1", "custom2"]  # Not overwritten
            assert agent.aliases_customized is True


class TestUpdateAliases:
    """Tests for PUT /api/agents/{name}/aliases endpoint."""

    def test_update_aliases_as_admin(self, admin_authenticated_client, sample_agents):
        """Admin can update agent aliases."""
        payload = {"aliases": ["new1", "new2", "new3"]}

        response = admin_authenticated_client.put(
            "/api/agents/profile/aliases",
            json=payload,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert data["aliases"] == ["new1", "new2", "new3"]
        assert data["aliases_customized"] is True

        # Verify in database
        with get_db_session() as session:
            agent = session.query(AgentMetadata).filter_by(agent_name="profile").first()
            assert agent.get_aliases() == ["new1", "new2", "new3"]
            assert agent.aliases_customized is True

    def test_update_aliases_non_admin_forbidden(self, authenticated_client, sample_agents):
        """Non-admin users cannot update aliases."""
        payload = {"aliases": ["new1", "new2"]}

        response = authenticated_client.put(
            "/api/agents/profile/aliases",
            json=payload,
        )
        assert response.status_code == 403

    def test_update_aliases_invalid_format(self, admin_authenticated_client, sample_agents):
        """Invalid alias format should be rejected."""
        # Test with special characters
        payload = {"aliases": ["valid", "invalid@alias", "also-valid"]}

        response = admin_authenticated_client.put(
            "/api/agents/profile/aliases",
            json=payload,
        )
        assert response.status_code == 400

    def test_update_aliases_not_a_list(self, admin_authenticated_client, sample_agents):
        """Aliases must be a list."""
        payload = {"aliases": "not-a-list"}

        response = admin_authenticated_client.put(
            "/api/agents/profile/aliases",
            json=payload,
        )
        assert response.status_code == 400


class TestAliasConflicts:
    """Tests for GET /api/agents/{name}/alias-conflicts endpoint."""

    def test_detect_alias_conflicts_with_other_agent(self, authenticated_client, db_session, sample_agents):
        """Should detect when aliases conflict with other agents."""
        # Create conflicting alias: profile uses "medic" (conflicts with meddic agent)
        agent = db_session.query(AgentMetadata).filter_by(agent_name="profile").first()
        agent.set_aliases(["profile", "medic"])  # "medic" is an alias of meddic agent
        db_session.commit()

        response = authenticated_client.get("/api/agents/profile/alias-conflicts")
        assert response.status_code == 200

        data = response.json()
        assert data["has_conflicts"] is True
        assert len(data["conflicts"]) == 1
        assert data["conflicts"][0]["conflicting_agent"] == "meddic"
        assert "medic" in data["conflicts"][0]["conflicting_aliases"]

    def test_detect_no_conflicts(self, authenticated_client, sample_agents):
        """Should return empty conflicts when no conflicts exist."""
        response = authenticated_client.get("/api/agents/profile/alias-conflicts")
        assert response.status_code == 200

        data = response.json()
        assert data["has_conflicts"] is False
        assert len(data["conflicts"]) == 0

    def test_detect_conflict_with_primary_name(self, authenticated_client, db_session, sample_agents):
        """Should detect when alias conflicts with another agent's primary name."""
        # profile agent uses "meddic" as alias (conflicts with meddic agent primary name)
        agent = db_session.query(AgentMetadata).filter_by(agent_name="profile").first()
        agent.set_aliases(["profile", "meddic"])
        db_session.commit()

        response = authenticated_client.get("/api/agents/profile/alias-conflicts")
        assert response.status_code == 200

        data = response.json()
        assert data["has_conflicts"] is True

        # Should have conflict with meddic primary name
        conflicts = data["conflicts"]
        assert any(c["conflict_type"] == "primary_name" for c in conflicts if "conflict_type" in c)


class TestToggleAgent:
    """Tests for POST /api/agents/{name}/toggle endpoints."""

    def test_toggle_agent_enabled(self, admin_authenticated_client, sample_agents):
        """Admin can toggle agent enabled state."""
        response = admin_authenticated_client.post("/api/agents/profile/toggle")
        assert response.status_code == 200

        data = response.json()
        assert data["is_enabled"] is False  # Was True, now False

        # Toggle back
        response = admin_authenticated_client.post("/api/agents/profile/toggle")
        assert response.status_code == 200
        assert response.json()["is_enabled"] is True

    def test_cannot_disable_system_agent(self, admin_authenticated_client, sample_agents):
        """System agents cannot be disabled."""
        response = admin_authenticated_client.post("/api/agents/help/toggle")
        assert response.status_code == 403

    def test_toggle_slack_visibility(self, admin_authenticated_client, sample_agents):
        """Admin can toggle Slack visibility."""
        response = admin_authenticated_client.post("/api/agents/profile/toggle-slack")
        assert response.status_code == 200

        data = response.json()
        assert data["is_slack_visible"] is False
        assert data["effective_in_slack"] is False


class TestDeleteAgent:
    """Tests for DELETE /api/agents/{name} endpoint."""

    def test_delete_agent_soft_deletes(self, admin_authenticated_client, db_session, sample_agents):
        """Delete should soft-delete (mark as deleted, not remove)."""
        response = admin_authenticated_client.delete("/api/agents/profile")
        assert response.status_code == 200

        # Verify soft delete
        with get_db_session() as session:
            agent = session.query(AgentMetadata).filter_by(agent_name="profile").first()
            assert agent is not None  # Still in database
            assert agent.is_deleted is True
            assert agent.is_enabled is False
            assert agent.is_slack_visible is False

    def test_cannot_delete_system_agent(self, admin_authenticated_client, sample_agents):
        """System agents cannot be deleted."""
        response = admin_authenticated_client.delete("/api/agents/help")
        assert response.status_code == 403


# Add fixture for service authentication (if not already exists)
@pytest.fixture
def service_authenticated_client(client):
    """Client with service-to-service authentication."""
    # Mock service token
    client.headers.update({"Authorization": "Bearer test-service-token"})
    return client
