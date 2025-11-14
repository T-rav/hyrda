"""Tests for OAuth redirect URI configuration."""

import os
from unittest.mock import patch


class TestOAuthRedirectURI:
    """Test that OAuth redirect URI uses configurable server base URL."""

    def test_default_redirect_uri_uses_localhost(self):
        """Test that default redirect URI is localhost:5001."""
        from config.settings import TasksSettings

        settings = TasksSettings()
        assert settings.server_base_url == "http://localhost:5001"

        # Verify redirect URI construction
        redirect_uri = f"{settings.server_base_url}/api/gdrive/auth/callback"
        assert redirect_uri == "http://localhost:5001/api/gdrive/auth/callback"

    def test_custom_server_base_url_from_env(self):
        """Test that SERVER_BASE_URL can be overridden via environment variable."""
        with patch.dict(
            os.environ, {"SERVER_BASE_URL": "http://3.133.107.199:5001"}, clear=False
        ):
            from config.settings import TasksSettings

            settings = TasksSettings()
            assert settings.server_base_url == "http://3.133.107.199:5001"

            # Verify redirect URI construction
            redirect_uri = f"{settings.server_base_url}/api/gdrive/auth/callback"
            assert (
                redirect_uri == "http://3.133.107.199:5001/api/gdrive/auth/callback"
            )

    def test_redirect_uri_construction_logic(self):
        """Test the redirect URI construction logic used in endpoints."""
        from config.settings import TasksSettings

        # Simulate what the endpoint does
        with patch.dict(
            os.environ, {"SERVER_BASE_URL": "http://testserver:5001"}, clear=False
        ):
            settings = TasksSettings()
            redirect_uri = f"{settings.server_base_url}/api/gdrive/auth/callback"

            assert redirect_uri == "http://testserver:5001/api/gdrive/auth/callback"

    def test_production_server_url_example(self):
        """Test example production server URL configuration."""
        with patch.dict(
            os.environ, {"SERVER_BASE_URL": "http://3.133.107.199:5001"}, clear=False
        ):
            from config.settings import TasksSettings

            settings = TasksSettings()

            # This is what production should use
            assert settings.server_base_url == "http://3.133.107.199:5001"

            # Google will redirect to this URL after OAuth approval
            expected_callback = "http://3.133.107.199:5001/api/gdrive/auth/callback"
            actual_callback = f"{settings.server_base_url}/api/gdrive/auth/callback"

            assert actual_callback == expected_callback
