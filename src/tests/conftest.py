import asyncio
import logging
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Configure logging for tests (reduce noise)
logging.basicConfig(level=logging.WARNING)


# Mock Langfuse to prevent import errors and external calls in tests
@pytest.fixture(scope="session", autouse=True)
def mock_langfuse():
    """Mock Langfuse imports and services for all tests."""
    with patch.dict(os.environ, {"LANGFUSE_ENABLED": "false"}, clear=False):
        # Mock the entire langfuse module to prevent import errors
        langfuse_mock = MagicMock()

        # Mock the decorators
        def mock_observe(name=None, as_type=None, **kwargs):
            def decorator(func):
                return func

            return decorator

        langfuse_mock.decorators.observe = mock_observe
        langfuse_mock.decorators.langfuse_context = MagicMock()
        langfuse_mock.openai.AsyncOpenAI = MagicMock()

        with (
            patch.dict(
                "sys.modules",
                {
                    "langfuse": langfuse_mock,
                    "langfuse.decorators": langfuse_mock.decorators,
                    "langfuse.openai": langfuse_mock.openai,
                },
            ),
            patch("services.langfuse_service.get_langfuse_service", return_value=None),
            patch("services.langfuse_service.observe", side_effect=mock_observe),
            patch("services.langfuse_service.langfuse_context", MagicMock()),
        ):
            yield


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for session."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Set up test environment variables"""
    test_env = {
        "SLACK_BOT_TOKEN": "xoxb-test-token",
        "SLACK_APP_TOKEN": "xapp-test-token",
        "LLM_API_URL": "https://api.test.com/v1",
        "LLM_API_KEY": "test-api-key",
        "DATABASE_URL": "postgresql+asyncpg://test:test@localhost:5432/test_db",
        "CACHE_REDIS_URL": "redis://localhost:6379/0",
        "ENVIRONMENT": "test",
        "LOG_LEVEL": "WARNING",
    }

    with patch.dict(os.environ, test_env, clear=False):
        yield


@pytest.fixture
def mock_settings():
    """Mock application settings with test values."""
    settings = MagicMock()

    # Slack settings
    settings.slack = MagicMock()
    settings.slack.bot_token = "xoxb-test"
    settings.slack.app_token = "xapp-test"
    settings.slack.bot_id = "B12345TEST"

    # LLM settings
    settings.llm = MagicMock()
    settings.llm.api_url = "https://api.test.com/v1"
    settings.llm.api_key = MagicMock()
    settings.llm.api_key.get_secret_value.return_value = "test-key"
    settings.llm.model = "gpt-4o-mini"

    # Database settings
    settings.database = MagicMock()
    settings.database.enabled = True
    settings.database.url = "postgresql+asyncpg://test:test@localhost:5432/test_db"

    # Cache settings
    settings.cache = MagicMock()
    settings.cache.enabled = True
    settings.cache.redis_url = "redis://localhost:6379/0"
    settings.cache.conversation_ttl = 1800

    return settings


@pytest.fixture
def mock_slack_service():
    """Mock Slack service for testing."""
    service = AsyncMock()
    service.send_message = AsyncMock()
    service.send_thinking_indicator = AsyncMock(return_value="thinking_ts_12345")
    service.delete_thinking_indicator = AsyncMock()
    service.get_thread_history = AsyncMock(return_value=([], True))
    service.get_thread_info = AsyncMock(return_value={"bot_is_participant": False})
    service.bot_id = "B12345TEST"
    return service


@pytest.fixture
def mock_llm_service():
    """Mock LLM service for testing."""
    service = AsyncMock()
    service.get_response = AsyncMock(return_value="Test LLM response")
    service.close = AsyncMock()
    return service


@pytest.fixture
def mock_conversation_cache():
    """Mock conversation cache for testing."""
    cache = AsyncMock()
    cache.get_conversation = AsyncMock(return_value=([], True, "cache"))
    cache.update_conversation = AsyncMock()
    cache.get_cache_stats = AsyncMock(
        return_value={
            "total_conversations": 10,
            "cache_hits": 8,
            "cache_misses": 2,
            "hit_rate": 0.8,
            "redis_connection": "healthy",
        }
    )
    cache.close = AsyncMock()
    return cache


@pytest.fixture
def mock_prompt_service():
    """Mock user prompt service for testing."""
    service = AsyncMock()
    service.initialize = AsyncMock()
    service.close = AsyncMock()
    service.get_user_prompt = AsyncMock(return_value=None)  # Default: no custom prompt
    service.set_user_prompt = AsyncMock()
    service.get_user_prompt_history = AsyncMock(return_value=[])
    service.reset_user_prompt = AsyncMock()

    # Mock migration manager
    service.migration_manager = AsyncMock()
    service.migration_manager.get_migration_status.return_value = {
        "total_migrations": 1,
        "applied_count": 1,
        "pending_count": 0,
        "applied_migrations": ["001"],
        "pending_migrations": [],
        "latest_applied": "001",
    }

    return service


@pytest.fixture
def mock_migration_manager():
    """Mock migration manager for testing."""
    manager = AsyncMock()
    manager.initialize = AsyncMock()
    manager.apply_migrations = AsyncMock()
    manager.get_applied_migrations = AsyncMock(return_value=["001"])
    manager.get_migration_status = AsyncMock(
        return_value={
            "total_migrations": 1,
            "applied_count": 1,
            "pending_count": 0,
            "applied_migrations": ["001"],
            "pending_migrations": [],
            "latest_applied": "001",
        }
    )
    manager.rollback_migration = AsyncMock()
    manager.close = AsyncMock()
    return manager


@pytest.fixture
def sample_user_message():
    """Sample user message for testing."""
    return {
        "user_id": "U12345TEST",
        "text": "Hello, how are you?",
        "channel": "C12345TEST",
        "thread_ts": "1234567890.123456",
    }


@pytest.fixture
def sample_thread_messages():
    """Sample thread messages for testing."""
    return [
        {"role": "user", "content": "What is Python?"},
        {"role": "assistant", "content": "Python is a programming language."},
    ]


# Auto-mock external APIs to prevent real API calls in tests
@pytest.fixture(autouse=True)
def mock_external_apis():
    """Mock external API calls by default."""
    with patch("aiohttp.ClientSession") as mock_session:
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = {"status": "ok"}

        mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response
        mock_session.return_value.__aenter__.return_value.post.return_value.__aenter__.return_value = mock_response

        yield mock_session
