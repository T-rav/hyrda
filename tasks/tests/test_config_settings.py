"""Tests for configuration settings (config/settings.py)."""

import pytest
from pydantic import ValidationError

from config.settings import TasksSettings, get_settings


class TestTasksSettingsDefaults:
    """Test default configuration values."""

    def test_default_port(self, monkeypatch):
        """Test default port is 8081."""
        monkeypatch.delenv("FLASK_PORT", raising=False)
        settings = TasksSettings()
        assert settings.port == 8081

    def test_default_host(self, monkeypatch):
        """Test default host is 0.0.0.0."""
        monkeypatch.delenv("TASKS_HOST", raising=False)
        settings = TasksSettings()
        assert settings.host == "0.0.0.0"

    def test_default_server_base_url(self, monkeypatch):
        """Test default server base URL."""
        monkeypatch.delenv("SERVER_BASE_URL", raising=False)
        settings = TasksSettings()
        assert settings.server_base_url == "http://localhost:5001"

    def test_default_secret_key(self, monkeypatch):
        """Test default secret key in development."""
        monkeypatch.delenv("SECRET_KEY", raising=False)
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        settings = TasksSettings()
        assert settings.secret_key == "dev-secret-key-change-in-production"

    def test_default_task_database_url(self, monkeypatch):
        """Test default task database URL."""
        monkeypatch.delenv("TASK_DATABASE_URL", raising=False)
        settings = TasksSettings()
        assert "mysql" in settings.task_database_url
        assert "insightmesh_task" in settings.task_database_url

    def test_default_data_database_url(self, monkeypatch):
        """Test default data database URL."""
        monkeypatch.delenv("DATA_DATABASE_URL", raising=False)
        settings = TasksSettings()
        assert "mysql" in settings.data_database_url
        assert "insightmesh_data" in settings.data_database_url

    def test_default_slack_bot_api_url(self):
        """Test default Slack bot API URL."""
        settings = TasksSettings()
        assert settings.slack_bot_api_url == "http://localhost:8080"

    def test_default_portal_url(self):
        """Test default portal URL."""
        settings = TasksSettings()
        assert settings.portal_url == "https://portal.8thlight.com"

    def test_default_portal_email(self):
        """Test default portal email."""
        settings = TasksSettings()
        assert settings.portal_email == "bot@8thlight.com"

    def test_default_qdrant_host(self):
        """Test default Qdrant host."""
        settings = TasksSettings()
        assert settings.qdrant_host == "qdrant"

    def test_default_qdrant_port(self):
        """Test default Qdrant port."""
        settings = TasksSettings()
        assert settings.qdrant_port == 6333

    def test_default_scheduler_timezone(self):
        """Test default scheduler timezone."""
        settings = TasksSettings()
        assert settings.scheduler_timezone == "UTC"

    def test_default_scheduler_coalesce(self):
        """Test default scheduler coalesce setting."""
        settings = TasksSettings()
        assert settings.scheduler_job_defaults_coalesce is True

    def test_default_scheduler_max_instances(self):
        """Test default scheduler max instances."""
        settings = TasksSettings()
        assert settings.scheduler_job_defaults_max_instances == 1

    def test_default_scheduler_max_workers(self):
        """Test default scheduler thread pool max workers."""
        settings = TasksSettings()
        assert settings.scheduler_executors_thread_pool_max_workers == 20


class TestTasksSettingsEnvironmentVariables:
    """Test loading settings from environment variables."""

    def test_port_from_env(self, monkeypatch):
        """Test loading port from FLASK_PORT env var."""
        monkeypatch.setenv("FLASK_PORT", "9000")
        settings = TasksSettings()
        assert settings.port == 9000

    def test_host_from_env(self, monkeypatch):
        """Test loading host from TASKS_HOST env var."""
        monkeypatch.setenv("TASKS_HOST", "127.0.0.1")
        settings = TasksSettings()
        assert settings.host == "127.0.0.1"

    def test_server_base_url_from_env(self, monkeypatch):
        """Test loading server base URL from env var."""
        monkeypatch.setenv("SERVER_BASE_URL", "https://example.com")
        settings = TasksSettings()
        assert settings.server_base_url == "https://example.com"

    def test_secret_key_from_env(self, monkeypatch):
        """Test loading secret key from env var."""
        monkeypatch.setenv("SECRET_KEY", "custom-secret-key")
        settings = TasksSettings()
        assert settings.secret_key == "custom-secret-key"

    def test_task_database_url_from_env(self, monkeypatch):
        """Test loading task database URL from env var."""
        monkeypatch.setenv("TASK_DATABASE_URL", "postgresql://localhost/testdb")
        settings = TasksSettings()
        assert settings.task_database_url == "postgresql://localhost/testdb"

    def test_data_database_url_from_env(self, monkeypatch):
        """Test loading data database URL from env var."""
        monkeypatch.setenv("DATA_DATABASE_URL", "postgresql://localhost/datadb")
        settings = TasksSettings()
        assert settings.data_database_url == "postgresql://localhost/datadb"

    def test_slack_bot_api_url_from_env(self, monkeypatch):
        """Test loading Slack bot API URL from env var."""
        monkeypatch.setenv("SLACK_BOT_API_URL", "http://bot-api:9000")
        settings = TasksSettings()
        assert settings.slack_bot_api_url == "http://bot-api:9000"

    def test_slack_bot_api_key_from_env(self, monkeypatch):
        """Test loading Slack bot API key from env var."""
        monkeypatch.setenv("SLACK_BOT_API_KEY", "test-api-key")
        settings = TasksSettings()
        assert settings.slack_bot_api_key == "test-api-key"

    def test_slack_bot_token_from_env(self, monkeypatch):
        """Test loading Slack bot token from env var."""
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test-token")
        settings = TasksSettings()
        assert settings.slack_bot_token == "xoxb-test-token"

    def test_qdrant_host_from_env(self, monkeypatch):
        """Test loading Qdrant host from env var."""
        monkeypatch.setenv("QDRANT_HOST", "localhost")
        settings = TasksSettings()
        assert settings.qdrant_host == "localhost"

    def test_qdrant_port_from_env(self, monkeypatch):
        """Test loading Qdrant port from env var."""
        monkeypatch.setenv("QDRANT_PORT", "7000")
        settings = TasksSettings()
        assert settings.qdrant_port == 7000

    def test_scheduler_timezone_from_env(self, monkeypatch):
        """Test loading scheduler timezone from env var."""
        monkeypatch.setenv("SCHEDULER_TIMEZONE", "America/New_York")
        settings = TasksSettings()
        assert settings.scheduler_timezone == "America/New_York"


class TestSecretKeyValidation:
    """Test secret key validation in production."""

    def test_production_with_default_secret_key_fails(self, monkeypatch):
        """Test that production env with default secret key raises error."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("SECRET_KEY", "dev-secret-key-change-in-production")

        with pytest.raises(ValidationError) as exc_info:
            TasksSettings()

        assert "SECRET_KEY must be set to a secure value in production" in str(
            exc_info.value
        )

    def test_production_with_custom_secret_key_succeeds(self, monkeypatch):
        """Test that production env with custom secret key works."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("SECRET_KEY", "secure-production-key-12345")

        settings = TasksSettings()
        assert settings.secret_key == "secure-production-key-12345"

    def test_development_with_default_secret_key_succeeds(self, monkeypatch):
        """Test that development env allows default secret key."""
        monkeypatch.setenv("ENVIRONMENT", "development")
        monkeypatch.setenv("SECRET_KEY", "dev-secret-key-change-in-production")

        settings = TasksSettings()
        assert settings.secret_key == "dev-secret-key-change-in-production"

    def test_production_with_other_default_variants_fails(self, monkeypatch):
        """Test that all default key variants are rejected in production."""
        monkeypatch.setenv("ENVIRONMENT", "production")

        default_keys = [
            "dev-secret-key-change-in-production",
            "dev-secret-key-change-in-prod",
            "dev-secret-change-in-prod",
        ]

        for key in default_keys:
            monkeypatch.setenv("SECRET_KEY", key)
            with pytest.raises(ValidationError):
                TasksSettings()

    def test_no_environment_var_uses_development(self, monkeypatch):
        """Test that missing ENVIRONMENT defaults to development."""
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        monkeypatch.setenv("SECRET_KEY", "dev-secret-key-change-in-production")

        # Should not raise error (defaults to development)
        settings = TasksSettings()
        assert settings.secret_key == "dev-secret-key-change-in-production"


class TestGetSettings:
    """Test get_settings() function."""

    def test_get_settings_returns_instance(self):
        """Test that get_settings returns TasksSettings instance."""
        settings = get_settings()
        assert isinstance(settings, TasksSettings)

    def test_get_settings_with_env_vars(self, monkeypatch):
        """Test get_settings respects environment variables."""
        monkeypatch.setenv("FLASK_PORT", "9999")
        monkeypatch.setenv("SECRET_KEY", "test-secret")

        settings = get_settings()
        assert settings.port == 9999
        assert settings.secret_key == "test-secret"

    def test_get_settings_multiple_calls(self):
        """Test multiple calls to get_settings."""
        settings1 = get_settings()
        settings2 = get_settings()

        # Both should be valid instances
        assert isinstance(settings1, TasksSettings)
        assert isinstance(settings2, TasksSettings)


class TestOptionalFields:
    """Test optional configuration fields."""

    def test_optional_slack_bot_api_key_defaults_none(self):
        """Test that optional Slack bot API key defaults to None."""
        settings = TasksSettings()
        assert settings.slack_bot_api_key is None

    def test_optional_slack_bot_token_defaults_none(self):
        """Test that optional Slack bot token defaults to None."""
        settings = TasksSettings()
        assert settings.slack_bot_token is None

    def test_optional_slack_app_token_defaults_none(self):
        """Test that optional Slack app token defaults to None."""
        settings = TasksSettings()
        assert settings.slack_app_token is None

    def test_optional_google_credentials_path_defaults_none(self):
        """Test that optional Google credentials path defaults to None."""
        settings = TasksSettings()
        assert settings.google_credentials_path is None

    def test_optional_google_token_path_defaults_none(self):
        """Test that optional Google token path defaults to None."""
        settings = TasksSettings()
        assert settings.google_token_path is None

    def test_optional_metrics_api_url_defaults_none(self):
        """Test that optional metrics API URL defaults to None."""
        settings = TasksSettings()
        assert settings.metrics_api_url is None

    def test_optional_metrics_api_key_defaults_none(self):
        """Test that optional metrics API key defaults to None."""
        settings = TasksSettings()
        assert settings.metrics_api_key is None

    def test_optional_portal_secret_defaults_none(self):
        """Test that optional portal secret defaults to None."""
        settings = TasksSettings()
        assert settings.portal_secret is None


class TestExtraFieldsIgnored:
    """Test that extra fields in environment are ignored."""

    def test_unknown_env_vars_ignored(self, monkeypatch):
        """Test that unknown environment variables don't cause errors."""
        monkeypatch.setenv("UNKNOWN_VAR", "some-value")
        monkeypatch.setenv("ANOTHER_UNKNOWN", "another-value")

        # Should not raise error due to extra='ignore'
        settings = TasksSettings()
        assert isinstance(settings, TasksSettings)
