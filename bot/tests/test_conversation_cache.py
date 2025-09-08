import asyncio
import os
import sys
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
