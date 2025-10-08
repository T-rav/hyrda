"""Configuration settings for the tasks service."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class TasksSettings(BaseSettings):
    """Tasks service configuration."""

    model_config = SettingsConfigDict(
        env_file=".env", env_ignore_empty=True, extra="ignore"
    )

    # Server configuration
    port: int = Field(default=8081, alias="FLASK_PORT")
    host: str = Field(default="0.0.0.0", alias="TASKS_HOST")
    secret_key: str = Field(
        default="dev-secret-key-change-in-production", alias="SECRET_KEY"
    )
    flask_env: str = Field(default="production", alias="FLASK_ENV")

    # Database configuration
    task_database_url: str = Field(
        default="mysql+pymysql://insightmesh_tasks:insightmesh_tasks_password@localhost:3306/insightmesh_task",
        alias="TASK_DATABASE_URL",
        description="MySQL database for task management",
    )
    data_database_url: str = Field(
        default="postgresql://postgres:password@localhost:5432/insightmesh_data",
        alias="DATA_DATABASE_URL",
        description="PostgreSQL database for metric_records table (sync driver)",
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
