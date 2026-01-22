"""Tests for OAuth credential management API (api/credentials.py).

Phase 1 refactoring: Removed duplicate fixtures (now in conftest.py)
and replaced credential fixtures with CredentialBuilder.
"""

from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

# Phase 1: Use builder pattern instead of individual fixtures
from tests.utils.builders import CredentialBuilder


@pytest.fixture
def app():
    """Create minimal FastAPI app for testing credentials router."""
    from fastapi import FastAPI

    from api.credentials import router

    app = FastAPI()
    app.include_router(router)

    return app


@pytest.fixture
def authenticated_client(app):
    """Create authenticated test client for credentials tests."""
    from dependencies.auth import get_current_user

    async def mock_get_current_user():
        return {"email": "test@test.com", "name": "Test User"}

    app.dependency_overrides[get_current_user] = mock_get_current_user

    return TestClient(app)


# Phase 1: Replaced 4 credential fixtures (78 lines) with builder pattern (0 lines)
# Old fixtures: mock_credential_active, mock_credential_expiring_soon,
#               mock_credential_expired, mock_credential_no_expiry
# New usage: CredentialBuilder.active().build()


class TestListCredentials:
    """Test GET /api/credentials endpoint."""

    def test_list_credentials_empty(self, authenticated_client):
        """Test listing credentials when none exist."""
        mock_session = Mock()
        mock_query = Mock()
        mock_query.all.return_value = []
        mock_session.query.return_value = mock_query

        with patch("api.credentials.get_db_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = mock_session

            response = authenticated_client.get("/api/credentials")

            assert response.status_code == 200
            data = response.json()
            assert data["credentials"] == []

    def test_list_credentials_active(self, authenticated_client):
        """Test listing active credential."""
        # Phase 1: Use CredentialBuilder instead of fixture
        mock_credential = CredentialBuilder.active().with_id("test-cred-1").build()

        mock_session = Mock()
        mock_query = Mock()
        mock_query.all.return_value = [mock_credential]
        mock_session.query.return_value = mock_query

        with patch("api.credentials.get_db_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = mock_session

            response = authenticated_client.get("/api/credentials")

            assert response.status_code == 200
            data = response.json()
            assert len(data["credentials"]) == 1
            cred = data["credentials"][0]
            assert cred["credential_id"] == "test-cred-1"
            assert cred["status"] == "active"
            assert cred["status_message"] == "Active"

    def test_list_credentials_expiring_soon(self, authenticated_client):
        """Test listing credential expiring soon."""
        # Phase 1: Use CredentialBuilder instead of fixture
        mock_credential = (
            CredentialBuilder.expiring()
            .with_id("test-cred-2")
            .with_name("Expiring Credential")
            .build()
        )

        mock_session = Mock()
        mock_query = Mock()
        mock_query.all.return_value = [mock_credential]
        mock_session.query.return_value = mock_query

        with patch("api.credentials.get_db_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = mock_session

            response = authenticated_client.get("/api/credentials")

            assert response.status_code == 200
            data = response.json()
            cred = data["credentials"][0]
            assert cred["status"] == "expiring_soon"
            assert cred["status_message"] == "Token expires soon"

    def test_list_credentials_expired(self, authenticated_client):
        """Test listing expired credential."""
        # Phase 1: Use CredentialBuilder instead of fixture
        mock_credential = (
            CredentialBuilder.dead()
            .with_id("test-cred-3")
            .with_name("Expired Credential")
            .build()
        )

        mock_session = Mock()
        mock_query = Mock()
        mock_query.all.return_value = [mock_credential]
        mock_session.query.return_value = mock_query

        with patch("api.credentials.get_db_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = mock_session

            response = authenticated_client.get("/api/credentials")

            assert response.status_code == 200
            data = response.json()
            cred = data["credentials"][0]
            assert cred["status"] == "expired"
            assert cred["status_message"] == "Token expired - refresh required"

    def test_list_credentials_no_expiry(self, authenticated_client):
        """Test listing credential without expiry info."""
        # Phase 1: Use CredentialBuilder instead of fixture
        mock_credential = (
            CredentialBuilder()
            .with_id("test-cred-4")
            .with_name("No Expiry Credential")
            .no_expiry()
            .build()
        )

        mock_session = Mock()
        mock_query = Mock()
        mock_query.all.return_value = [mock_credential]
        mock_session.query.return_value = mock_query

        with patch("api.credentials.get_db_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = mock_session

            response = authenticated_client.get("/api/credentials")

            assert response.status_code == 200
            data = response.json()
            cred = data["credentials"][0]
            assert cred["status"] == "unknown"
            assert cred["status_message"] == "No expiry info"

    def test_list_credentials_multiple(self, authenticated_client):
        """Test listing multiple credentials with different statuses."""
        # Phase 1: Use CredentialBuilder instead of fixtures
        mock_credentials = [
            CredentialBuilder.active().with_id("test-cred-1").build(),
            CredentialBuilder.dead().with_id("test-cred-3").build(),
            CredentialBuilder.expiring().with_id("test-cred-2").build(),
        ]

        mock_session = Mock()
        mock_query = Mock()
        mock_query.all.return_value = mock_credentials
        mock_session.query.return_value = mock_query

        with patch("api.credentials.get_db_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = mock_session

            response = authenticated_client.get("/api/credentials")

            assert response.status_code == 200
            data = response.json()
            assert len(data["credentials"]) == 3

            # Verify different statuses present
            statuses = [c["status"] for c in data["credentials"]]
            assert "active" in statuses
            assert "expired" in statuses
            assert "expiring_soon" in statuses

    def test_list_credentials_invalid_expiry_format(self, authenticated_client):
        """Test handling credential with invalid expiry format."""
        mock_cred = Mock()
        mock_cred.credential_id = "test-invalid"
        mock_cred.token_metadata = {"expiry": "invalid-date-format"}
        mock_cred.to_dict.return_value = {
            "credential_id": "test-invalid",
            "token_metadata": {"expiry": "invalid-date-format"},
        }

        mock_session = Mock()
        mock_query = Mock()
        mock_query.all.return_value = [mock_cred]
        mock_session.query.return_value = mock_query

        with patch("api.credentials.get_db_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = mock_session

            response = authenticated_client.get("/api/credentials")

            assert response.status_code == 200
            data = response.json()
            cred = data["credentials"][0]
            assert cred["status"] == "unknown"
            assert cred["status_message"] == "Status unknown"

    def test_list_credentials_database_error(self, authenticated_client):
        """Test handling database errors."""
        mock_session = Mock()
        mock_session.query.side_effect = Exception("Database connection failed")

        with patch("api.credentials.get_db_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = mock_session

            response = authenticated_client.get("/api/credentials")

            assert response.status_code == 500
            assert "Database connection failed" in response.json()["detail"]


class TestDeleteCredential:
    """Test DELETE /api/credentials/{cred_id} endpoint."""

    def test_delete_credential_success(self, authenticated_client):
        """Test successfully deleting a credential."""
        mock_cred = Mock()
        mock_cred.credential_id = "test-cred-1"
        mock_cred.credential_name = "Test Credential"

        mock_session = Mock()
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_cred
        mock_session.query.return_value = mock_query

        with patch("api.credentials.get_db_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = mock_session

            response = authenticated_client.delete("/api/credentials/test-cred-1")

            assert response.status_code == 200
            data = response.json()
            assert data["message"] == "Credential deleted successfully"

            # Verify delete was called
            mock_session.delete.assert_called_once_with(mock_cred)
            mock_session.commit.assert_called_once()

    def test_delete_credential_not_found(self, authenticated_client):
        """Test deleting non-existent credential."""
        mock_session = Mock()
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_session.query.return_value = mock_query

        with patch("api.credentials.get_db_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = mock_session

            response = authenticated_client.delete("/api/credentials/nonexistent")

            assert response.status_code == 404
            assert "Credential not found" in response.json()["detail"]

            # Verify delete was not called
            mock_session.delete.assert_not_called()

    def test_delete_credential_database_error(self, authenticated_client):
        """Test handling database errors during deletion."""
        mock_session = Mock()
        mock_session.query.side_effect = Exception("Database error")

        with patch("api.credentials.get_db_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = mock_session

            response = authenticated_client.delete("/api/credentials/test-cred-1")

            assert response.status_code == 500
            assert "Database error" in response.json()["detail"]

    def test_delete_credential_commit_error(self, authenticated_client):
        """Test handling commit errors."""
        mock_cred = Mock()
        mock_session = Mock()
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_cred
        mock_session.query.return_value = mock_query
        mock_session.commit.side_effect = Exception("Commit failed")

        with patch("api.credentials.get_db_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = mock_session

            response = authenticated_client.delete("/api/credentials/test-cred-1")

            assert response.status_code == 500
            assert "Commit failed" in response.json()["detail"]


class TestCredentialsAuthentication:
    """Test authentication requirements for credentials endpoints."""

    def test_list_credentials_requires_auth(self, app):
        """Test that listing credentials requires authentication."""
        # Client without auth override
        client = TestClient(app)

        response = client.get("/api/credentials")

        # Should get authentication error (503 if control-plane unavailable)
        assert response.status_code in [401, 403, 422, 503]

    def test_delete_credential_requires_auth(self, app):
        """Test that deleting credentials requires authentication."""
        # Client without auth override
        client = TestClient(app)

        response = client.delete("/api/credentials/test-cred")

        # Should get authentication error (503 if control-plane unavailable)
        assert response.status_code in [401, 403, 422, 503]
