"""Test configuration and fixtures."""

import pytest
from unittest.mock import Mock, AsyncMock
import tempfile
import os

from config.settings import TasksSettings


@pytest.fixture
def test_settings():
    """Create test settings with temporary database."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name

    # Set environment variables for Pydantic to pick up
    os.environ.update({
        'SECRET_KEY': 'test-secret-key',
        'SLACK_BOT_API_URL': 'http://localhost:8080',
        'SLACK_BOT_API_KEY': 'test-api-key',
        'SLACK_BOT_TOKEN': 'xoxb-test-token',
        'DATABASE_URL': f"sqlite:///{db_path}",
        'REDIS_URL': 'redis://localhost:6379/15'
    })

    settings = TasksSettings()

    yield settings

    # Cleanup
    try:
        os.unlink(db_path)
    except OSError:
        pass


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
                "status_text": "Working"
            },
            "is_admin": False,
            "is_owner": False,
            "is_bot": False,
            "deleted": False,
            "tz": "America/New_York",
            "updated": 1234567890
        },
        {
            "id": "U2345678",
            "name": "admin.user",
            "real_name": "Admin User",
            "profile": {
                "display_name": "Admin",
                "email": "admin@example.com"
            },
            "is_admin": True,
            "is_owner": False,
            "is_bot": False,
            "deleted": False,
            "tz": "UTC",
            "updated": 1234567890
        }
    ]