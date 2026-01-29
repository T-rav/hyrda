"""Test suite for Service Account API endpoints.

Tests CRUD operations, authentication, API key generation, rate limiting,
and revocation for external API integration service accounts.
"""

import bcrypt

# Import models for test assertions
from models.base import get_db_session
from models import ServiceAccount

# All fixtures are now in conftest.py


# Test: Create Service Account
def test_create_service_account_success(authenticated_client, service_account_builder):
    """Test creating a service account returns API key once."""
    # Arrange
    payload = service_account_builder().for_hubspot().build()

    # Act
    response = authenticated_client.post("/api/service-accounts", json=payload)

    # Assert
    assert response.status_code == 200
    data = response.json()

    # Check response contains API key
    assert "api_key" in data
    assert data["api_key"].startswith("sa_")
    assert len(data["api_key"]) > 40  # Should be sa_ + 32+ chars

    # Check other fields
    assert data["name"] == "HubSpot Production"
    assert data["description"] == "Integration with HubSpot CRM"
    assert data["scopes"] == "agents:read,agents:invoke"
    assert data["rate_limit"] == 500
    assert data["is_active"] is True
    assert data["is_revoked"] is False
    assert data["api_key_prefix"] == data["api_key"][:8]

    # Verify API key is hashed in database
    with get_db_session() as session:
        account = (
            session.query(ServiceAccount).filter_by(name="HubSpot Production").first()
        )
        assert account is not None
        assert bcrypt.checkpw(data["api_key"].encode(), account.api_key_hash.encode())


def test_create_service_account_duplicate_name(
    authenticated_client, service_account_builder
):
    """Test creating service account with duplicate name fails."""
    # Arrange
    payload = service_account_builder().named("Test Account").read_only().build()

    # Act - Create first account
    authenticated_client.post("/api/service-accounts", json=payload)

    # Act - Try to create duplicate
    response = authenticated_client.post("/api/service-accounts", json=payload)

    # Assert
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


def test_create_service_account_with_allowed_agents(
    authenticated_client, service_account_builder
):
    """Test creating service account with specific allowed agents."""
    # Arrange
    payload = (
        service_account_builder()
        .named("Limited Account")
        .invoke_only()
        .limited_to_agents(["profile_researcher", "meddic_coach"])
        .build()
    )

    # Act
    response = authenticated_client.post("/api/service-accounts", json=payload)

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert set(data["allowed_agents"]) == {"profile_researcher", "meddic_coach"}


def test_create_service_account_with_empty_agents_array(
    authenticated_client, service_account_builder
):
    """Test creating service account with empty agents array = no access."""
    # Arrange
    payload = (
        service_account_builder()
        .named("No Access Account")
        .invoke_only()
        .no_agent_access()
        .build()
    )

    # Act
    response = authenticated_client.post("/api/service-accounts", json=payload)

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["allowed_agents"] == []  # Should return empty array

    # Verify the model denies access to all agents
    with get_db_session() as session:
        account = (
            session.query(ServiceAccount).filter_by(name="No Access Account").first()
        )
        assert account is not None
        assert account.can_access_agent("profile_researcher") is False
        assert account.can_access_agent("any_agent") is False


def test_create_service_account_with_expiration(authenticated_client):
    """Test creating service account with expiration date."""
    from datetime import datetime, timezone, timedelta

    expires_at = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()

    response = authenticated_client.post(
        "/api/service-accounts",
        json={
            "name": "Temporary Account",
            "scopes": "agents:read",
            "expires_at": expires_at,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["expires_at"] is not None


# Test: List Service Accounts
def test_list_service_accounts_empty(authenticated_client):
    """Test listing service accounts when none exist."""
    response = authenticated_client.get("/api/service-accounts")
    assert response.status_code == 200
    assert response.json() == []


def test_list_service_accounts(authenticated_client, service_account_builder):
    """Test listing service accounts."""
    # Arrange - Create two accounts
    account1 = service_account_builder().named("Account 1").read_only().build()
    account2 = service_account_builder().named("Account 2").invoke_only().build()
    authenticated_client.post("/api/service-accounts", json=account1)
    authenticated_client.post("/api/service-accounts", json=account2)

    # Act
    response = authenticated_client.get("/api/service-accounts")

    # Assert
    assert response.status_code == 200
    accounts = response.json()
    assert len(accounts) == 2
    assert {a["name"] for a in accounts} == {"Account 1", "Account 2"}


def test_list_service_accounts_exclude_revoked(authenticated_client):
    """Test listing excludes revoked accounts by default."""
    # Create and revoke an account
    create_response = authenticated_client.post(
        "/api/service-accounts",
        json={"name": "Revoked Account", "scopes": "agents:read"},
    )
    account_id = create_response.json()["id"]

    authenticated_client.post(f"/api/service-accounts/{account_id}/revoke")

    # List should be empty (revoked excluded)
    response = authenticated_client.get("/api/service-accounts")
    assert response.status_code == 200
    assert response.json() == []

    # List with include_revoked should show it
    response = authenticated_client.get("/api/service-accounts?include_revoked=true")
    assert response.status_code == 200
    accounts = response.json()
    assert len(accounts) == 1
    assert accounts[0]["is_revoked"] is True


# Test: Get Service Account
def test_get_service_account(authenticated_client):
    """Test retrieving a specific service account."""
    create_response = authenticated_client.post(
        "/api/service-accounts",
        json={"name": "Get Test", "scopes": "agents:read"},
    )
    account_id = create_response.json()["id"]

    response = authenticated_client.get(f"/api/service-accounts/{account_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Get Test"


def test_get_service_account_not_found(authenticated_client):
    """Test retrieving non-existent service account."""
    response = authenticated_client.get("/api/service-accounts/99999")
    assert response.status_code == 404


# Test: Update Service Account
def test_update_service_account(authenticated_client):
    """Test updating service account settings."""
    create_response = authenticated_client.post(
        "/api/service-accounts",
        json={"name": "Update Test", "scopes": "agents:read", "rate_limit": 100},
    )
    account_id = create_response.json()["id"]

    # Update rate limit and description
    response = authenticated_client.patch(
        f"/api/service-accounts/{account_id}",
        json={"rate_limit": 1000, "description": "Updated description"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["rate_limit"] == 1000
    assert data["description"] == "Updated description"


def test_update_revoked_service_account_fails(authenticated_client):
    """Test updating revoked service account fails."""
    create_response = authenticated_client.post(
        "/api/service-accounts",
        json={"name": "Revoke Then Update", "scopes": "agents:read"},
    )
    account_id = create_response.json()["id"]

    # Revoke it
    authenticated_client.post(f"/api/service-accounts/{account_id}/revoke")

    # Try to update
    response = authenticated_client.patch(
        f"/api/service-accounts/{account_id}",
        json={"rate_limit": 500},
    )

    assert response.status_code == 400
    assert "revoked" in response.json()["detail"].lower()


# Test: Revoke Service Account
def test_revoke_service_account(authenticated_client):
    """Test revoking a service account."""
    create_response = authenticated_client.post(
        "/api/service-accounts",
        json={"name": "To Revoke", "scopes": "agents:read"},
    )
    account_id = create_response.json()["id"]

    response = authenticated_client.post(
        f"/api/service-accounts/{account_id}/revoke",
        params={"reason": "Security incident"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["is_revoked"] is True
    assert data["is_active"] is False
    assert data["revoked_at"] is not None
    assert data["revoked_by"] == "admin@8thlight.com"
    assert data["revoke_reason"] == "Security incident"


def test_revoke_already_revoked_fails(authenticated_client):
    """Test revoking already revoked account fails."""
    create_response = authenticated_client.post(
        "/api/service-accounts",
        json={"name": "Double Revoke", "scopes": "agents:read"},
    )
    account_id = create_response.json()["id"]

    # Revoke once
    authenticated_client.post(f"/api/service-accounts/{account_id}/revoke")

    # Try to revoke again
    response = authenticated_client.post(f"/api/service-accounts/{account_id}/revoke")

    assert response.status_code == 400
    assert "already revoked" in response.json()["detail"].lower()


# Test: Delete Service Account
def test_delete_service_account(authenticated_client):
    """Test permanently deleting a service account."""
    create_response = authenticated_client.post(
        "/api/service-accounts",
        json={"name": "To Delete", "scopes": "agents:read"},
    )
    account_id = create_response.json()["id"]

    response = authenticated_client.delete(f"/api/service-accounts/{account_id}")

    assert response.status_code == 200
    assert "deleted permanently" in response.json()["message"].lower()

    # Verify it's gone
    response = authenticated_client.get(f"/api/service-accounts/{account_id}")
    assert response.status_code == 404


# Test: Service Account Model Methods
def test_service_account_is_expired():
    """Test ServiceAccount.is_expired() method."""
    from datetime import datetime, timezone, timedelta

    with get_db_session() as session:
        # Create expired account
        expired_account = ServiceAccount(
            name="Expired",
            api_key_hash=bcrypt.hashpw(b"test", bcrypt.gensalt()).decode(),
            api_key_prefix="sa_test",
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        session.add(expired_account)
        session.commit()

        assert expired_account.is_expired() is True

        # Create non-expired account
        active_account = ServiceAccount(
            name="Active",
            api_key_hash=bcrypt.hashpw(b"test2", bcrypt.gensalt()).decode(),
            api_key_prefix="sa_test2",
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        session.add(active_account)
        session.commit()

        assert active_account.is_expired() is False


def test_service_account_can_access_agent():
    """Test ServiceAccount.can_access_agent() method."""
    import json

    with get_db_session() as session:
        # All agents allowed (NULL)
        account_all = ServiceAccount(
            name="All Access",
            api_key_hash=bcrypt.hashpw(b"test", bcrypt.gensalt()).decode(),
            api_key_prefix="sa_test",
            allowed_agents=None,
        )
        session.add(account_all)
        session.commit()

        assert account_all.can_access_agent("profile_researcher") is True
        assert account_all.can_access_agent("any_agent") is True

        # Specific agents only
        account_limited = ServiceAccount(
            name="Limited Access",
            api_key_hash=bcrypt.hashpw(b"test2", bcrypt.gensalt()).decode(),
            api_key_prefix="sa_test2",
            allowed_agents=json.dumps(["profile_researcher"]),
        )
        session.add(account_limited)
        session.commit()

        assert account_limited.can_access_agent("profile_researcher") is True
        assert account_limited.can_access_agent("other_agent") is False


def test_service_account_has_scope():
    """Test ServiceAccount.has_scope() method."""
    with get_db_session() as session:
        account = ServiceAccount(
            name="Scoped",
            api_key_hash=bcrypt.hashpw(b"test", bcrypt.gensalt()).decode(),
            api_key_prefix="sa_test",
            scopes="agents:read,agents:invoke",
        )
        session.add(account)
        session.commit()

        assert account.has_scope("agents:read") is True
        assert account.has_scope("agents:invoke") is True
        assert account.has_scope("agents:admin") is False


def test_generate_api_key_format():
    """Test API key generation format."""
    from models.service_account import generate_api_key

    api_key = generate_api_key()

    assert api_key.startswith("sa_")
    assert len(api_key) > 40  # sa_ + 32+ chars
    assert api_key[3].isalnum()  # After prefix should be alphanumeric


# Test: Admin-Only Access (should fail without admin auth)
def test_create_service_account_requires_admin(client, app):
    """Test that creating service account requires admin auth."""
    # Temporarily clear auth overrides to test unauthenticated access
    saved_overrides = app.dependency_overrides.copy()
    app.dependency_overrides.clear()

    try:
        response = client.post(
            "/api/service-accounts",
            json={"name": "Unauthorized", "scopes": "agents:read"},
        )

        # Should fail without admin authentication
        assert response.status_code in [401, 403]
    finally:
        # Restore overrides for other tests
        app.dependency_overrides = saved_overrides


# Test: Service Account Validation Endpoint
def test_validate_service_account_success(authenticated_client):
    """Test validating a service account API key."""
    # Create service account
    create_response = authenticated_client.post(
        "/api/service-accounts",
        json={
            "name": "Validation Test",
            "scopes": "agents:read,agents:invoke",
            "rate_limit": 100,
        },
    )
    assert create_response.status_code == 200
    api_key = create_response.json()["api_key"]

    # Validate the API key
    response = authenticated_client.post(
        "/api/service-accounts/validate",
        json={"api_key": api_key, "client_ip": "192.168.1.1"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Validation Test"
    assert data["scopes"] == "agents:read,agents:invoke"
    assert data["rate_limit"] == 100
    assert data["allowed_agents"] is None  # All agents allowed


def test_validate_service_account_invalid_key(authenticated_client):
    """Test validating an invalid API key."""
    response = authenticated_client.post(
        "/api/service-accounts/validate",
        json={"api_key": "sa_invalid_key_12345", "client_ip": "192.168.1.1"},
    )

    assert response.status_code == 401
    assert "Invalid API key" in response.json()["detail"]


def test_validate_service_account_revoked(authenticated_client):
    """Test validating a revoked API key."""
    # Create service account
    create_response = authenticated_client.post(
        "/api/service-accounts",
        json={"name": "Revoke Test", "scopes": "agents:invoke"},
    )
    api_key = create_response.json()["api_key"]
    account_id = create_response.json()["id"]

    # Revoke it
    authenticated_client.post(f"/api/service-accounts/{account_id}/revoke")

    # Try to validate
    response = authenticated_client.post(
        "/api/service-accounts/validate",
        json={"api_key": api_key, "client_ip": "192.168.1.1"},
    )

    assert response.status_code == 403
    assert "revoked" in response.json()["detail"].lower()


def test_validate_service_account_inactive(authenticated_client):
    """Test validating an inactive API key."""
    # Create service account
    create_response = authenticated_client.post(
        "/api/service-accounts",
        json={"name": "Inactive Test", "scopes": "agents:invoke"},
    )
    api_key = create_response.json()["api_key"]
    account_id = create_response.json()["id"]

    # Deactivate it
    authenticated_client.patch(
        f"/api/service-accounts/{account_id}",
        json={"is_active": False},
    )

    # Try to validate
    response = authenticated_client.post(
        "/api/service-accounts/validate",
        json={"api_key": api_key, "client_ip": "192.168.1.1"},
    )

    assert response.status_code == 403
    assert "inactive" in response.json()["detail"].lower()


def test_validate_service_account_expired(authenticated_client):
    """Test validating an expired API key."""
    from datetime import datetime, timezone, timedelta

    # Create service account with past expiration
    expires_at = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()

    create_response = authenticated_client.post(
        "/api/service-accounts",
        json={
            "name": "Expired Test",
            "scopes": "agents:invoke",
            "expires_at": expires_at,
        },
    )
    api_key = create_response.json()["api_key"]

    # Try to validate
    response = authenticated_client.post(
        "/api/service-accounts/validate",
        json={"api_key": api_key, "client_ip": "192.168.1.1"},
    )

    assert response.status_code == 403
    assert "expired" in response.json()["detail"].lower()


def test_validate_service_account_tracks_usage(authenticated_client):
    """Test that validation tracks usage stats."""
    # Create service account
    create_response = authenticated_client.post(
        "/api/service-accounts",
        json={"name": "Usage Test", "scopes": "agents:invoke"},
    )
    api_key = create_response.json()["api_key"]
    account_id = create_response.json()["id"]

    # Validate multiple times
    for i in range(3):
        response = authenticated_client.post(
            "/api/service-accounts/validate",
            json={"api_key": api_key, "client_ip": f"192.168.1.{i}"},
        )
        assert response.status_code == 200

    # Check usage stats
    get_response = authenticated_client.get(f"/api/service-accounts/{account_id}")
    data = get_response.json()

    assert data["total_requests"] >= 3
    assert data["last_used_at"] is not None
    assert data["last_request_ip"] is not None


def test_validate_service_account_with_allowed_agents(authenticated_client):
    """Test validation returns allowed_agents list."""
    # Create service account with specific allowed agents
    create_response = authenticated_client.post(
        "/api/service-accounts",
        json={
            "name": "Limited Test",
            "scopes": "agents:invoke",
            "allowed_agents": ["help", "profile_researcher"],
        },
    )
    api_key = create_response.json()["api_key"]

    # Validate
    response = authenticated_client.post(
        "/api/service-accounts/validate",
        json={"api_key": api_key, "client_ip": "192.168.1.1"},
    )

    assert response.status_code == 200
    data = response.json()
    assert set(data["allowed_agents"]) == {"help", "profile_researcher"}
