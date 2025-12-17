"""Tests for OAuth credential management API (api/credentials.py)."""

from datetime import UTC, datetime, timedelta
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def app():
    """Create FastAPI app for testing."""
    from fastapi import FastAPI

    from api.credentials import router

    app = FastAPI()
    app.include_router(router)

    return app


@pytest.fixture
def authenticated_client(app):
    """Create authenticated test client."""
    from dependencies.auth import get_current_user

    async def mock_get_current_user():
        return {"email": "test@test.com", "name": "Test User"}

    app.dependency_overrides[get_current_user] = mock_get_current_user

    return TestClient(app)


@pytest.fixture
def mock_credential_active():
    """Create mock credential that is active."""
    mock_cred = Mock()
    mock_cred.credential_id = "test-cred-1"
    mock_cred.credential_name = "Test Credential"
    mock_cred.provider = "google_drive"

    # Token expires in 7 days (active)
    expiry = datetime.now(UTC) + timedelta(days=7)
    mock_cred.token_metadata = {"expiry": expiry.isoformat()}
    mock_cred.to_dict.return_value = {
        "credential_id": "test-cred-1",
        "credential_name": "Test Credential",
        "provider": "google_drive",
        "token_metadata": {"expiry": expiry.isoformat()},
    }

    return mock_cred


@pytest.fixture
def mock_credential_expiring_soon():
    """Create mock credential expiring in 12 hours."""
    mock_cred = Mock()
    mock_cred.credential_id = "test-cred-2"
    mock_cred.credential_name = "Expiring Credential"
    mock_cred.provider = "google_drive"

    # Token expires in 12 hours
    expiry = datetime.now(UTC) + timedelta(hours=12)
    mock_cred.token_metadata = {"expiry": expiry.isoformat()}
    mock_cred.to_dict.return_value = {
        "credential_id": "test-cred-2",
        "credential_name": "Expiring Credential",
        "provider": "google_drive",
        "token_metadata": {"expiry": expiry.isoformat()},
    }

    return mock_cred


@pytest.fixture
def mock_credential_expired():
    """Create mock credential that has expired."""
    mock_cred = Mock()
    mock_cred.credential_id = "test-cred-3"
    mock_cred.credential_name = "Expired Credential"
    mock_cred.provider = "google_drive"

    # Token expired 1 day ago
    expiry = datetime.now(UTC) - timedelta(days=1)
    mock_cred.token_metadata = {"expiry": expiry.isoformat()}
    mock_cred.to_dict.return_value = {
        "credential_id": "test-cred-3",
        "credential_name": "Expired Credential",
        "provider": "google_drive",
        "token_metadata": {"expiry": expiry.isoformat()},
    }

    return mock_cred


@pytest.fixture
def mock_credential_no_expiry():
    """Create mock credential with no expiry info."""
    mock_cred = Mock()
    mock_cred.credential_id = "test-cred-4"
    mock_cred.credential_name = "No Expiry Credential"
    mock_cred.provider = "google_drive"
    mock_cred.token_metadata = {}  # No expiry
    mock_cred.to_dict.return_value = {
        "credential_id": "test-cred-4",
        "credential_name": "No Expiry Credential",
        "provider": "google_drive",
        "token_metadata": {},
    }

    return mock_cred


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

    def test_list_credentials_active(
        self, authenticated_client, mock_credential_active
    ):
        """Test listing active credential."""
        mock_session = Mock()
        mock_query = Mock()
        mock_query.all.return_value = [mock_credential_active]
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

    def test_list_credentials_expiring_soon(
        self, authenticated_client, mock_credential_expiring_soon
    ):
        """Test listing credential expiring soon."""
        mock_session = Mock()
        mock_query = Mock()
        mock_query.all.return_value = [mock_credential_expiring_soon]
        mock_session.query.return_value = mock_query

        with patch("api.credentials.get_db_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = mock_session

            response = authenticated_client.get("/api/credentials")

            assert response.status_code == 200
            data = response.json()
            cred = data["credentials"][0]
            assert cred["status"] == "expiring_soon"
            assert cred["status_message"] == "Token expires soon"

    def test_list_credentials_expired(
        self, authenticated_client, mock_credential_expired
    ):
        """Test listing expired credential."""
        mock_session = Mock()
        mock_query = Mock()
        mock_query.all.return_value = [mock_credential_expired]
        mock_session.query.return_value = mock_query

        with patch("api.credentials.get_db_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = mock_session

            response = authenticated_client.get("/api/credentials")

            assert response.status_code == 200
            data = response.json()
            cred = data["credentials"][0]
            assert cred["status"] == "expired"
            assert cred["status_message"] == "Token expired - refresh required"

    def test_list_credentials_no_expiry(
        self, authenticated_client, mock_credential_no_expiry
    ):
        """Test listing credential without expiry info."""
        mock_session = Mock()
        mock_query = Mock()
        mock_query.all.return_value = [mock_credential_no_expiry]
        mock_session.query.return_value = mock_query

        with patch("api.credentials.get_db_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = mock_session

            response = authenticated_client.get("/api/credentials")

            assert response.status_code == 200
            data = response.json()
            cred = data["credentials"][0]
            assert cred["status"] == "unknown"
            assert cred["status_message"] == "No expiry info"

    def test_list_credentials_multiple(
        self,
        authenticated_client,
        mock_credential_active,
        mock_credential_expired,
        mock_credential_expiring_soon,
    ):
        """Test listing multiple credentials with different statuses."""
        mock_session = Mock()
        mock_query = Mock()
        mock_query.all.return_value = [
            mock_credential_active,
            mock_credential_expired,
            mock_credential_expiring_soon,
        ]
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
