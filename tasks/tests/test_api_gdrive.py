"""Comprehensive tests for Google Drive API endpoints (api/gdrive.py)."""

from unittest.mock import Mock, patch

import pytest


@pytest.fixture
def mock_oauth_env(monkeypatch):
    """Mock OAuth environment variables."""
    monkeypatch.setenv(
        "GOOGLE_OAUTH_CLIENT_ID", "test-client-id.apps.googleusercontent.com"
    )
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("ENVIRONMENT", "development")


class TestInitiateGDriveAuth:
    """Test POST /api/gdrive/auth/initiate endpoint."""

    @patch("api.gdrive.Flow")
    @patch("api.gdrive.get_settings")
    def test_initiate_auth_success(
        self, mock_get_settings, mock_flow_class, authenticated_client, mock_oauth_env
    ):
        """Test initiating Google Drive auth successfully."""
        # Mock settings
        mock_settings = Mock()
        mock_settings.server_base_url = "http://localhost:5001"
        mock_get_settings.return_value = mock_settings

        # Mock OAuth flow
        mock_flow = Mock()
        mock_flow.authorization_url.return_value = (
            "https://accounts.google.com/o/oauth2/auth?client_id=test",
            "test-state-123",
        )
        mock_flow_class.from_client_config.return_value = mock_flow

        response = authenticated_client.post(
            "/api/gdrive/auth/initiate",
            json={
                "task_id": "test-task-1",
                "credential_name": "Test GDrive Credential",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "authorization_url" in data
        assert "state" in data
        assert "credential_id" in data
        assert data["state"] == "test-state-123"

    def test_initiate_auth_missing_task_id(self, authenticated_client):
        """Test initiate auth fails without task_id."""
        response = authenticated_client.post(
            "/api/gdrive/auth/initiate", json={"credential_name": "Test Credential"}
        )

        assert response.status_code == 400
        assert "task_id is required" in response.json()["detail"]

    def test_initiate_auth_missing_credential_name(self, authenticated_client):
        """Test initiate auth fails without credential_name."""
        response = authenticated_client.post(
            "/api/gdrive/auth/initiate", json={"task_id": "test-task-1"}
        )

        assert response.status_code == 400
        assert "credential_name is required" in response.json()["detail"]

    def test_initiate_auth_credential_name_too_long(self, authenticated_client):
        """Test initiate auth fails with credential_name > 255 chars."""
        long_name = "A" * 256

        response = authenticated_client.post(
            "/api/gdrive/auth/initiate",
            json={"task_id": "test-task-1", "credential_name": long_name},
        )

        assert response.status_code == 400
        assert "255 characters or less" in response.json()["detail"]

    def test_initiate_auth_invalid_credential_name_characters(
        self, authenticated_client
    ):
        """Test initiate auth fails with invalid characters in credential_name."""
        response = authenticated_client.post(
            "/api/gdrive/auth/initiate",
            json={
                "task_id": "test-task-1",
                "credential_name": "Test<script>alert('xss')</script>",
            },
        )

        assert response.status_code == 400
        assert "invalid characters" in response.json()["detail"]

    def test_initiate_auth_valid_credential_name_special_chars(
        self, authenticated_client, mock_oauth_env
    ):
        """Test initiate auth allows valid special characters."""
        with (
            patch("api.gdrive.Flow") as mock_flow_class,
            patch("api.gdrive.get_settings") as mock_get_settings,
        ):
            mock_settings = Mock()
            mock_settings.server_base_url = "http://localhost:5001"
            mock_get_settings.return_value = mock_settings

            mock_flow = Mock()
            mock_flow.authorization_url.return_value = ("https://test.com", "state")
            mock_flow_class.from_client_config.return_value = mock_flow

            response = authenticated_client.post(
                "/api/gdrive/auth/initiate",
                json={
                    "task_id": "test-task-1",
                    "credential_name": "Test-Credential_123.prod",
                },
            )

            assert response.status_code == 200

    @patch("api.gdrive.get_settings")
    def test_initiate_auth_missing_oauth_config(
        self, mock_get_settings, authenticated_client, monkeypatch
    ):
        """Test initiate auth fails without OAuth configuration."""
        # Remove OAuth env vars
        monkeypatch.delenv("GOOGLE_OAUTH_CLIENT_ID", raising=False)
        monkeypatch.delenv("GOOGLE_OAUTH_CLIENT_SECRET", raising=False)

        mock_settings = Mock()
        mock_settings.server_base_url = "http://localhost:5001"
        mock_get_settings.return_value = mock_settings

        response = authenticated_client.post(
            "/api/gdrive/auth/initiate",
            json={"task_id": "test-task-1", "credential_name": "Test Credential"},
        )

        assert response.status_code == 500
        assert "not configured" in response.json()["detail"]

    @patch("api.gdrive.Flow")
    @patch("api.gdrive.get_settings")
    def test_initiate_auth_oauth_error(
        self, mock_get_settings, mock_flow_class, authenticated_client, mock_oauth_env
    ):
        """Test initiate auth handles OAuth errors."""
        mock_settings = Mock()
        mock_settings.server_base_url = "http://localhost:5001"
        mock_get_settings.return_value = mock_settings

        mock_flow_class.from_client_config.side_effect = Exception(
            "OAuth configuration error"
        )

        response = authenticated_client.post(
            "/api/gdrive/auth/initiate",
            json={"task_id": "test-task-1", "credential_name": "Test Credential"},
        )

        assert response.status_code == 500


class TestGDriveEndpointIntegration:
    """Integration tests for Google Drive OAuth flow."""

    @patch("api.gdrive.Flow")
    @patch("api.gdrive.get_settings")
    def test_full_oauth_flow_simulation(
        self, mock_get_settings, mock_flow_class, authenticated_client, mock_oauth_env
    ):
        """Test simulated full OAuth flow from initiate to callback."""
        # Mock settings
        mock_settings = Mock()
        mock_settings.server_base_url = "http://localhost:5001"
        mock_get_settings.return_value = mock_settings

        # Step 1: Initiate OAuth
        mock_flow = Mock()
        mock_flow.authorization_url.return_value = (
            "https://accounts.google.com/o/oauth2/auth?state=state-123",
            "state-123",
        )
        mock_flow_class.from_client_config.return_value = mock_flow

        init_response = authenticated_client.post(
            "/api/gdrive/auth/initiate",
            json={
                "task_id": "integration-test-task",
                "credential_name": "Integration Test Credential",
            },
        )

        assert init_response.status_code == 200
        assert "authorization_url" in init_response.json()
        assert "credential_id" in init_response.json()

        # Step 2: Verify session was set (would normally redirect to Google)
        # In real flow, user would authenticate with Google and redirect back
        # Here we just verify the initiate step worked
        credential_id = init_response.json()["credential_id"]
        assert credential_id is not None
