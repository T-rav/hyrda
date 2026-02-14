"""Tests for HubSpot credential management API (api/hubspot.py)."""

from unittest.mock import Mock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def app():
    """Create minimal FastAPI app for testing HubSpot router."""
    from api.hubspot import router

    app = FastAPI()
    app.include_router(router)

    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


class TestCreateHubSpotCredential:
    """Test POST /api/hubspot/credentials endpoint."""

    def test_create_credential_success(self, client):
        """Test successfully creating a HubSpot credential."""
        mock_session = Mock()

        with (
            patch("api.hubspot.get_db_session") as mock_get_session,
            patch("api.hubspot.get_encryption_service") as mock_get_encryption,
        ):
            mock_get_session.return_value.__enter__.return_value = mock_session
            mock_encryption = Mock()
            mock_encryption.encrypt.return_value = "encrypted_token_data"
            mock_get_encryption.return_value = mock_encryption

            response = client.post(
                "/api/hubspot/credentials",
                json={
                    "credential_name": "Test HubSpot",
                    "access_token": "test-access-token",
                    "client_secret": "test-client-secret",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["credential_name"] == "Test HubSpot"
            assert data["provider"] == "hubspot"
            assert "credential_id" in data
            assert data["message"] == "HubSpot credentials stored successfully"

            # Verify credential was added to session
            mock_session.add.assert_called_once()
            mock_session.commit.assert_called_once()

    def test_create_credential_name_too_long(self, client):
        """Test creating credential with name exceeding 255 characters."""
        long_name = "a" * 256

        response = client.post(
            "/api/hubspot/credentials",
            json={
                "credential_name": long_name,
                "access_token": "test-token",
                "client_secret": "test-secret",
            },
        )

        assert response.status_code == 400
        assert "255 characters" in response.json()["detail"]

    def test_create_credential_invalid_name_characters(self, client):
        """Test creating credential with invalid characters in name."""
        response = client.post(
            "/api/hubspot/credentials",
            json={
                "credential_name": "Test<>HubSpot",
                "access_token": "test-token",
                "client_secret": "test-secret",
            },
        )

        assert response.status_code == 400
        assert "invalid characters" in response.json()["detail"]

    def test_create_credential_valid_name_with_special_chars(self, client):
        """Test creating credential with allowed special characters."""
        mock_session = Mock()

        with (
            patch("api.hubspot.get_db_session") as mock_get_session,
            patch("api.hubspot.get_encryption_service") as mock_get_encryption,
        ):
            mock_get_session.return_value.__enter__.return_value = mock_session
            mock_encryption = Mock()
            mock_encryption.encrypt.return_value = "encrypted_token_data"
            mock_get_encryption.return_value = mock_encryption

            response = client.post(
                "/api/hubspot/credentials",
                json={
                    "credential_name": "8th-Light_HubSpot.Prod",
                    "access_token": "test-token",
                    "client_secret": "test-secret",
                },
            )

            assert response.status_code == 200
            assert response.json()["credential_name"] == "8th-Light_HubSpot.Prod"

    def test_create_credential_database_error(self, client):
        """Test handling database errors during creation."""
        mock_session = Mock()
        mock_session.commit.side_effect = Exception("Database connection failed")

        with (
            patch("api.hubspot.get_db_session") as mock_get_session,
            patch("api.hubspot.get_encryption_service") as mock_get_encryption,
        ):
            mock_get_session.return_value.__enter__.return_value = mock_session
            mock_encryption = Mock()
            mock_encryption.encrypt.return_value = "encrypted"
            mock_get_encryption.return_value = mock_encryption

            response = client.post(
                "/api/hubspot/credentials",
                json={
                    "credential_name": "Test",
                    "access_token": "token",
                    "client_secret": "secret",
                },
            )

            assert response.status_code == 500
            assert "Failed to store credentials" in response.json()["detail"]

    def test_create_credential_missing_fields(self, client):
        """Test creating credential with missing required fields."""
        response = client.post(
            "/api/hubspot/credentials",
            json={
                "credential_name": "Test",
                # Missing access_token and client_secret
            },
        )

        assert response.status_code == 422  # Validation error


class TestListHubSpotCredentials:
    """Test GET /api/hubspot/credentials endpoint."""

    def test_list_credentials_empty(self, client):
        """Test listing credentials when none exist."""
        mock_session = Mock()
        mock_query = Mock()
        mock_query.filter.return_value.all.return_value = []
        mock_session.query.return_value = mock_query

        with patch("api.hubspot.get_db_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = mock_session

            response = client.get("/api/hubspot/credentials")

            assert response.status_code == 200
            assert response.json() == []

    def test_list_credentials_returns_hubspot_only(self, client):
        """Test listing returns only HubSpot credentials."""
        mock_cred = Mock()
        mock_cred.to_dict.return_value = {
            "credential_id": "test-id",
            "credential_name": "Test HubSpot",
            "provider": "hubspot",
            "created_at": "2024-01-01T00:00:00Z",
        }

        mock_session = Mock()
        mock_query = Mock()
        mock_query.filter.return_value.all.return_value = [mock_cred]
        mock_session.query.return_value = mock_query

        with patch("api.hubspot.get_db_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = mock_session

            response = client.get("/api/hubspot/credentials")

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["credential_name"] == "Test HubSpot"
            assert data[0]["provider"] == "hubspot"

    def test_list_credentials_multiple(self, client):
        """Test listing multiple HubSpot credentials."""
        mock_creds = []
        for i in range(3):
            mock_cred = Mock()
            mock_cred.to_dict.return_value = {
                "credential_id": f"test-id-{i}",
                "credential_name": f"HubSpot {i}",
                "provider": "hubspot",
            }
            mock_creds.append(mock_cred)

        mock_session = Mock()
        mock_query = Mock()
        mock_query.filter.return_value.all.return_value = mock_creds
        mock_session.query.return_value = mock_query

        with patch("api.hubspot.get_db_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = mock_session

            response = client.get("/api/hubspot/credentials")

            assert response.status_code == 200
            assert len(response.json()) == 3

    def test_list_credentials_database_error(self, client):
        """Test handling database errors."""
        mock_session = Mock()
        mock_session.query.side_effect = Exception("Database error")

        with patch("api.hubspot.get_db_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = mock_session

            response = client.get("/api/hubspot/credentials")

            assert response.status_code == 500


class TestDeleteHubSpotCredential:
    """Test DELETE /api/hubspot/credentials/{credential_id} endpoint."""

    def test_delete_credential_success(self, client):
        """Test successfully deleting a credential."""
        mock_cred = Mock()
        mock_cred.credential_id = "test-id"

        mock_session = Mock()
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_cred
        mock_session.query.return_value = mock_query

        with patch("api.hubspot.get_db_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = mock_session

            response = client.delete("/api/hubspot/credentials/test-id")

            assert response.status_code == 200
            assert response.json()["message"] == "Credential deleted successfully"
            mock_session.delete.assert_called_once_with(mock_cred)
            mock_session.commit.assert_called_once()

    def test_delete_credential_not_found(self, client):
        """Test deleting non-existent credential."""
        mock_session = Mock()
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_session.query.return_value = mock_query

        with patch("api.hubspot.get_db_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = mock_session

            response = client.delete("/api/hubspot/credentials/nonexistent")

            assert response.status_code == 404
            assert "Credential not found" in response.json()["detail"]
            mock_session.delete.assert_not_called()

    def test_delete_credential_database_error(self, client):
        """Test handling database errors during deletion."""
        mock_session = Mock()
        mock_session.query.side_effect = Exception("Database error")

        with patch("api.hubspot.get_db_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = mock_session

            response = client.delete("/api/hubspot/credentials/test-id")

            assert response.status_code == 500
