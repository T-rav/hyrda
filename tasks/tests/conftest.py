"""Test configuration and fixtures."""

import contextlib
import os
import tempfile
from unittest.mock import AsyncMock, Mock

import pytest
from prometheus_client import REGISTRY

from config.settings import TasksSettings
from tests.factories import (
    FastAPIAppFactory,
    MockJobRegistryFactory,
    MockSchedulerFactory,
)


# Clear Prometheus collectors before each test to avoid duplication
@pytest.fixture(scope="function", autouse=True)
def clear_prometheus_registry():
    """Clear Prometheus registry before each test."""
    collectors = list(REGISTRY._collector_to_names.keys())
    for collector in collectors:
        with contextlib.suppress(Exception):
            REGISTRY.unregister(collector)
    yield


# Reset external task loader before each test to avoid pollution
@pytest.fixture(scope="function", autouse=True)
def reset_external_loader():
    """Reset the global external task loader before each test."""
    import services.external_task_loader as loader_module

    # Reset the global loader
    loader_module._external_loader = None

    yield

    # Clean up after test
    loader_module._external_loader = None


@pytest.fixture
def test_settings():
    """Create test settings with temporary database."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        task_db_path = f.name

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        data_db_path = f.name

    # Set environment variables for Pydantic to pick up
    os.environ.update(
        {
            "SECRET_KEY": "test-secret-key",
            "SLACK_BOT_API_URL": "http://localhost:8080",
            "SLACK_BOT_API_KEY": "test-api-key",
            "SLACK_BOT_TOKEN": "xoxb-test-token",
            "TASK_DATABASE_URL": f"sqlite:///{task_db_path}",
            "DATA_DATABASE_URL": f"sqlite:///{data_db_path}",
            "REDIS_URL": "redis://localhost:6379/15",
            "METRIC_API_KEY": "test-metric-api-key",
            "LLM_API_KEY": "test-llm-api-key",
            "VECTOR_API_KEY": "test-vector-api-key",
            "PINECONE_API_KEY": "test-pinecone-api-key",
            "PINECONE_INDEX_NAME": "test-index",
            "PINECONE_ENVIRONMENT": "test-env",
        }
    )

    settings = TasksSettings()

    yield settings

    # Cleanup
    with contextlib.suppress(OSError):
        os.unlink(task_db_path)
    with contextlib.suppress(OSError):
        os.unlink(data_db_path)


@pytest.fixture
def mock_slack_client():
    """Mock Slack client."""
    client = Mock()
    client.users_list = AsyncMock()
    return client


@pytest.fixture
def mock_requests():
    """Mock requests module."""
    mock = Mock()
    mock.post = Mock()
    mock.get = Mock()
    return mock


@pytest.fixture
def sample_slack_users():
    """Sample Slack users data."""
    return [
        {
            "id": "U1234567",
            "name": "john.doe",
            "real_name": "John Doe",
            "profile": {
                "display_name": "John",
                "email": "john@example.com",
                "status_text": "Working",
            },
            "is_admin": False,
            "is_owner": False,
            "is_bot": False,
            "deleted": False,
            "tz": "America/New_York",
            "updated": 1234567890,
        },
        {
            "id": "U2345678",
            "name": "admin.user",
            "real_name": "Admin User",
            "profile": {"display_name": "Admin", "email": "admin@example.com"},
            "is_admin": True,
            "is_owner": False,
            "is_bot": False,
            "deleted": False,
            "tz": "UTC",
            "updated": 1234567890,
        },
    ]


# Flask app testing fixtures using factories


@pytest.fixture
def mock_scheduler():
    """Create a mock scheduler instance."""
    return MockSchedulerFactory.create()


@pytest.fixture
def mock_job_registry():
    """Create a mock job registry instance."""
    return MockJobRegistryFactory.create()


@pytest.fixture
def app_factory():
    """Factory function for creating Flask test apps."""
    return FastAPIAppFactory.create_test_app


@pytest.fixture
def app(monkeypatch, mock_scheduler, mock_job_registry):
    """Create a fresh Flask app for each test with mocked services."""
    # Set OAuth env vars
    monkeypatch.setenv(
        "GOOGLE_OAUTH_CLIENT_ID", "test-client-id.apps.googleusercontent.com"
    )
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("SERVER_BASE_URL", "http://localhost:5001")
    monkeypatch.setenv("ALLOWED_EMAIL_DOMAIN", "test.com")  # Domain without @ prefix
    monkeypatch.setenv("TASK_DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("DATA_DATABASE_URL", "sqlite:///:memory:")

    # Create app using factory
    test_app = FastAPIAppFactory.create_test_app(
        mock_scheduler=mock_scheduler,
        mock_registry=mock_job_registry,
    )

    return test_app


@pytest.fixture
def client(app):
    """Create an authenticated test client."""
    return FastAPIAppFactory.create_test_client(app, authenticated=True)


@pytest.fixture
def unauthenticated_client(app):
    """Create an unauthenticated test client."""
    return FastAPIAppFactory.create_test_client(app, authenticated=False)
