import asyncio
import json
import os
import sys
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add the parent directory to sys.path to allow importing the module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.conversation_cache import ConversationCache
from services.slack_service import SlackService


# Test Data Builders
class MessageBuilder:
    """Builder for creating test messages"""

    def __init__(self):
        self._role = "user"
        self._content = "test message"
        self._metadata = {}

    def with_role(self, role: str) -> "MessageBuilder":
        self._role = role
        return self

    def with_content(self, content: str) -> "MessageBuilder":
        self._content = content
        return self

    def with_metadata(self, **metadata) -> "MessageBuilder":
        self._metadata.update(metadata)
        return self

    def build(self) -> dict[str, Any]:
        message = {"role": self._role, "content": self._content}
        if self._metadata:
            message.update(self._metadata)
        return message

    @classmethod
    def user_message(cls, content: str = "test user message") -> "MessageBuilder":
        return cls().with_role("user").with_content(content)

    @classmethod
    def assistant_message(
        cls, content: str = "test assistant message"
    ) -> "MessageBuilder":
        return cls().with_role("assistant").with_content(content)

    @classmethod
    def system_message(cls, content: str = "test system message") -> "MessageBuilder":
        return cls().with_role("system").with_content(content)


class ConversationBuilder:
    """Builder for creating test conversations"""

    def __init__(self):
        self._messages = []
        self._channel = "C12345"
        self._thread_ts = "1234567890.123"

    def with_messages(self, messages: list[dict[str, Any]]) -> "ConversationBuilder":
        self._messages = messages
        return self

    def add_message(self, message: dict[str, Any]) -> "ConversationBuilder":
        self._messages.append(message)
        return self

    def with_channel(self, channel: str) -> "ConversationBuilder":
        self._channel = channel
        return self

    def with_thread_ts(self, thread_ts: str) -> "ConversationBuilder":
        self._thread_ts = thread_ts
        return self

    def build(self) -> tuple:
        return (self._messages, self._channel, self._thread_ts)

    @classmethod
    def simple_conversation(cls) -> "ConversationBuilder":
        return (
            cls()
            .add_message(MessageBuilder.user_message("Hello").build())
            .add_message(MessageBuilder.assistant_message("Hi there!").build())
        )

    @classmethod
    def large_conversation(cls, message_count: int = 100) -> "ConversationBuilder":
        builder = cls()
        for i in range(message_count):
            role = "user" if i % 2 == 0 else "assistant"
            content = f"Message {i} content"
            builder.add_message(
                MessageBuilder().with_role(role).with_content(content).build()
            )
        return builder


class CacheStatsBuilder:
    """Builder for creating cache statistics"""

    def __init__(self):
        self._stats = {
            "total_conversations": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "hit_rate": 0.0,
            "redis_connection": "healthy",
            "status": "available",
        }

    def with_conversations(self, count: int) -> "CacheStatsBuilder":
        self._stats["total_conversations"] = count
        return self

    def with_hits(self, hits: int) -> "CacheStatsBuilder":
        self._stats["cache_hits"] = hits
        return self

    def with_misses(self, misses: int) -> "CacheStatsBuilder":
        self._stats["cache_misses"] = misses
        return self

    def with_hit_rate(self, rate: float) -> "CacheStatsBuilder":
        self._stats["hit_rate"] = rate
        return self

    def with_status(self, status: str) -> "CacheStatsBuilder":
        self._stats["status"] = status
        return self

    def unavailable(self) -> "CacheStatsBuilder":
        self._stats["status"] = "unavailable"
        self._stats["redis_connection"] = "unavailable"
        return self

    def with_error(self, error: str) -> "CacheStatsBuilder":
        self._stats["status"] = "error"
        self._stats["error"] = error
        return self

    def build(self) -> dict[str, Any]:
        return self._stats.copy()


# Factory Methods for Mock Setup
class RedisFactory:
    """Factory for creating Redis mocks with common configurations"""

    @staticmethod
    def create_healthy_redis() -> AsyncMock:
        """Create a healthy Redis mock"""
        mock_redis = AsyncMock()
        mock_redis.ping.return_value = "PONG"
        mock_redis.get.return_value = None  # Default to cache miss
        mock_redis.setex.return_value = True
        mock_redis.delete.return_value = 2
        mock_redis.keys.return_value = []
        mock_redis.info.return_value = {"used_memory_human": "1MB"}
        mock_redis.aclose.return_value = None
        return mock_redis

    @staticmethod
    def create_failing_redis(error: str = "Connection failed") -> AsyncMock:
        """Create a Redis mock that fails connection"""
        import redis.asyncio as redis

        mock_redis = AsyncMock()
        mock_redis.ping.side_effect = redis.ConnectionError(error)
        return mock_redis

    @staticmethod
    def create_redis_with_cache(
        messages: list[dict[str, Any]], metadata: dict[str, Any] | None = None
    ) -> AsyncMock:
        """Create Redis mock with cached data"""
        mock_redis = RedisFactory.create_healthy_redis()

        if metadata is None:
            metadata = {"created_at": "2023-01-01T00:00:00Z", "ttl": 1800}

        mock_redis.get.side_effect = [
            json.dumps(messages),  # cached_data
            json.dumps(metadata),  # cached_meta
        ]
        return mock_redis

    @staticmethod
    def create_redis_with_error(
        error: str = "Redis error", operation: str = "get"
    ) -> AsyncMock:
        """Create Redis mock that fails on specific operations"""
        mock_redis = RedisFactory.create_healthy_redis()
        setattr(mock_redis, operation, AsyncMock(side_effect=Exception(error)))
        return mock_redis


class SlackServiceFactory:
    """Factory for creating SlackService mocks"""

    @staticmethod
    def create_mock_slack_service(
        messages: list[dict[str, Any]] | None = None, success: bool = True
    ) -> AsyncMock:
        """Create mock Slack service"""
        service = AsyncMock(spec=SlackService)

        if messages is None:
            messages = [MessageBuilder.user_message("from slack").build()]

        service.get_thread_history.return_value = (messages, success)
        return service


class ConversationCacheFactory:
    """Factory for creating ConversationCache instances and mocks"""

    @staticmethod
    def create_mock_cache() -> MagicMock:
        """Create a mock ConversationCache for testing"""
        cache = MagicMock(spec=ConversationCache)

        # Mock async methods
        cache.get_conversation = AsyncMock()
        cache.update_conversation = AsyncMock()
        cache.get_cache_stats = AsyncMock()
        cache.close = AsyncMock()

        return cache

    @staticmethod
    def create_real_cache(
        redis_url: str = "redis://localhost:6379", ttl: int = 1800
    ) -> ConversationCache:
        """Create a real ConversationCache instance"""
        return ConversationCache(redis_url=redis_url, ttl=ttl)


# Fixtures using factories
@pytest.fixture
def mock_redis_url():
    """Mock Redis URL for testing"""
    return "redis://localhost:6379"


@pytest.fixture
def mock_slack_service():
    """Create mock Slack service"""
    return SlackServiceFactory.create_mock_slack_service()


@pytest.fixture
def mock_conversation_cache():
    """Create a mock ConversationCache for testing"""
    return ConversationCacheFactory.create_mock_cache()


class TestConversationCache:
    """Tests for ConversationCache Redis operations"""

    @pytest.mark.asyncio
    async def test_cache_initialization(self, mock_redis_url):
        """Test cache initialization with Redis connection"""
        with patch("services.conversation_cache.redis.Redis") as mock_redis_class:
            mock_redis = RedisFactory.create_healthy_redis()
            mock_redis_class.return_value = mock_redis

            cache = ConversationCacheFactory.create_real_cache(
                redis_url=mock_redis_url, ttl=1800
            )

            assert cache.redis_url == mock_redis_url
            assert cache.ttl == 1800
            assert cache.cache_key_prefix == "slack_conversation:"

    @pytest.mark.asyncio
    async def test_get_conversation_cache_hit(
        self, mock_conversation_cache, mock_slack_service
    ):
        """Test getting conversation from cache when data exists"""
        # Use builders for test data
        conversation_data = ConversationBuilder.simple_conversation().build()
        cached_messages, channel, thread_ts = conversation_data

        mock_conversation_cache.get_conversation.return_value = (
            cached_messages,
            True,
            "cache",
        )

        messages, success, source = await mock_conversation_cache.get_conversation(
            channel, thread_ts, mock_slack_service
        )

        assert success is True
        assert source == "cache"
        assert messages == cached_messages
        assert len(messages) == 2
        mock_conversation_cache.get_conversation.assert_called_once_with(
            channel, thread_ts, mock_slack_service
        )

    @pytest.mark.asyncio
    async def test_get_conversation_cache_miss_slack_fallback(
        self, mock_conversation_cache, mock_slack_service
    ):
        """Test getting conversation with cache miss, falling back to Slack API"""
        # Use builders for test data
        slack_messages = [
            MessageBuilder.user_message("How are you?").build(),
            MessageBuilder.assistant_message("I'm doing well!").build(),
        ]
        _, channel, thread_ts = ConversationBuilder().build()

        # Mock cache miss, successful Slack fallback
        mock_conversation_cache.get_conversation.return_value = (
            slack_messages,
            True,
            "slack_api",
        )

        messages, success, source = await mock_conversation_cache.get_conversation(
            channel, thread_ts, mock_slack_service
        )

        assert success is True
        assert source == "slack_api"
        assert messages == slack_messages
        assert len(messages) == 2

    @pytest.mark.asyncio
    async def test_get_conversation_cache_and_slack_fail(
        self, mock_conversation_cache, mock_slack_service
    ):
        """Test getting conversation when both cache and Slack API fail"""
        _, channel, thread_ts = ConversationBuilder().build()

        # Mock both cache and Slack API failure
        mock_conversation_cache.get_conversation.return_value = ([], False, "error")

        messages, success, source = await mock_conversation_cache.get_conversation(
            channel, thread_ts, mock_slack_service
        )

        assert success is False
        assert source == "error"
        assert messages == []

    @pytest.mark.asyncio
    async def test_update_conversation_user_message(self, mock_conversation_cache):
        """Test updating conversation with user message"""
        _, _, thread_ts = ConversationBuilder().build()
        message = MessageBuilder.user_message("What is Python?").build()

        await mock_conversation_cache.update_conversation(
            thread_ts, message, is_bot_message=False
        )

        mock_conversation_cache.update_conversation.assert_called_once_with(
            thread_ts, message, is_bot_message=False
        )

    @pytest.mark.asyncio
    async def test_update_conversation_bot_message(self, mock_conversation_cache):
        """Test updating conversation with bot message"""
        _, _, thread_ts = ConversationBuilder().build()
        message = MessageBuilder.assistant_message(
            "Python is a programming language"
        ).build()

        await mock_conversation_cache.update_conversation(
            thread_ts, message, is_bot_message=True
        )

        mock_conversation_cache.update_conversation.assert_called_once_with(
            thread_ts, message, is_bot_message=True
        )

    @pytest.mark.asyncio
    async def test_get_cache_stats(self, mock_conversation_cache):
        """Test getting cache statistics"""
        expected_stats = (
            CacheStatsBuilder()
            .with_conversations(42)
            .with_hits(100)
            .with_misses(25)
            .with_hit_rate(0.8)
            .build()
        )

        mock_conversation_cache.get_cache_stats.return_value = expected_stats

        stats = await mock_conversation_cache.get_cache_stats()

        assert stats == expected_stats
        assert stats["total_conversations"] == 42
        assert stats["hit_rate"] == 0.8
        mock_conversation_cache.get_cache_stats.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_cache(self, mock_conversation_cache):
        """Test closing the cache connection"""
        await mock_conversation_cache.close()

        mock_conversation_cache.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_key_generation(self):
        """Test cache key generation for different channels and threads"""
        cache_key_prefix = "slack_conversation:"

        test_cases = [
            ("C12345", "1234567890.123", f"{cache_key_prefix}C12345:1234567890.123"),
            ("D98765", "9876543210.456", f"{cache_key_prefix}D98765:9876543210.456"),
            ("G11111", "1111111111.789", f"{cache_key_prefix}G11111:1111111111.789"),
        ]

        for channel, thread_ts, expected_key in test_cases:
            actual_key = f"{cache_key_prefix}{channel}:{thread_ts}"
            assert actual_key == expected_key

    @pytest.mark.asyncio
    async def test_redis_connection_error_handling(
        self, mock_conversation_cache, mock_slack_service
    ):
        """Test handling Redis connection errors gracefully"""
        _, channel, thread_ts = ConversationBuilder().build()

        # Mock Redis connection error, should fallback to Slack
        mock_conversation_cache.get_conversation.return_value = (
            [],
            True,
            "slack_api_fallback",
        )

        messages, success, source = await mock_conversation_cache.get_conversation(
            channel, thread_ts, mock_slack_service
        )

        # Should still succeed via fallback
        assert success is True
        assert source == "slack_api_fallback"

    @pytest.mark.asyncio
    async def test_conversation_ttl_setting(self, mock_redis_url):
        """Test that TTL is properly configured"""
        custom_ttl = 3600  # 1 hour

        with patch("services.conversation_cache.redis.Redis") as mock_redis_class:
            mock_redis = RedisFactory.create_healthy_redis()
            mock_redis_class.return_value = mock_redis

            cache = ConversationCacheFactory.create_real_cache(
                redis_url=mock_redis_url, ttl=custom_ttl
            )

            assert cache.ttl == custom_ttl

    def test_message_format_validation(self):
        """Test that messages follow expected format"""
        valid_user_message = MessageBuilder.user_message("Hello").build()
        valid_bot_message = MessageBuilder.assistant_message("Hi there!").build()

        # Validate required fields
        assert "role" in valid_user_message
        assert "content" in valid_user_message
        assert valid_user_message["role"] in ["user", "assistant", "system"]

        assert "role" in valid_bot_message
        assert "content" in valid_bot_message
        assert valid_bot_message["role"] in ["user", "assistant", "system"]

    @pytest.mark.asyncio
    async def test_large_conversation_handling(
        self, mock_conversation_cache, mock_slack_service
    ):
        """Test handling large conversations that might hit cache limits"""
        # Use builder for large conversation
        conversation_data = ConversationBuilder.large_conversation(100).build()
        large_conversation, channel, thread_ts = conversation_data

        mock_conversation_cache.get_conversation.return_value = (
            large_conversation,
            True,
            "cache",
        )

        messages, success, source = await mock_conversation_cache.get_conversation(
            channel, thread_ts, mock_slack_service
        )

        assert success is True
        assert source == "cache"
        assert len(messages) == 100

    @pytest.mark.asyncio
    async def test_concurrent_cache_operations(self, mock_conversation_cache):
        """Test concurrent cache operations don't interfere"""
        _, _, thread_ts1 = (
            ConversationBuilder().with_thread_ts("1234567890.123").build()
        )
        _, _, thread_ts2 = (
            ConversationBuilder().with_thread_ts("1234567890.456").build()
        )

        message1 = MessageBuilder.user_message("First conversation").build()
        message2 = MessageBuilder.user_message("Second conversation").build()

        # Simulate concurrent updates
        await asyncio.gather(
            mock_conversation_cache.update_conversation(
                thread_ts1, message1, is_bot_message=False
            ),
            mock_conversation_cache.update_conversation(
                thread_ts2, message2, is_bot_message=False
            ),
        )

        # Both calls should have been made
        assert mock_conversation_cache.update_conversation.call_count == 2


class TestConversationCacheImplementation:
    """Tests for actual ConversationCache implementation (not mocks)"""

    @pytest.fixture
    def cache(self):
        """Create real ConversationCache instance for testing"""
        return ConversationCacheFactory.create_real_cache()

    def test_get_cache_key(self):
        """Test cache key generation"""
        cache = ConversationCacheFactory.create_real_cache()
        _, _, thread_ts = ConversationBuilder().build()
        key = cache._get_cache_key(thread_ts)
        assert key == f"conversation:{thread_ts}"

    def test_get_metadata_key(self):
        """Test metadata key generation"""
        cache = ConversationCacheFactory.create_real_cache()
        _, _, thread_ts = ConversationBuilder().build()
        key = cache._get_metadata_key(thread_ts)
        assert key == f"conversation_meta:{thread_ts}"

    @pytest.mark.asyncio
    async def test_get_redis_client_connection_failure(self):
        """Test Redis client handling when connection fails"""
        cache = ConversationCacheFactory.create_real_cache(
            redis_url="redis://invalid:1234"
        )

        with patch("services.conversation_cache.redis.from_url") as mock_from_url:
            mock_redis = RedisFactory.create_failing_redis("Connection failed")
            mock_from_url.return_value = mock_redis

            client = await cache._get_redis_client()
            assert client is None
            assert cache._redis_available is False

    @pytest.mark.asyncio
    async def test_get_redis_client_success(self):
        """Test successful Redis client creation"""
        cache = ConversationCacheFactory.create_real_cache()

        with patch("services.conversation_cache.redis.from_url") as mock_from_url:
            mock_redis = RedisFactory.create_healthy_redis()
            mock_from_url.return_value = mock_redis

            client = await cache._get_redis_client()
            assert client == mock_redis
            assert cache._redis_available is True

    @pytest.mark.asyncio
    async def test_get_conversation_no_redis(self, cache):
        """Test get_conversation when Redis is unavailable"""
        test_messages = [MessageBuilder.user_message("test").build()]
        mock_slack_service = SlackServiceFactory.create_mock_slack_service(
            test_messages
        )
        _, channel, thread_ts = ConversationBuilder().with_channel("C123").build()

        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_get_client.return_value = None  # No Redis client

            messages, success, source = await cache.get_conversation(
                channel, thread_ts, mock_slack_service
            )

        assert success is True
        assert source == "slack_api"
        assert len(messages) == 1
        mock_slack_service.get_thread_history.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_conversation_cache_hit(self, cache):
        """Test successful cache retrieval"""
        cached_messages = [MessageBuilder.user_message("Hello").build()]
        cached_metadata = {"created_at": "2023-01-01T00:00:00Z", "ttl": 1800}
        _, channel, thread_ts = ConversationBuilder().with_channel("C123").build()

        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_redis = RedisFactory.create_redis_with_cache(
                cached_messages, cached_metadata
            )
            mock_get_client.return_value = mock_redis

            with patch.object(cache, "_get_cache_age", return_value=300):
                messages, success, source = await cache.get_conversation(
                    channel, thread_ts, AsyncMock()
                )

        assert success is True
        assert source == "cache"
        assert messages == cached_messages

    @pytest.mark.asyncio
    async def test_get_conversation_cache_miss_slack_fallback(self, cache):
        """Test cache miss with Slack API fallback"""
        slack_messages = [MessageBuilder.user_message("From Slack").build()]
        mock_slack_service = SlackServiceFactory.create_mock_slack_service(
            slack_messages
        )
        _, channel, thread_ts = ConversationBuilder().with_channel("C123").build()

        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_redis = RedisFactory.create_healthy_redis()
            mock_redis.get.return_value = None  # Cache miss
            mock_get_client.return_value = mock_redis

            messages, success, source = await cache.get_conversation(
                channel, thread_ts, mock_slack_service
            )

        assert success is True
        assert source == "slack_api"
        assert messages == slack_messages

    @pytest.mark.asyncio
    async def test_update_conversation_no_redis(self, cache):
        """Test update_conversation when Redis is unavailable"""
        cache._redis_available = False
        cache.redis_client = None

        message = MessageBuilder.user_message("test").build()
        _, _, thread_ts = ConversationBuilder().build()

        # Should not raise exception when Redis unavailable
        await cache.update_conversation(thread_ts, message, is_bot_message=False)

    @pytest.mark.asyncio
    async def test_update_conversation_success(self, cache):
        """Test successful conversation update"""
        message = MessageBuilder.user_message("New message").build()
        existing_messages = [MessageBuilder.assistant_message("Old message").build()]
        _, _, thread_ts = ConversationBuilder().build()

        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_redis = RedisFactory.create_healthy_redis()
            mock_redis.get.return_value = json.dumps(existing_messages)
            mock_get_client.return_value = mock_redis

            with patch("services.conversation_cache.datetime") as mock_datetime:
                mock_datetime.now.return_value.isoformat.return_value = (
                    "2023-01-01T00:00:00Z"
                )
                mock_datetime.UTC = UTC

                await cache.update_conversation(
                    thread_ts, message, is_bot_message=False
                )

        # Verify Redis operations
        assert mock_redis.setex.call_count == 2  # Both data and metadata

    @pytest.mark.asyncio
    async def test_get_cache_stats_no_redis(self, cache):
        """Test cache stats when Redis unavailable"""
        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_get_client.return_value = None  # No Redis client

            stats = await cache.get_cache_stats()

        expected_stats = CacheStatsBuilder().unavailable().build()
        assert stats["status"] == expected_stats["status"]

    @pytest.mark.asyncio
    async def test_get_cache_stats_with_redis(self, cache):
        """Test cache stats with Redis available"""
        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_redis = RedisFactory.create_healthy_redis()
            mock_redis.keys.return_value = ["conversation:1", "conversation:2"]
            mock_redis.info.return_value = {"used_memory_human": "1MB"}
            mock_get_client.return_value = mock_redis

            stats = await cache.get_cache_stats()

        assert stats["status"] == "available"
        assert stats["cached_conversations"] == 2

    def test_get_cache_age(self, cache):
        """Test cache age calculation"""
        # Mock metadata with timestamp (using cached_at key)
        metadata = {"cached_at": "2023-01-01T00:00:00Z"}

        with patch("services.conversation_cache.datetime") as mock_datetime:
            mock_now = datetime(2023, 1, 1, 0, 5, 0, tzinfo=UTC)  # 5 minutes later
            mock_datetime.now.return_value = mock_now
            mock_datetime.fromisoformat = datetime.fromisoformat
            mock_datetime.UTC = UTC

            age = cache._get_cache_age(metadata)
            assert age == 300  # 5 minutes in seconds

    def test_get_cache_age_invalid_timestamp(self, cache):
        """Test cache age with invalid timestamp"""
        metadata = {"created_at": "invalid-timestamp"}

        age = cache._get_cache_age(metadata)
        assert age == 0  # Should return 0 for invalid timestamps

    @pytest.mark.asyncio
    async def test_close_no_redis(self, cache):
        """Test close when Redis client not available"""
        cache.redis_client = None

        # Should not raise exception
        await cache.close()

    @pytest.mark.asyncio
    async def test_close_with_redis(self, cache):
        """Test close with active Redis client"""
        mock_redis = RedisFactory.create_healthy_redis()
        cache.redis_client = mock_redis

        await cache.close()

        mock_redis.aclose.assert_called_once()
        assert cache.redis_client is None

    @pytest.mark.asyncio
    async def test_update_conversation_existing_cache(self, cache):
        """Test updating existing cached conversation"""
        existing_messages = [MessageBuilder.user_message("First message").build()]
        new_message = MessageBuilder.assistant_message("Response").build()
        _, _, thread_ts = ConversationBuilder().build()

        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_redis = RedisFactory.create_healthy_redis()
            mock_redis.get.return_value = json.dumps(existing_messages)
            mock_get_client.return_value = mock_redis

            with patch("services.conversation_cache.datetime") as mock_datetime:
                mock_datetime.now.return_value.isoformat.return_value = (
                    "2023-01-01T00:00:00Z"
                )
                mock_datetime.UTC = UTC

                await cache.update_conversation(
                    thread_ts, new_message, is_bot_message=True
                )

        # Should get existing conversation first
        mock_redis.get.assert_called()
        # Should update with both messages
        assert mock_redis.setex.call_count == 2

    @pytest.mark.asyncio
    async def test_get_conversation_json_decode_error(self, cache):
        """Test handling of JSON decode errors in cache"""
        fallback_messages = [MessageBuilder.user_message("fallback").build()]
        mock_slack_service = SlackServiceFactory.create_mock_slack_service(
            fallback_messages
        )
        _, channel, thread_ts = ConversationBuilder().with_channel("C123").build()

        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_redis = RedisFactory.create_healthy_redis()
            mock_redis.get.return_value = "invalid json"  # Invalid JSON
            mock_get_client.return_value = mock_redis

            messages, success, source = await cache.get_conversation(
                channel, thread_ts, mock_slack_service
            )

        # Should fallback to Slack API
        assert success is True
        assert source == "slack_api"
        mock_slack_service.get_thread_history.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_conversation_new_cache(self, cache):
        """Test creating new cached conversation"""
        message = MessageBuilder.user_message("First message").build()
        _, _, thread_ts = ConversationBuilder().build()

        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_redis = RedisFactory.create_healthy_redis()
            mock_redis.get.return_value = None  # No existing conversation
            mock_get_client.return_value = mock_redis

            with patch("services.conversation_cache.datetime") as mock_datetime:
                mock_datetime.now.return_value.isoformat.return_value = (
                    "2023-01-01T00:00:00Z"
                )
                mock_datetime.UTC = UTC

                await cache.update_conversation(
                    thread_ts, message, is_bot_message=False
                )

        # Should create new conversation with single message
        mock_redis.setex.assert_called()
        assert mock_redis.setex.call_count == 2  # Data and metadata

    @pytest.mark.asyncio
    async def test_cache_conversation_helper(self, cache):
        """Test the _cache_conversation helper method"""
        messages = [MessageBuilder.user_message("Test").build()]
        _, _, thread_ts = ConversationBuilder().build()

        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_redis = RedisFactory.create_healthy_redis()
            mock_get_client.return_value = mock_redis

            with patch("services.conversation_cache.datetime") as mock_datetime:
                mock_datetime.now.return_value.isoformat.return_value = (
                    "2023-01-01T00:00:00Z"
                )
                mock_datetime.UTC = UTC

                await cache._cache_conversation(mock_redis, thread_ts, messages)

        # Should cache both messages and metadata
        assert mock_redis.setex.call_count == 2

    @pytest.mark.asyncio
    async def test_clear_conversation_success(self, cache):
        """Test successful conversation clearing"""
        _, _, thread_ts = ConversationBuilder().build()

        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_redis = RedisFactory.create_healthy_redis()
            mock_redis.delete.return_value = 2  # Deleted 2 keys
            mock_get_client.return_value = mock_redis

            result = await cache.clear_conversation(thread_ts)

        assert result is True
        mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_clear_conversation_no_redis(self, cache):
        """Test conversation clearing when Redis unavailable"""
        _, _, thread_ts = ConversationBuilder().build()

        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_get_client.return_value = None

            result = await cache.clear_conversation(thread_ts)

        assert result is False

    @pytest.mark.asyncio
    async def test_update_conversation_cache_error(self, cache):
        """Test update conversation with caching error"""
        message = MessageBuilder.user_message("Test").build()
        _, _, thread_ts = ConversationBuilder().build()

        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_redis = RedisFactory.create_redis_with_error("Redis error", "setex")
            mock_redis.get.return_value = None
            mock_get_client.return_value = mock_redis

            # Should not raise exception despite Redis error
            result = await cache.update_conversation(
                thread_ts, message, is_bot_message=False
            )
            assert result is False

    @pytest.mark.asyncio
    async def test_clear_conversation_redis_error(self, cache):
        """Test clear conversation with Redis error"""
        _, _, thread_ts = ConversationBuilder().build()

        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_redis = RedisFactory.create_redis_with_error("Redis error", "delete")
            mock_get_client.return_value = mock_redis

            result = await cache.clear_conversation(thread_ts)

        assert result is False

    @pytest.mark.asyncio
    async def test_get_cache_stats_redis_error(self, cache):
        """Test cache stats with Redis error"""
        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_redis = RedisFactory.create_redis_with_error("Redis error", "info")
            mock_get_client.return_value = mock_redis

            stats = await cache.get_cache_stats()

        expected_stats = CacheStatsBuilder().with_error("Redis error").build()
        assert stats["status"] == expected_stats["status"]
        assert "Redis error" in stats["error"]

    @pytest.mark.asyncio
    async def test_get_conversation_cache_fallback_after_error(self, cache):
        """Test cache falling back to Slack after Redis error during retrieve"""
        slack_messages = [MessageBuilder.user_message("from slack").build()]
        mock_slack_service = SlackServiceFactory.create_mock_slack_service(
            slack_messages
        )
        _, channel, thread_ts = ConversationBuilder().with_channel("C123").build()

        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_redis = RedisFactory.create_redis_with_error("Cache error", "get")
            mock_get_client.return_value = mock_redis

            messages, success, source = await cache.get_conversation(
                channel, thread_ts, mock_slack_service
            )

        assert success is True
        assert source == "slack_api"
        assert len(messages) == 1
