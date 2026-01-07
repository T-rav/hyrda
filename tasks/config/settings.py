"""Configuration settings for the tasks service."""

import os

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class TasksSettings(BaseSettings):
    """Tasks service configuration."""

    model_config = SettingsConfigDict(env_ignore_empty=True, extra="ignore")

    # Server configuration
    port: int = Field(default=8081, alias="FLASK_PORT")
    host: str = Field(default="0.0.0.0", alias="TASKS_HOST")
    server_base_url: str = Field(
        default="http://localhost:5001",
        alias="SERVER_BASE_URL",
        description="Public base URL for OAuth redirects (e.g., http://3.133.107.199:5001)",
    )
    secret_key: str = Field(
        default="dev-secret-key-change-in-production", alias="SECRET_KEY"
    )
    flask_env: str = Field(default="production", alias="FLASK_ENV")

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key_in_production(cls, v: str) -> str:
        """Validate that SECRET_KEY is not default value in production."""
        environment = os.getenv("ENVIRONMENT")
        # Only enforce in production - if ENVIRONMENT not set, assume development
        if environment != "production":
            return v

        # Check for various default/placeholder values
        default_patterns = [
            "dev-secret",
            "change-in-production",
            "change-in-prod",
            "test-secret",
            "your-secret-here",
        ]
        is_default_key = any(pattern in v.lower() for pattern in default_patterns)

        if is_default_key:
            raise ValueError(
                "SECRET_KEY must be set to a secure value in production. "
                "Current value appears to be a default/placeholder key."
            )

        return v

    # Database configuration
    task_database_url: str = Field(
        default="mysql+pymysql://insightmesh_tasks:insightmesh_tasks_password@mysql:3306/insightmesh_task",
        alias="TASK_DATABASE_URL",
        description="MySQL database for task management",
    )
    data_database_url: str = Field(
        default="mysql+pymysql://insightmesh_data:insightmesh_data_password@mysql:3306/insightmesh_data",
        alias="DATA_DATABASE_URL",
        description="MySQL database for metric_records table",
    )

    # Main Slack Bot API integration
    slack_bot_api_url: str = Field(
        default="http://localhost:8080", alias="SLACK_BOT_API_URL"
    )
    slack_bot_api_key: str | None = Field(default=None, alias="SLACK_BOT_API_KEY")

    # Slack API credentials (for direct Slack operations)
    slack_bot_token: str | None = Field(default=None, alias="SLACK_BOT_TOKEN")
    slack_app_token: str | None = Field(default=None, alias="SLACK_APP_TOKEN")

    # Google Drive API
    google_credentials_path: str | None = Field(
        default=None, alias="GOOGLE_CREDENTIALS_PATH"
    )
    google_token_path: str | None = Field(default=None, alias="GOOGLE_TOKEN_PATH")

    # Metrics API
    metrics_api_url: str | None = Field(default=None, alias="METRICS_API_URL")
    metrics_api_key: str | None = Field(default=None, alias="METRICS_API_KEY")

    # Portal API (8th Light Employee Portal)
    portal_secret: str | None = Field(default=None, alias="PORTAL_SECRET")
    portal_url: str = Field(default="https://portal.8thlight.com", alias="PORTAL_URL")
    portal_email: str = Field(
        default="bot@8thlight.com",
        alias="PORTAL_EMAIL",
        description="Email for Portal JWT authentication",
    )

    # Vector database configuration (Qdrant)
    qdrant_host: str = Field(
        default="qdrant",
        alias="QDRANT_HOST",
        description="Qdrant host (docker service name)",
    )
    qdrant_port: int = Field(
        default=6333, alias="QDRANT_PORT", description="Qdrant port"
    )

    # Scheduler configuration
    scheduler_timezone: str = Field(default="UTC", alias="SCHEDULER_TIMEZONE")
    scheduler_job_defaults_coalesce: bool = Field(
        default=True, alias="SCHEDULER_JOB_DEFAULTS_COALESCE"
    )
    scheduler_job_defaults_max_instances: int = Field(
        default=1, alias="SCHEDULER_JOB_DEFAULTS_MAX_INSTANCES"
    )
    scheduler_executors_thread_pool_max_workers: int = Field(
        default=20, alias="SCHEDULER_EXECUTORS_THREAD_POOL_MAX_WORKERS"
    )


def get_settings() -> TasksSettings:
    """Get application settings."""
    return TasksSettings()
