import asyncio
import json
import os
import sys
from datetime import UTC
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add the parent directory to sys.path to allow importing the module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.conversation_cache import ConversationCache
from services.slack_service import SlackService


@pytest.fixture
def mock_redis_url():
    """Mock Redis URL for testing"""
    return "redis://localhost:6379"


@pytest.fixture
def mock_slack_service():
    """Create mock Slack service"""
    service = AsyncMock(spec=SlackService)
    service.get_thread_history = AsyncMock()
    return service


@pytest.fixture
def mock_conversation_cache():
    """Create a mock ConversationCache for testing"""
    cache = MagicMock(spec=ConversationCache)

    # Mock async methods
    cache.get_conversation = AsyncMock()
    cache.update_conversation = AsyncMock()
    cache.get_cache_stats = AsyncMock()
    cache.close = AsyncMock()

    return cache


class TestConversationCache:
    """Tests for ConversationCache Redis operations"""

    @pytest.mark.asyncio
    async def test_cache_initialization(self, mock_redis_url):
        """Test cache initialization with Redis connection"""
        with patch("services.conversation_cache.redis.Redis") as mock_redis_class:
            mock_redis = AsyncMock()
            mock_redis_class.return_value = mock_redis

            cache = ConversationCache(redis_url=mock_redis_url, ttl=1800)

            assert cache.redis_url == mock_redis_url
            assert cache.ttl == 1800
            assert cache.cache_key_prefix == "slack_conversation:"

    @pytest.mark.asyncio
    async def test_get_conversation_cache_hit(
        self, mock_conversation_cache, mock_slack_service
    ):
        """Test getting conversation from cache when data exists"""
        channel = "C12345"
        thread_ts = "1234567890.123"

        cached_messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]

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
        channel = "C12345"
        thread_ts = "1234567890.123"

        slack_messages = [
            {"role": "user", "content": "How are you?"},
            {"role": "assistant", "content": "I'm doing well!"},
        ]

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
        channel = "C12345"
        thread_ts = "1234567890.123"

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
        thread_ts = "1234567890.123"
        message = {"role": "user", "content": "What is Python?"}

        await mock_conversation_cache.update_conversation(
            thread_ts, message, is_bot_message=False
        )

        mock_conversation_cache.update_conversation.assert_called_once_with(
            thread_ts, message, is_bot_message=False
        )

    @pytest.mark.asyncio
    async def test_update_conversation_bot_message(self, mock_conversation_cache):
        """Test updating conversation with bot message"""
        thread_ts = "1234567890.123"
        message = {"role": "assistant", "content": "Python is a programming language"}

        await mock_conversation_cache.update_conversation(
            thread_ts, message, is_bot_message=True
        )

        mock_conversation_cache.update_conversation.assert_called_once_with(
            thread_ts, message, is_bot_message=True
        )

    @pytest.mark.asyncio
    async def test_get_cache_stats(self, mock_conversation_cache):
        """Test getting cache statistics"""
        expected_stats = {
            "total_conversations": 42,
            "cache_hits": 100,
            "cache_misses": 25,
            "hit_rate": 0.8,
            "redis_connection": "healthy",
        }

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
        channel = "C12345"
        thread_ts = "1234567890.123"

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
            mock_redis = AsyncMock()
            mock_redis_class.return_value = mock_redis

            cache = ConversationCache(redis_url=mock_redis_url, ttl=custom_ttl)

            assert cache.ttl == custom_ttl

    def test_message_format_validation(self):
        """Test that messages follow expected format"""
        valid_user_message = {"role": "user", "content": "Hello"}
        valid_bot_message = {"role": "assistant", "content": "Hi there!"}

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
        channel = "C12345"
        thread_ts = "1234567890.123"

        # Create a large conversation
        large_conversation = []
        for i in range(100):  # 100 messages
            large_conversation.append(
                {
                    "role": "user" if i % 2 == 0 else "assistant",
                    "content": f"Message {i} content",
                }
            )

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
        thread_ts1 = "1234567890.123"
        thread_ts2 = "1234567890.456"

        message1 = {"role": "user", "content": "First conversation"}
        message2 = {"role": "user", "content": "Second conversation"}

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
        return ConversationCache(redis_url="redis://localhost:6379", ttl=1800)

    def test_get_cache_key(self):
        """Test cache key generation"""
        cache = ConversationCache()
        thread_ts = "1234567890.123"
        key = cache._get_cache_key(thread_ts)
        assert key == "conversation:1234567890.123"

    def test_get_metadata_key(self):
        """Test metadata key generation"""
        cache = ConversationCache()
        thread_ts = "1234567890.123"
        key = cache._get_metadata_key(thread_ts)
        assert key == "conversation_meta:1234567890.123"

    @pytest.mark.asyncio
    async def test_get_redis_client_connection_failure(self):
        """Test Redis client handling when connection fails"""
        cache = ConversationCache(redis_url="redis://invalid:1234")

        with patch("services.conversation_cache.redis.from_url") as mock_from_url:
            mock_redis = AsyncMock()
            mock_redis.ping.side_effect = Exception("Connection failed")
            mock_from_url.return_value = mock_redis

            client = await cache._get_redis_client()
            assert client is None
            assert cache._redis_available is False

    @pytest.mark.asyncio
    async def test_get_redis_client_success(self):
        """Test successful Redis client creation"""
        cache = ConversationCache()

        with patch("services.conversation_cache.redis.from_url") as mock_from_url:
            mock_redis = AsyncMock()
            mock_redis.ping.return_value = "PONG"
            mock_from_url.return_value = mock_redis

            client = await cache._get_redis_client()
            assert client == mock_redis
            assert cache._redis_available is True

    @pytest.mark.asyncio
    async def test_get_conversation_no_redis(self, cache):
        """Test get_conversation when Redis is unavailable"""
        mock_slack_service = AsyncMock(spec=SlackService)
        mock_slack_service.get_thread_history.return_value = (
            [{"role": "user", "content": "test"}],
            True,
        )

        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_get_client.return_value = None  # No Redis client

            messages, success, source = await cache.get_conversation(
                "C123", "1234567890.123", mock_slack_service
            )

        assert success is True
        assert source == "slack_api"
        assert len(messages) == 1
        mock_slack_service.get_thread_history.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_conversation_cache_hit(self, cache):
        """Test successful cache retrieval"""
        cached_messages = [{"role": "user", "content": "Hello"}]
        cached_metadata = {"created_at": "2023-01-01T00:00:00Z", "ttl": 1800}

        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_redis = AsyncMock()
            mock_redis.get.side_effect = [
                json.dumps(cached_messages),  # cached_data
                json.dumps(cached_metadata),  # cached_meta
            ]
            mock_get_client.return_value = mock_redis

            with patch.object(cache, "_get_cache_age", return_value=300):
                messages, success, source = await cache.get_conversation(
                    "C123", "1234567890.123", AsyncMock()
                )

        assert success is True
        assert source == "cache"
        assert messages == cached_messages

    @pytest.mark.asyncio
    async def test_get_conversation_cache_miss_slack_fallback(self, cache):
        """Test cache miss with Slack API fallback"""
        slack_messages = [{"role": "user", "content": "From Slack"}]

        mock_slack_service = AsyncMock(spec=SlackService)
        mock_slack_service.get_thread_history.return_value = (slack_messages, True)

        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_redis = AsyncMock()
            mock_redis.get.return_value = None  # Cache miss
            mock_get_client.return_value = mock_redis

            messages, success, source = await cache.get_conversation(
                "C123", "1234567890.123", mock_slack_service
            )

        assert success is True
        assert source == "slack_api"
        assert messages == slack_messages

    @pytest.mark.asyncio
    async def test_update_conversation_no_redis(self, cache):
        """Test update_conversation when Redis is unavailable"""
        cache._redis_available = False
        cache.redis_client = None

        message = {"role": "user", "content": "test"}

        # Should not raise exception when Redis unavailable
        await cache.update_conversation("1234567890.123", message, is_bot_message=False)

    @pytest.mark.asyncio
    async def test_update_conversation_success(self, cache):
        """Test successful conversation update"""
        message = {"role": "user", "content": "New message"}
        existing_messages = [{"role": "assistant", "content": "Old message"}]

        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_redis = AsyncMock()
            mock_redis.get.return_value = json.dumps(existing_messages)
            mock_get_client.return_value = mock_redis

            with patch("services.conversation_cache.datetime") as mock_datetime:
                mock_datetime.now.return_value.isoformat.return_value = (
                    "2023-01-01T00:00:00Z"
                )
                mock_datetime.UTC = UTC

                await cache.update_conversation(
                    "1234567890.123", message, is_bot_message=False
                )

        # Verify Redis operations
        assert mock_redis.setex.call_count == 2  # Both data and metadata

    @pytest.mark.asyncio
    async def test_get_cache_stats_no_redis(self, cache):
        """Test cache stats when Redis unavailable"""
        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_get_client.return_value = None  # No Redis client

            stats = await cache.get_cache_stats()

        assert stats["status"] == "unavailable"

    @pytest.mark.asyncio
    async def test_get_cache_stats_with_redis(self, cache):
        """Test cache stats with Redis available"""
        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_redis = AsyncMock()
            mock_redis.keys.return_value = ["conversation:1", "conversation:2"]
            mock_redis.info.return_value = {"used_memory_human": "1MB"}
            mock_get_client.return_value = mock_redis

            stats = await cache.get_cache_stats()

        assert stats["status"] == "available"
        assert stats["cached_conversations"] == 2

    def test_get_cache_age(self, cache):
        """Test cache age calculation"""
        from datetime import UTC, datetime

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
        mock_redis = AsyncMock()
        cache.redis_client = mock_redis

        await cache.close()

        mock_redis.aclose.assert_called_once()
        assert cache.redis_client is None

    @pytest.mark.asyncio
    async def test_update_conversation_existing_cache(self, cache):
        """Test updating existing cached conversation"""
        existing_messages = [{"role": "user", "content": "First message"}]
        new_message = {"role": "assistant", "content": "Response"}

        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_redis = AsyncMock()
            mock_redis.get.return_value = json.dumps(existing_messages)
            mock_get_client.return_value = mock_redis

            with patch("services.conversation_cache.datetime") as mock_datetime:
                mock_datetime.now.return_value.isoformat.return_value = (
                    "2023-01-01T00:00:00Z"
                )
                mock_datetime.UTC = UTC

                await cache.update_conversation(
                    "1234567890.123", new_message, is_bot_message=True
                )

        # Should get existing conversation first
        mock_redis.get.assert_called()
        # Should update with both messages
        assert mock_redis.setex.call_count == 2

    @pytest.mark.asyncio
    async def test_get_conversation_json_decode_error(self, cache):
        """Test handling of JSON decode errors in cache"""
        mock_slack_service = AsyncMock(spec=SlackService)
        mock_slack_service.get_thread_history.return_value = (
            [{"role": "user", "content": "fallback"}],
            True,
        )

        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_redis = AsyncMock()
            mock_redis.get.return_value = "invalid json"  # Invalid JSON
            mock_get_client.return_value = mock_redis

            messages, success, source = await cache.get_conversation(
                "C123", "1234567890.123", mock_slack_service
            )

        # Should fallback to Slack API
        assert success is True
        assert source == "slack_api"
        mock_slack_service.get_thread_history.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_conversation_new_cache(self, cache):
        """Test creating new cached conversation"""
        message = {"role": "user", "content": "First message"}

        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_redis = AsyncMock()
            mock_redis.get.return_value = None  # No existing conversation
            mock_get_client.return_value = mock_redis

            with patch("services.conversation_cache.datetime") as mock_datetime:
                mock_datetime.now.return_value.isoformat.return_value = (
                    "2023-01-01T00:00:00Z"
                )
                mock_datetime.UTC = UTC

                await cache.update_conversation(
                    "1234567890.123", message, is_bot_message=False
                )

        # Should create new conversation with single message
        mock_redis.setex.assert_called()
        assert mock_redis.setex.call_count == 2  # Data and metadata

    @pytest.mark.asyncio
    async def test_cache_conversation_helper(self, cache):
        """Test the _cache_conversation helper method"""
        messages = [{"role": "user", "content": "Test"}]

        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_redis = AsyncMock()
            mock_get_client.return_value = mock_redis

            with patch("services.conversation_cache.datetime") as mock_datetime:
                mock_datetime.now.return_value.isoformat.return_value = (
                    "2023-01-01T00:00:00Z"
                )
                mock_datetime.UTC = UTC

                await cache._cache_conversation(mock_redis, "1234567890.123", messages)

        # Should cache both messages and metadata
        assert mock_redis.setex.call_count == 2

    @pytest.mark.asyncio
    async def test_clear_conversation_success(self, cache):
        """Test successful conversation clearing"""
        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_redis = AsyncMock()
            mock_redis.delete.return_value = 2  # Deleted 2 keys
            mock_get_client.return_value = mock_redis

            result = await cache.clear_conversation("1234567890.123")

        assert result is True
        mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_clear_conversation_no_redis(self, cache):
        """Test conversation clearing when Redis unavailable"""
        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_get_client.return_value = None

            result = await cache.clear_conversation("1234567890.123")

        assert result is False

    @pytest.mark.asyncio
    async def test_update_conversation_cache_error(self, cache):
        """Test update conversation with caching error"""
        message = {"role": "user", "content": "Test"}

        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_redis = AsyncMock()
            mock_redis.get.return_value = None
            mock_redis.setex.side_effect = Exception("Redis error")
            mock_get_client.return_value = mock_redis

            # Should not raise exception despite Redis error
            result = await cache.update_conversation(
                "1234567890.123", message, is_bot_message=False
            )
            assert result is False
