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


# Mock OpenTelemetry to prevent import errors and context manager issues
@pytest.fixture(scope="session", autouse=True)
def mock_opentelemetry():
    """Mock OpenTelemetry imports for all tests."""
    from contextlib import contextmanager

    @contextmanager
    def mock_create_span(*args, **kwargs):
        """Mock create_span as a proper context manager."""
        yield MagicMock()

    def mock_record_exception(*args, **kwargs):
        """Mock record_exception as a no-op."""
        pass

    with (
        patch(
            "shared.utils.otel_http_client.create_span", side_effect=mock_create_span
        ),
        patch(
            "shared.utils.otel_http_client.record_exception",
            side_effect=mock_record_exception,
        ),
    ):
        yield


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
        ):
            # Note: Removed langfuse_service patches since internal_deep_research no longer uses Langfuse
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
    """Set up test environment variables

    Only sets fake API keys if LLM_API_KEY is not already set (allows integration tests)
    """
    # If LLM_API_KEY is already set, don't override it (integration tests)
    if os.getenv("LLM_API_KEY") and os.getenv("LLM_API_KEY") != "test-api-key":
        # Integration test mode - don't override environment
        yield
        return

    # Unit test mode - use fake API keys
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


# Factory classes for creating test mocks with consistent patterns
class SettingsMockFactory:
    """Factory for creating application settings mocks"""

    @staticmethod
    def create_basic_settings() -> MagicMock:
        """Create basic application settings mock with default test values"""
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

    @staticmethod
    def create_settings_with_disabled_cache() -> MagicMock:
        """Create settings with cache disabled"""
        settings = SettingsMockFactory.create_basic_settings()
        settings.cache.enabled = False
        return settings

    @staticmethod
    def create_settings_with_disabled_database() -> MagicMock:
        """Create settings with database disabled"""
        settings = SettingsMockFactory.create_basic_settings()
        settings.database.enabled = False
        return settings


class SlackServiceMockFactory:
    """Factory for creating Slack service mocks"""

    @staticmethod
    def create_basic_service(bot_id: str = "B12345TEST") -> AsyncMock:
        """Create basic Slack service mock with standard responses"""
        service = AsyncMock()
        service.send_message = AsyncMock()
        service.send_thinking_indicator = AsyncMock(return_value="thinking_ts_12345")
        service.delete_thinking_indicator = AsyncMock()
        service.get_thread_history = AsyncMock(return_value=([], True))
        service.get_thread_info = AsyncMock(return_value={"bot_is_participant": False})
        service.bot_id = bot_id
        return service

    @staticmethod
    def create_service_with_thread_history(history: list) -> AsyncMock:
        """Create Slack service mock with pre-populated thread history"""
        service = SlackServiceMockFactory.create_basic_service()
        service.get_thread_history = AsyncMock(return_value=(history, True))
        return service

    @staticmethod
    def create_failing_service(error: str = "Slack API error") -> AsyncMock:
        """Create Slack service mock that raises errors"""
        service = SlackServiceMockFactory.create_basic_service()
        service.send_message = AsyncMock(side_effect=Exception(error))
        return service


class LLMServiceMockFactory:
    """Factory for creating LLM service mocks"""

    @staticmethod
    def create_basic_service(response: str = "Test LLM response") -> AsyncMock:
        """Create basic LLM service mock with standard response"""
        service = AsyncMock()
        service.get_response = AsyncMock(return_value=response)
        service.close = AsyncMock()
        return service

    @staticmethod
    def create_failing_service(error: str = "LLM API error") -> AsyncMock:
        """Create LLM service mock that raises errors"""
        service = AsyncMock()
        service.get_response = AsyncMock(side_effect=Exception(error))
        service.close = AsyncMock()
        return service

    @staticmethod
    def create_streaming_service(chunks: list[str]) -> AsyncMock:
        """Create LLM service mock that returns streaming responses"""
        service = AsyncMock()

        async def mock_stream():
            for chunk in chunks:
                yield chunk

        service.get_response = AsyncMock(return_value=mock_stream())
        service.close = AsyncMock()
        return service


class ConversationCacheMockFactory:
    """Factory for creating conversation cache mocks"""

    @staticmethod
    def create_basic_cache() -> AsyncMock:
        """Create basic conversation cache mock with standard responses"""
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

    @staticmethod
    def create_cache_with_conversation(conversation: list) -> AsyncMock:
        """Create cache mock with pre-populated conversation"""
        cache = ConversationCacheMockFactory.create_basic_cache()
        cache.get_conversation = AsyncMock(return_value=(conversation, True, "cache"))
        return cache

    @staticmethod
    def create_failing_cache(error: str = "Redis connection error") -> AsyncMock:
        """Create cache mock that raises errors"""
        cache = AsyncMock()
        cache.get_conversation = AsyncMock(side_effect=Exception(error))
        cache.update_conversation = AsyncMock(side_effect=Exception(error))
        cache.get_cache_stats = AsyncMock(side_effect=Exception(error))
        cache.close = AsyncMock()
        return cache


# Fixtures using factory classes
@pytest.fixture
def mock_settings():
    """Mock application settings with test values."""
    return SettingsMockFactory.create_basic_settings()


@pytest.fixture
def mock_slack_service():
    """Mock Slack service for testing."""
    return SlackServiceMockFactory.create_basic_service()


@pytest.fixture
def mock_llm_service():
    """Mock LLM service for testing."""
    return LLMServiceMockFactory.create_basic_service()


@pytest.fixture
def mock_conversation_cache():
    """Mock conversation cache for testing."""
    return ConversationCacheMockFactory.create_basic_cache()


# User prompt service and migrations removed - no longer used


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


# Clean up Prometheus metrics registry to prevent conflicts in tests
@pytest.fixture(autouse=True)
def clean_prometheus_registry():
    """Clean up Prometheus metrics registry before and after each test."""
    try:
        import prometheus_client

        # Clear registry before test
        prometheus_client.REGISTRY._names_to_collectors.clear()
        prometheus_client.REGISTRY._collector_to_names.clear()

        yield

        # Clear registry after test
        prometheus_client.REGISTRY._names_to_collectors.clear()
        prometheus_client.REGISTRY._collector_to_names.clear()
    except ImportError:
        # prometheus_client not installed, skip cleanup
        yield


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


# ==============================================================================
# Helper Functions for Integration Tests
# ==============================================================================


def assert_valid_http_response(response, expected_codes=None):
    """Assert that HTTP response has a valid status code.

    Args:
        response: HTTP response object
        expected_codes: List of expected status codes (default: 2xx)
    """
    if expected_codes is None:
        expected_codes = range(200, 300)

    assert response.status_code in expected_codes, (
        f"Unexpected status code: {response.status_code}\n"
        f"Expected: {expected_codes}\n"
        f"Response: {response.text[:200] if hasattr(response, 'text') else 'N/A'}"
    )


def assert_json_contains_keys(data, required_keys):
    """Assert that JSON data contains required keys.

    Args:
        data: Dictionary or JSON response
        required_keys: List of required key names
    """
    if not isinstance(data, dict):
        try:
            data = data.json() if hasattr(data, "json") else data
        except Exception:
            raise AssertionError(f"Response is not JSON: {type(data)}") from None

    missing_keys = [key for key in required_keys if key not in data]

    assert not missing_keys, (
        f"Missing required keys: {missing_keys}\nAvailable keys: {list(data.keys())}"
    )
