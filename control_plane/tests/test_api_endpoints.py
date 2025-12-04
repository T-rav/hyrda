"""Test suite for Control Plane API endpoints."""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch
import pytest
from starlette.testclient import TestClient

# Create temporary file-based SQLite databases for tests
security_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
data_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
security_db_path = security_db_file.name
data_db_path = data_db_file.name
security_db_file.close()
data_db_file.close()

# Set up SQLite for tests BEFORE any imports
os.environ["SECURITY_DATABASE_URL"] = f"sqlite:///{security_db_path}"
os.environ["DATA_DATABASE_URL"] = f"sqlite:///{data_db_path}"

# Add control_plane to path BEFORE importing app
control_plane_dir = Path(__file__).parent.parent
if str(control_plane_dir) not in sys.path:
    sys.path.insert(0, str(control_plane_dir))

# Now import from control_plane - but create tables first
from models.base import Base
from models import (
    PermissionGroup,
    UserGroup,
    AgentGroupPermission,
    AgentMetadata,
    User,
    get_db_session,
)

# Create tables in SQLite BEFORE app initialization
with get_db_session() as session:
    Base.metadata.create_all(session.bind)


@pytest.fixture(scope="module")
def app():
    """Get FastAPI app for testing."""
    from app import create_app

    fastapi_app = create_app()
    yield fastapi_app


@pytest.fixture
def mock_oauth_env():
    """Mock OAuth environment variables."""
    with patch.dict(
        os.environ,
        {
            "GOOGLE_OAUTH_CLIENT_ID": "test-client-id.apps.googleusercontent.com",
            "GOOGLE_OAUTH_CLIENT_SECRET": "test-client-secret",
            "ALLOWED_EMAIL_DOMAIN": "@8thlight.com",
            "CONTROL_PLANE_BASE_URL": "http://localhost:6001",
        },
        clear=False,
    ):
        yield


@pytest.fixture
def client(app, mock_oauth_env):
    """Create test client with OAuth env mocked."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def authenticated_client(client, app):
    """Create authenticated test client with valid session and admin user."""
    from utils.permissions import get_current_user, require_admin

    # Create mock admin user (no database needed with dependency overrides)
    mock_admin = User(
        email="admin@8thlight.com",
        full_name="Test Admin",
        slack_user_id="U_ADMIN_TEST",
        is_admin=True,
    )

    # Mock authentication dependencies for FastAPI
    async def mock_get_current_user():
        return mock_admin

    async def mock_require_admin():
        return None

    app.dependency_overrides[get_current_user] = mock_get_current_user
    app.dependency_overrides[require_admin] = mock_require_admin

    yield client

    # Clean up overrides
    app.dependency_overrides.clear()


@pytest.fixture
def db_session():
    """Create test database session."""
    from models import get_db_session

    with get_db_session() as session:
        try:
            # Clean up test data (order matters for FK constraints)
            # Preserve system agent permissions
            session.query(AgentGroupPermission).filter(
                AgentGroupPermission.agent_name != "help"
            ).delete()
            session.query(UserGroup).delete()
            session.query(PermissionGroup).filter(
                PermissionGroup.group_name != "all_users"
            ).delete()
            session.query(AgentMetadata).filter(
                AgentMetadata.agent_name.like("%test%")
            ).delete()
            session.query(User).filter(User.slack_user_id.like("%TEST%")).delete()
            session.commit()
        except Exception:
            session.rollback()

        yield session

        try:
            # Cleanup after tests (order matters for FK constraints)
            session.rollback()  # Rollback any pending changes first
            # Preserve system agent permissions
            session.query(AgentGroupPermission).filter(
                AgentGroupPermission.agent_name != "help"
            ).delete()
            session.query(UserGroup).delete()
            session.query(PermissionGroup).filter(
                PermissionGroup.group_name != "all_users"
            ).delete()
            session.query(AgentMetadata).filter(
                AgentMetadata.agent_name.like("%test%")
            ).delete()
            session.query(User).filter(User.slack_user_id.like("%TEST%")).delete()
            session.commit()
        except Exception:
            session.rollback()


class TestGroupsAPI:
    """Test group management endpoints."""

    def test_list_groups(self, authenticated_client):
        """Test listing all groups."""
        response = authenticated_client.get("/api/groups")
        assert response.status_code == 200
        data = response.json()
        assert "groups" in data
        assert isinstance(data["groups"], list)

    def test_create_group(self, authenticated_client, db_session):
        """Test creating a new group."""
        response = authenticated_client.post(
            "/api/groups",
            json={
                "group_name": "test_group",
                "display_name": "Test Group",
                "description": "A test group",
                "created_by": "test_user",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "created"
        assert data["group_name"] == "test_group"

        # Verify in database
        group = (
            db_session.query(PermissionGroup)
            .filter(PermissionGroup.group_name == "test_group")
            .first()
        )
        assert group is not None
        assert group.display_name == "Test Group"
        assert group.description == "A test group"

    def test_update_group(self, authenticated_client, db_session):
        """Test updating group display name and description."""
        # Create test group
        group = PermissionGroup(
            group_name="update_test",
            display_name="Original Name",
            description="Original description",
            created_by="test",
        )
        db_session.add(group)
        db_session.commit()

        # Update group
        response = authenticated_client.put(
            "/api/groups/update_test",
            json={"display_name": "Updated Name", "description": "Updated description"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "updated"
        assert data["display_name"] == "Updated Name"
        assert data["description"] == "Updated description"

        # Verify in database
        db_session.expire_all()
        updated_group = (
            db_session.query(PermissionGroup)
            .filter(PermissionGroup.group_name == "update_test")
            .first()
        )
        assert updated_group.display_name == "Updated Name"
        assert updated_group.description == "Updated description"

    def test_delete_group(self, authenticated_client, db_session):
        """Test deleting a group."""
        # Create test group
        group = PermissionGroup(
            group_name="delete_test",
            display_name="Delete Test",
            description="To be deleted",
            created_by="test",
        )
        db_session.add(group)
        db_session.commit()

        # Delete group
        response = authenticated_client.delete("/api/groups/delete_test")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "deleted"

        # Verify deleted from database
        db_session.expire_all()
        deleted_group = (
            db_session.query(PermissionGroup)
            .filter(PermissionGroup.group_name == "delete_test")
            .first()
        )
        assert deleted_group is None

    def test_cannot_delete_system_group(self, authenticated_client):
        """Test that system groups cannot be deleted."""
        response = authenticated_client.delete("/api/groups/all_users")
        assert response.status_code == 403
        data = response.json()
        assert "Cannot delete system group" in data["detail"]


class TestGroupMembersAPI:
    """Test group membership endpoints."""

    def test_add_user_to_group(self, authenticated_client, db_session):
        """Test adding a user to a group."""
        # Create test group
        group = PermissionGroup(
            group_name="member_test", display_name="Member Test", created_by="test"
        )
        db_session.add(group)
        db_session.commit()

        # Create test user in separate transaction
        user = User(
            slack_user_id="U123TEST",
            full_name="Test User",
            email="test_member@example.com",
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()

        # Add user to group
        response = authenticated_client.post(
            "/api/groups/member_test/users",
            json={"user_id": "U123TEST", "added_by": "test"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "added"

        # Verify in database
        db_session.expire_all()
        membership = (
            db_session.query(UserGroup)
            .filter(
                UserGroup.group_name == "member_test",
                UserGroup.slack_user_id == "U123TEST",
            )
            .first()
        )
        assert membership is not None

    def test_remove_user_from_group(self, authenticated_client, db_session):
        """Test removing a user from a group."""
        # Create test group, user, and membership
        group = PermissionGroup(
            group_name="remove_test", display_name="Remove Test", created_by="test"
        )
        user = User(
            slack_user_id="U456TEST",
            full_name="Test User 2",
            email="test_remove@example.com",
            is_active=True,
        )
        membership = UserGroup(
            group_name="remove_test", slack_user_id="U456TEST", added_by="test"
        )
        db_session.add(group)
        db_session.add(user)
        db_session.add(membership)
        db_session.commit()

        # Remove user from group
        response = authenticated_client.delete(
            "/api/groups/remove_test/users?user_id=U456TEST"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "removed"

        # Verify removed from database
        db_session.expire_all()
        removed_membership = (
            db_session.query(UserGroup)
            .filter(
                UserGroup.group_name == "remove_test",
                UserGroup.slack_user_id == "U456TEST",
            )
            .first()
        )
        assert removed_membership is None

    def test_cannot_remove_from_system_group(self, authenticated_client, db_session):
        """Test that users cannot be manually removed from system groups."""
        response = authenticated_client.delete(
            "/api/groups/all_users/users?user_id=U123"
        )
        assert response.status_code == 403
        data = response.json()
        assert "Cannot manually remove" in data["detail"]


class TestAgentPermissionsAPI:
    """Test agent permission endpoints."""

    def test_grant_agent_to_group(self, authenticated_client, db_session):
        """Test granting agent access to a group."""
        # Create test group
        group = PermissionGroup(
            group_name="agent_test", display_name="Agent Test", created_by="test"
        )
        db_session.add(group)
        db_session.commit()

        # Grant agent to group
        response = authenticated_client.post(
            "/api/groups/agent_test/agents",
            json={"agent_name": "test_agent", "granted_by": "admin"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "granted"

        # Verify in database
        permission = (
            db_session.query(AgentGroupPermission)
            .filter(
                AgentGroupPermission.group_name == "agent_test",
                AgentGroupPermission.agent_name == "test_agent",
            )
            .first()
        )
        assert permission is not None
        assert permission.permission_type == "allow"

    def test_revoke_agent_from_group(self, authenticated_client, db_session):
        """Test revoking agent access from a group."""
        try:
            # Create test group
            group = PermissionGroup(
                group_name="revoke_test", display_name="Revoke Test", created_by="test"
            )
            db_session.add(group)
            db_session.commit()

            # Create permission in separate transaction
            permission = AgentGroupPermission(
                group_name="revoke_test",
                agent_name="revoke_agent",
                permission_type="allow",
                granted_by="admin",
            )
            db_session.add(permission)
            db_session.commit()

            # Revoke agent from group
            response = authenticated_client.delete(
                "/api/groups/revoke_test/agents?agent_name=revoke_agent"
            )
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "revoked"

            # Verify removed from database
            db_session.expire_all()
            removed_permission = (
                db_session.query(AgentGroupPermission)
                .filter(
                    AgentGroupPermission.group_name == "revoke_test",
                    AgentGroupPermission.agent_name == "revoke_agent",
                )
                .first()
            )
            assert removed_permission is None
        except Exception:
            db_session.rollback()
            raise

    def test_get_group_agents(self, authenticated_client, db_session):
        """Test getting agents a group has access to."""
        try:
            # Create test group
            group = PermissionGroup(
                group_name="list_agents_test",
                display_name="List Agents Test",
                created_by="test",
            )
            db_session.add(group)
            db_session.commit()

            # Create permissions in separate transactions
            perm1 = AgentGroupPermission(
                group_name="list_agents_test",
                agent_name="agent1",
                permission_type="allow",
                granted_by="admin",
            )
            db_session.add(perm1)
            db_session.commit()

            perm2 = AgentGroupPermission(
                group_name="list_agents_test",
                agent_name="agent2",
                permission_type="allow",
                granted_by="admin",
            )
            db_session.add(perm2)
            db_session.commit()

            # Get group agents
            response = authenticated_client.get("/api/groups/list_agents_test/agents")
            assert response.status_code == 200
            data = response.json()
            assert "agent_names" in data
            assert len(data["agent_names"]) == 2
            assert "agent1" in data["agent_names"]
            assert "agent2" in data["agent_names"]
        except Exception:
            db_session.rollback()
            raise


class TestAgentToggleAPI:
    """Test agent enable/disable endpoints."""

    def test_toggle_agent_enabled(self, authenticated_client, db_session):
        """Test toggling agent from disabled to enabled."""
        try:
            # Create disabled agent
            agent = AgentMetadata(agent_name="toggle_test_enabled", is_public=False)
            db_session.add(agent)
            db_session.commit()

            # Toggle to enabled
            response = authenticated_client.post(
                "/api/agents/toggle_test_enabled/toggle"
            )
            assert response.status_code == 200
            data = response.json()
            assert data["is_enabled"] is True

            # Verify in database
            db_session.expire_all()
            updated_agent = (
                db_session.query(AgentMetadata)
                .filter(AgentMetadata.agent_name == "toggle_test_enabled")
                .first()
            )
            assert updated_agent.is_public is True

            # Clean up
            db_session.delete(updated_agent)
            db_session.commit()
        except Exception:
            db_session.rollback()
            raise

    def test_toggle_creates_metadata_if_missing(self, authenticated_client, db_session):
        """Test that toggle creates metadata entry if it doesn't exist."""
        try:
            # Use a unique agent name to avoid conflicts
            test_agent_name = "new_agent_test_create"

            # Ensure no metadata exists
            existing = (
                db_session.query(AgentMetadata)
                .filter(AgentMetadata.agent_name == test_agent_name)
                .first()
            )
            if existing:
                db_session.delete(existing)
                db_session.commit()

            # Toggle (should create and enable)
            response = authenticated_client.post(
                f"/api/agents/{test_agent_name}/toggle"
            )
            assert response.status_code == 200
            data = response.json()
            assert data["is_enabled"] is True

            # Verify created in database with fresh session
            from models import get_db_session

            with get_db_session() as fresh_session:
                new_agent = (
                    fresh_session.query(AgentMetadata)
                    .filter(AgentMetadata.agent_name == test_agent_name)
                    .first()
                )
                assert new_agent is not None
                assert new_agent.is_public is True

                # Clean up
                fresh_session.delete(new_agent)
                fresh_session.commit()
        except Exception:
            db_session.rollback()
            raise


class TestSystemGroups:
    """Test system group behavior."""

    def test_all_users_group_exists(self, authenticated_client):
        """Test that 'All Users' system group is created on startup."""
        response = authenticated_client.get("/api/groups")
        assert response.status_code == 200
        data = response.json()

        all_users_group = next(
            (g for g in data["groups"] if g["group_name"] == "all_users"), None
        )
        assert all_users_group is not None
        assert all_users_group["display_name"] == "All Users"
        assert "automatically" in all_users_group["description"].lower()

    def test_system_group_protected_from_deletion(self, authenticated_client):
        """Test that system groups cannot be deleted."""
        response = authenticated_client.delete("/api/groups/all_users")
        assert response.status_code == 403
        data = response.json()
        assert "system group" in data["detail"].lower()

    def test_system_group_protected_from_manual_membership(self, authenticated_client):
        """Test that users cannot be manually removed from system groups."""
        response = authenticated_client.delete(
            "/api/groups/all_users/users?user_id=U123"
        )
        assert response.status_code == 403
        data = response.json()
        assert "system group" in data["detail"].lower()


class TestSystemAgents:
    """Test system agent behavior."""

    def test_help_agent_is_system(self, authenticated_client):
        """Test that help agent is marked as system agent."""
        response = authenticated_client.get("/api/agents/help")
        assert response.status_code == 200
        data = response.json()
        assert data["is_system"] is True
        assert data["is_public"] is True

    def test_help_agent_has_all_users_access(self, authenticated_client):
        """Test that help agent has all_users group access."""
        response = authenticated_client.get("/api/agents/help")
        assert response.status_code == 200
        data = response.json()
        assert "all_users" in data["authorized_group_names"]

    def test_cannot_disable_system_agent(self, authenticated_client):
        """Test that system agents cannot be disabled."""
        response = authenticated_client.post("/api/agents/help/toggle")
        assert response.status_code == 403
        data = response.json()
        assert "Cannot disable system agents" in data["detail"]

    def test_cannot_grant_system_agent_to_non_all_users(
        self, authenticated_client, db_session
    ):
        """Test that system agents can only be granted to all_users group."""
        # Create a test group
        from models import PermissionGroup

        group = PermissionGroup(
            group_name="test_group_system", display_name="Test Group", created_by="test"
        )
        db_session.add(group)
        db_session.commit()

        # Try to grant help agent to non-all_users group
        response = authenticated_client.post(
            "/api/groups/test_group_system/agents",
            json={"agent_name": "help", "granted_by": "admin"},
        )
        assert response.status_code == 403
        data = response.json()
        assert (
            "System agents can only be granted to 'all_users' group" in data["detail"]
        )

    def test_cannot_revoke_system_agent_from_all_users(self, authenticated_client):
        """Test that system agents cannot be revoked from all_users."""
        response = authenticated_client.delete(
            "/api/groups/all_users/agents?agent_name=help"
        )
        assert response.status_code == 403
        data = response.json()
        assert "Cannot revoke system agents from 'all_users' group" in data["detail"]


class TestAgentDeletionAPI:
    """Test agent soft delete endpoints."""

    def test_delete_agent_marks_as_deleted(self, authenticated_client, db_session):
        """Test that deleting an agent marks it as deleted."""
        # Create test agent
        agent = AgentMetadata(
            agent_name="delete_test_agent",
            display_name="Delete Test",
            is_public=True,
            is_deleted=False,
        )
        db_session.add(agent)
        db_session.commit()

        # Delete the agent
        response = authenticated_client.delete("/api/agents/delete_test_agent")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "deleted" in data["message"].lower()

        # Verify agent is marked as deleted in database
        db_session.expire_all()
        deleted_agent = (
            db_session.query(AgentMetadata)
            .filter(AgentMetadata.agent_name == "delete_test_agent")
            .first()
        )
        assert deleted_agent is not None
        assert deleted_agent.is_deleted is True
        assert deleted_agent.is_public is False

    def test_delete_nonexistent_agent_returns_404(self, authenticated_client):
        """Test that deleting a non-existent agent returns 404."""
        response = authenticated_client.delete("/api/agents/nonexistent_agent")
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"]["error"].lower()

    def test_cannot_delete_system_agent(self, authenticated_client):
        """Test that system agents cannot be deleted."""
        response = authenticated_client.delete("/api/agents/help")
        assert response.status_code == 403
        data = response.json()
        assert "system" in data["detail"]["error"].lower()

    def test_deleted_agent_excluded_from_list(self, authenticated_client, db_session):
        """Test that deleted agents are excluded from the agent list."""
        # Create and delete an agent
        agent = AgentMetadata(
            agent_name="list_test_agent",
            display_name="List Test",
            is_public=True,
            is_deleted=False,
        )
        db_session.add(agent)
        db_session.commit()

        # Delete it
        authenticated_client.delete("/api/agents/list_test_agent")

        # List agents - deleted agent should not appear
        response = authenticated_client.get("/api/agents")
        assert response.status_code == 200
        data = response.json()
        agent_names = [a["name"] for a in data["agents"]]
        assert "list_test_agent" not in agent_names

    def test_can_reregister_deleted_agent(self, authenticated_client, db_session):
        """Test that a deleted agent can be re-registered."""
        # Create and delete an agent
        agent = AgentMetadata(
            agent_name="reregister_test",
            display_name="Reregister Test",
            is_public=True,
            is_deleted=False,
        )
        db_session.add(agent)
        db_session.commit()

        # Delete it
        authenticated_client.delete("/api/agents/reregister_test")

        # Re-register the agent
        response = authenticated_client.post(
            "/api/agents/register",
            json={
                "name": "reregister_test",
                "display_name": "Reregistered",
                "description": "Reactivated agent",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["action"] == "reactivated"

        # Verify agent is active again
        db_session.expire_all()
        reactivated_agent = (
            db_session.query(AgentMetadata)
            .filter(AgentMetadata.agent_name == "reregister_test")
            .first()
        )
        assert reactivated_agent is not None
        assert reactivated_agent.is_deleted is False
        assert reactivated_agent.is_public is True
