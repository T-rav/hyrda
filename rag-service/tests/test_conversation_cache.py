"""
Comprehensive tests for conversation cache service.

Tests Redis-based caching for conversations, document storage, summary management,
compression logic, and metadata operations.
"""

import json
import sys
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest

# Mock the SlackService import before importing conversation_cache
sys.modules["services.slack_service"] = Mock()
sys.modules["services.slack_service"].SlackService = Mock()

from services.conversation_cache import ConversationCache


class TestConversationCacheInitialization:
    """Test conversation cache initialization and setup."""

    def test_cache_initialization_with_defaults(self):
        """Test cache can be initialized with default values."""
        cache = ConversationCache()
        assert cache.redis_url == "redis://localhost:6379"
        assert cache.ttl == 1800
        assert cache.cache_key_prefix == "slack_conversation:"
        assert cache.redis_client is None
        assert cache._redis_available is None

    def test_cache_initialization_with_custom_values(self):
        """Test cache initialization with custom redis_url and ttl."""
        cache = ConversationCache(redis_url="redis://custom:6380", ttl=3600)
        assert cache.redis_url == "redis://custom:6380"
        assert cache.ttl == 3600

    def test_cache_initialization_with_short_ttl(self):
        """Test cache initialization with short TTL."""
        cache = ConversationCache(ttl=60)
        assert cache.ttl == 60


class TestCacheKeyGeneration:
    """Test cache key generation methods."""

    def test_get_cache_key(self):
        """Test conversation cache key generation."""
        cache = ConversationCache()
        key = cache._get_cache_key("1234567890.123456")
        assert key == "conversation:1234567890.123456"

    def test_get_metadata_key(self):
        """Test metadata cache key generation."""
        cache = ConversationCache()
        key = cache._get_metadata_key("1234567890.123456")
        assert key == "conversation_meta:1234567890.123456"

    def test_get_document_key(self):
        """Test document cache key generation."""
        cache = ConversationCache()
        key = cache._get_document_key("1234567890.123456")
        assert key == "conversation_documents:1234567890.123456"

    def test_get_summary_key_current(self):
        """Test current summary key generation."""
        cache = ConversationCache()
        key = cache._get_summary_key("1234567890.123456")
        assert key == "conversation_summary:1234567890.123456:current"

    def test_get_summary_key_versioned(self):
        """Test versioned summary key generation."""
        cache = ConversationCache()
        key = cache._get_summary_key("1234567890.123456", version=3)
        assert key == "conversation_summary:1234567890.123456:v3"

    def test_get_summary_key_version_zero(self):
        """Test summary key generation with version 0."""
        cache = ConversationCache()
        key = cache._get_summary_key("1234567890.123456", version=0)
        assert key == "conversation_summary:1234567890.123456:v0"

    def test_get_summary_history_key(self):
        """Test summary history key generation."""
        cache = ConversationCache()
        key = cache._get_summary_history_key("1234567890.123456")
        assert key == "conversation_summary:1234567890.123456:history"


class TestRedisClientConnection:
    """Test Redis client connection and health checks."""

    @pytest.mark.asyncio
    async def test_get_redis_client_success(self):
        """Test successful Redis client connection."""
        cache = ConversationCache()

        with patch("redis.asyncio.from_url") as mock_from_url:
            mock_client = AsyncMock()
            mock_client.ping = AsyncMock()
            mock_from_url.return_value = mock_client

            client = await cache._get_redis_client()

            assert client is not None
            assert cache._redis_available is True
            mock_client.ping.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_redis_client_connection_error(self):
        """Test Redis connection error handling."""
        cache = ConversationCache()

        # Import redis module to use its actual exception types
        import redis.asyncio as redis

        with patch("redis.asyncio.from_url") as mock_from_url:
            mock_client = AsyncMock()
            # Use ConnectionError which is caught by the code
            mock_client.ping = AsyncMock(side_effect=redis.ConnectionError("Connection refused"))
            mock_from_url.return_value = mock_client

            client = await cache._get_redis_client()

            assert client is None
            assert cache._redis_available is False

    @pytest.mark.asyncio
    async def test_get_redis_client_timeout_error(self):
        """Test Redis timeout error handling."""
        cache = ConversationCache()

        with patch("redis.asyncio.from_url") as mock_from_url:
            import redis.asyncio as redis

            mock_client = AsyncMock()
            mock_client.ping = AsyncMock(side_effect=redis.TimeoutError("Timeout"))
            mock_from_url.return_value = mock_client

            client = await cache._get_redis_client()

            assert client is None
            assert cache._redis_available is False

    @pytest.mark.asyncio
    async def test_get_redis_client_cached(self):
        """Test that Redis client is cached after first connection."""
        cache = ConversationCache()

        with patch("redis.asyncio.from_url") as mock_from_url:
            mock_client = AsyncMock()
            mock_client.ping = AsyncMock()
            mock_from_url.return_value = mock_client

            # First call
            client1 = await cache._get_redis_client()
            # Second call should use cached client
            client2 = await cache._get_redis_client()

            assert client1 is client2
            # from_url should only be called once
            assert mock_from_url.call_count == 1


class TestConversationRetrieval:
    """Test conversation history retrieval with cache-first approach."""

    @pytest.mark.asyncio
    async def test_get_conversation_from_cache(self):
        """Test retrieving conversation from cache."""
        cache = ConversationCache()
        mock_slack_service = AsyncMock()

        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        metadata = {"cached_at": datetime.now(UTC).isoformat(), "message_count": 2}

        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(
                side_effect=[
                    json.dumps(messages),  # cached_data
                    json.dumps(metadata),  # cached_meta
                ]
            )
            mock_get_client.return_value = mock_client

            result_messages, success, source = await cache.get_conversation(
                "C123", "1234567890.123456", mock_slack_service
            )

            assert success is True
            assert source == "cache"
            assert len(result_messages) == 2
            assert result_messages[0]["content"] == "Hello"
            # Slack API should not be called
            mock_slack_service.get_thread_history.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_conversation_cache_miss(self):
        """Test falling back to Slack API on cache miss."""
        cache = ConversationCache()
        mock_slack_service = AsyncMock()

        slack_messages = [{"role": "user", "content": "Hello from Slack"}]
        mock_slack_service.get_thread_history = AsyncMock(return_value=(slack_messages, True))

        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=None)  # Cache miss
            mock_client.setex = AsyncMock()
            mock_get_client.return_value = mock_client

            result_messages, success, source = await cache.get_conversation(
                "C123", "1234567890.123456", mock_slack_service
            )

            assert success is True
            assert source == "slack_api"
            assert len(result_messages) == 1
            assert result_messages[0]["content"] == "Hello from Slack"
            mock_slack_service.get_thread_history.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_conversation_slack_api_failure(self):
        """Test handling Slack API failure."""
        cache = ConversationCache()
        mock_slack_service = AsyncMock()
        mock_slack_service.get_thread_history = AsyncMock(return_value=([], False))

        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=None)
            mock_get_client.return_value = mock_client

            result_messages, success, source = await cache.get_conversation(
                "C123", "1234567890.123456", mock_slack_service
            )

            assert success is False
            assert source == "failed"
            assert result_messages == []

    @pytest.mark.asyncio
    async def test_get_conversation_redis_unavailable(self):
        """Test conversation retrieval when Redis is unavailable."""
        cache = ConversationCache()
        mock_slack_service = AsyncMock()

        slack_messages = [{"role": "user", "content": "Hello"}]
        mock_slack_service.get_thread_history = AsyncMock(return_value=(slack_messages, True))

        with patch.object(cache, "_get_redis_client", return_value=None):
            result_messages, success, source = await cache.get_conversation(
                "C123", "1234567890.123456", mock_slack_service
            )

            assert success is True
            assert source == "slack_api"
            mock_slack_service.get_thread_history.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_conversation_caches_slack_result(self):
        """Test that successful Slack API results are cached."""
        cache = ConversationCache()
        mock_slack_service = AsyncMock()

        slack_messages = [{"role": "user", "content": "Hello"}]
        mock_slack_service.get_thread_history = AsyncMock(return_value=(slack_messages, True))

        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=None)
            mock_client.setex = AsyncMock()
            mock_get_client.return_value = mock_client

            with patch.object(cache, "_cache_conversation") as mock_cache:
                await cache.get_conversation("C123", "1234567890.123456", mock_slack_service)

                mock_cache.assert_called_once()


class TestDocumentStorage:
    """Test document content storage and retrieval."""

    @pytest.mark.asyncio
    async def test_store_document_content_success(self):
        """Test storing document content successfully."""
        cache = ConversationCache()

        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.setex = AsyncMock()
            mock_get_client.return_value = mock_client

            result = await cache.store_document_content(
                "1234567890.123456", "Document content here", "report.pdf"
            )

            assert result is True
            mock_client.setex.assert_called_once()
            # Verify the key and data structure
            call_args = mock_client.setex.call_args
            assert "conversation_documents:1234567890.123456" in call_args[0]
            assert cache.ttl in call_args[0]

    @pytest.mark.asyncio
    async def test_store_document_content_redis_unavailable(self):
        """Test storing document when Redis is unavailable."""
        cache = ConversationCache()

        with patch.object(cache, "_get_redis_client", return_value=None):
            result = await cache.store_document_content(
                "1234567890.123456", "Document content", "report.pdf"
            )

            assert result is False

    @pytest.mark.asyncio
    async def test_store_document_content_exception(self):
        """Test handling exception during document storage."""
        cache = ConversationCache()

        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.setex = AsyncMock(side_effect=Exception("Redis error"))
            mock_get_client.return_value = mock_client

            result = await cache.store_document_content(
                "1234567890.123456", "Document content", "report.pdf"
            )

            assert result is False

    @pytest.mark.asyncio
    async def test_get_document_content_success(self):
        """Test retrieving document content successfully."""
        cache = ConversationCache()

        document_data = {
            "content": "Document content here",
            "filename": "report.pdf",
            "stored_at": datetime.now(UTC).isoformat(),
        }

        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=json.dumps(document_data))
            mock_get_client.return_value = mock_client

            content, filename = await cache.get_document_content("1234567890.123456")

            assert content == "Document content here"
            assert filename == "report.pdf"

    @pytest.mark.asyncio
    async def test_get_document_content_not_found(self):
        """Test retrieving document when not found in cache."""
        cache = ConversationCache()

        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=None)
            mock_get_client.return_value = mock_client

            content, filename = await cache.get_document_content("1234567890.123456")

            assert content is None
            assert filename is None

    @pytest.mark.asyncio
    async def test_get_document_content_redis_unavailable(self):
        """Test retrieving document when Redis is unavailable."""
        cache = ConversationCache()

        with patch.object(cache, "_get_redis_client", return_value=None):
            content, filename = await cache.get_document_content("1234567890.123456")

            assert content is None
            assert filename is None


class TestSummaryStorage:
    """Test summary storage with versioning."""

    @pytest.mark.asyncio
    async def test_store_summary_first_version(self):
        """Test storing first summary version."""
        cache = ConversationCache()

        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=None)  # No existing history
            mock_client.setex = AsyncMock()
            mock_get_client.return_value = mock_client

            result = await cache.store_summary(
                "1234567890.123456",
                "This is a summary of the conversation",
                message_count=5,
                compressed_from=10,
            )

            assert result is True
            # Should create current, versioned, and history keys
            assert mock_client.setex.call_count == 3

    @pytest.mark.asyncio
    async def test_store_summary_increments_version(self):
        """Test that summary versions increment correctly."""
        cache = ConversationCache()

        existing_history = {
            "current_version": 2,
            "versions": [
                {"version": 1, "token_count": 100, "created_at": "2024-01-01T00:00:00Z"},
                {"version": 2, "token_count": 150, "created_at": "2024-01-02T00:00:00Z"},
            ],
        }

        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=json.dumps(existing_history))
            mock_client.setex = AsyncMock()
            mock_client.delete = AsyncMock()
            mock_get_client.return_value = mock_client

            result = await cache.store_summary(
                "1234567890.123456", "Updated summary", message_count=8, compressed_from=15
            )

            assert result is True
            # Verify new version is 3
            history_call = [
                call for call in mock_client.setex.call_args_list if "history" in str(call)
            ]
            assert len(history_call) > 0

    @pytest.mark.asyncio
    async def test_store_summary_respects_max_versions(self):
        """Test that old versions are deleted when exceeding max_versions."""
        cache = ConversationCache()

        # Create history with 5 versions (at max)
        existing_history = {
            "current_version": 5,
            "versions": [
                {"version": i, "token_count": 100, "created_at": "2024-01-01T00:00:00Z"}
                for i in range(1, 6)
            ],
        }

        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=json.dumps(existing_history))
            mock_client.setex = AsyncMock()
            mock_client.delete = AsyncMock()
            mock_get_client.return_value = mock_client

            result = await cache.store_summary(
                "1234567890.123456",
                "Sixth summary",
                message_count=10,
                compressed_from=20,
                max_versions=5,
            )

            assert result is True
            # Should delete the oldest version (version 1)
            mock_client.delete.assert_called_once()
            delete_key = mock_client.delete.call_args[0][0]
            assert "v1" in delete_key

    @pytest.mark.asyncio
    async def test_store_summary_token_count_estimation(self):
        """Test that token count is estimated correctly."""
        cache = ConversationCache()

        summary_text = "A" * 400  # 400 characters should be ~100 tokens

        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=None)
            mock_client.setex = AsyncMock()
            mock_get_client.return_value = mock_client

            await cache.store_summary("1234567890.123456", summary_text)

            # Find the setex call with summary data
            for call in mock_client.setex.call_args_list:
                if "current" in str(call[0][0]):
                    data = json.loads(call[0][2])
                    # 400 chars / 4 = 100 tokens
                    assert data["token_count"] == 100
                    break

    @pytest.mark.asyncio
    async def test_store_summary_redis_unavailable(self):
        """Test storing summary when Redis is unavailable."""
        cache = ConversationCache()

        with patch.object(cache, "_get_redis_client", return_value=None):
            result = await cache.store_summary("1234567890.123456", "Summary text")
            assert result is False


class TestSummaryRetrieval:
    """Test summary retrieval."""

    @pytest.mark.asyncio
    async def test_get_summary_current_version(self):
        """Test retrieving current summary version."""
        cache = ConversationCache()

        summary_data = {
            "summary": "Current conversation summary",
            "version": 3,
            "token_count": 120,
            "message_count": 7,
            "compressed_from_messages": 12,
            "created_at": datetime.now(UTC).isoformat(),
        }

        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=json.dumps(summary_data))
            mock_get_client.return_value = mock_client

            summary = await cache.get_summary("1234567890.123456")

            assert summary == "Current conversation summary"

    @pytest.mark.asyncio
    async def test_get_summary_specific_version(self):
        """Test retrieving specific summary version."""
        cache = ConversationCache()

        summary_data = {
            "summary": "Version 2 summary",
            "version": 2,
            "token_count": 100,
            "message_count": 5,
            "compressed_from_messages": 8,
            "created_at": datetime.now(UTC).isoformat(),
        }

        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=json.dumps(summary_data))
            mock_get_client.return_value = mock_client

            summary = await cache.get_summary("1234567890.123456", version=2)

            assert summary == "Version 2 summary"
            # Verify correct key was used
            mock_client.get.assert_called_once()
            key_used = mock_client.get.call_args[0][0]
            assert "v2" in key_used

    @pytest.mark.asyncio
    async def test_get_summary_not_found(self):
        """Test retrieving summary that doesn't exist."""
        cache = ConversationCache()

        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=None)
            mock_get_client.return_value = mock_client

            summary = await cache.get_summary("1234567890.123456")

            assert summary is None

    @pytest.mark.asyncio
    async def test_get_summary_redis_unavailable(self):
        """Test retrieving summary when Redis is unavailable."""
        cache = ConversationCache()

        with patch.object(cache, "_get_redis_client", return_value=None):
            summary = await cache.get_summary("1234567890.123456")
            assert summary is None


class TestSummaryMetadata:
    """Test summary metadata operations."""

    @pytest.mark.asyncio
    async def test_get_summary_metadata_success(self):
        """Test retrieving summary metadata."""
        cache = ConversationCache()

        summary_data = {
            "summary": "Full summary text that we don't want",
            "version": 2,
            "token_count": 150,
            "message_count": 8,
            "compressed_from_messages": 15,
            "created_at": "2024-01-15T10:30:00Z",
        }

        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=json.dumps(summary_data))
            mock_get_client.return_value = mock_client

            metadata = await cache.get_summary_metadata("1234567890.123456")

            assert metadata is not None
            assert metadata["version"] == 2
            assert metadata["token_count"] == 150
            assert metadata["message_count"] == 8
            assert metadata["compressed_from_messages"] == 15
            assert "summary" not in metadata  # Should not include full summary
            assert metadata["summary_length"] == len("Full summary text that we don't want")

    @pytest.mark.asyncio
    async def test_get_summary_metadata_not_found(self):
        """Test retrieving metadata when summary doesn't exist."""
        cache = ConversationCache()

        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=None)
            mock_get_client.return_value = mock_client

            metadata = await cache.get_summary_metadata("1234567890.123456")
            assert metadata is None

    @pytest.mark.asyncio
    async def test_get_summary_history_success(self):
        """Test retrieving summary version history."""
        cache = ConversationCache()

        history_data = {
            "current_version": 3,
            "versions": [
                {"version": 1, "token_count": 100, "created_at": "2024-01-01T00:00:00Z"},
                {"version": 2, "token_count": 120, "created_at": "2024-01-02T00:00:00Z"},
                {"version": 3, "token_count": 140, "created_at": "2024-01-03T00:00:00Z"},
            ],
            "updated_at": "2024-01-03T00:00:00Z",
        }

        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=json.dumps(history_data))
            mock_get_client.return_value = mock_client

            history = await cache.get_summary_history("1234567890.123456")

            assert history is not None
            assert history["current_version"] == 3
            assert len(history["versions"]) == 3

    @pytest.mark.asyncio
    async def test_get_summary_history_not_found(self):
        """Test retrieving history when it doesn't exist."""
        cache = ConversationCache()

        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=None)
            mock_get_client.return_value = mock_client

            history = await cache.get_summary_history("1234567890.123456")
            assert history is None


class TestConversationUpdate:
    """Test updating cached conversations."""

    @pytest.mark.asyncio
    async def test_update_conversation_with_existing_cache(self):
        """Test updating conversation with existing cached messages."""
        cache = ConversationCache()

        existing_messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"},
        ]
        new_message = {"role": "user", "content": "How are you?"}

        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=json.dumps(existing_messages))
            mock_client.setex = AsyncMock()
            mock_get_client.return_value = mock_client

            with patch.object(cache, "_cache_conversation") as mock_cache:
                result = await cache.update_conversation("1234567890.123456", new_message)

                assert result is True
                # Verify _cache_conversation was called with updated messages
                mock_cache.assert_called_once()
                call_messages = mock_cache.call_args[0][2]
                assert len(call_messages) == 3
                assert call_messages[-1]["content"] == "How are you?"

    @pytest.mark.asyncio
    async def test_update_conversation_no_existing_cache(self):
        """Test updating conversation when no cache exists."""
        cache = ConversationCache()

        new_message = {"role": "user", "content": "First message"}

        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=None)
            mock_client.setex = AsyncMock()
            mock_get_client.return_value = mock_client

            with patch.object(cache, "_cache_conversation") as mock_cache:
                result = await cache.update_conversation("1234567890.123456", new_message)

                assert result is True
                call_messages = mock_cache.call_args[0][2]
                assert len(call_messages) == 1
                assert call_messages[0]["content"] == "First message"

    @pytest.mark.asyncio
    async def test_update_conversation_redis_unavailable(self):
        """Test updating conversation when Redis is unavailable."""
        cache = ConversationCache()

        with patch.object(cache, "_get_redis_client", return_value=None):
            result = await cache.update_conversation(
                "1234567890.123456", {"role": "user", "content": "Test"}
            )
            assert result is False

    @pytest.mark.asyncio
    async def test_update_conversation_with_bot_message(self):
        """Test updating conversation with bot message flag."""
        cache = ConversationCache()

        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=None)
            mock_client.setex = AsyncMock()
            mock_get_client.return_value = mock_client

            with patch.object(cache, "_cache_conversation"):
                result = await cache.update_conversation(
                    "1234567890.123456",
                    {"role": "assistant", "content": "Bot response"},
                    is_bot_message=True,
                )
                assert result is True


class TestCacheConversation:
    """Test internal conversation caching method."""

    @pytest.mark.asyncio
    async def test_cache_conversation_new_metadata(self):
        """Test caching conversation with new metadata."""
        cache = ConversationCache(ttl=3600)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=None)  # No existing metadata
        mock_client.setex = AsyncMock()

        messages = [{"role": "user", "content": "Hello"}, {"role": "assistant", "content": "Hi!"}]

        await cache._cache_conversation(mock_client, "1234567890.123456", messages)

        # Should call setex twice: once for messages, once for metadata
        assert mock_client.setex.call_count == 2

        # Verify metadata structure
        meta_call = [
            call for call in mock_client.setex.call_args_list if "meta" in str(call[0][0])
        ][0]
        metadata = json.loads(meta_call[0][2])
        assert metadata["message_count"] == 2
        assert "cached_at" in metadata
        assert metadata["ttl"] == 3600

    @pytest.mark.asyncio
    async def test_cache_conversation_preserves_existing_metadata(self):
        """Test that caching preserves existing metadata fields."""
        cache = ConversationCache()

        existing_metadata = {"thread_type": "profile", "user_id": "U123", "custom_field": "value"}

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=json.dumps(existing_metadata))
        mock_client.setex = AsyncMock()

        messages = [{"role": "user", "content": "Test"}]

        await cache._cache_conversation(mock_client, "1234567890.123456", messages)

        # Find metadata setex call
        meta_call = [
            call for call in mock_client.setex.call_args_list if "meta" in str(call[0][0])
        ][0]
        metadata = json.loads(meta_call[0][2])

        # Should preserve existing fields
        assert metadata["thread_type"] == "profile"
        assert metadata["user_id"] == "U123"
        assert metadata["custom_field"] == "value"
        # And add new cache info
        assert "cached_at" in metadata
        assert metadata["message_count"] == 1

    @pytest.mark.asyncio
    async def test_cache_conversation_handles_invalid_existing_metadata(self):
        """Test handling invalid existing metadata."""
        cache = ConversationCache()

        mock_client = AsyncMock()
        # Return invalid JSON that will cause decode error
        mock_client.get = AsyncMock(return_value="invalid json")
        mock_client.setex = AsyncMock()

        messages = [{"role": "user", "content": "Test"}]

        # Should not raise, should create new metadata
        await cache._cache_conversation(mock_client, "1234567890.123456", messages)

        assert mock_client.setex.call_count == 2


class TestCacheAge:
    """Test cache age calculation."""

    def test_get_cache_age_recent(self):
        """Test calculating age for recent cache."""
        cache = ConversationCache()

        recent_time = datetime.now(UTC) - timedelta(seconds=30)
        metadata = {"cached_at": recent_time.isoformat()}

        age = cache._get_cache_age(metadata)
        assert 25 <= age <= 35  # Should be around 30 seconds

    def test_get_cache_age_old(self):
        """Test calculating age for old cache."""
        cache = ConversationCache()

        old_time = datetime.now(UTC) - timedelta(hours=2)
        metadata = {"cached_at": old_time.isoformat()}

        age = cache._get_cache_age(metadata)
        assert 7000 <= age <= 7400  # Around 2 hours (7200 seconds)

    def test_get_cache_age_with_z_suffix(self):
        """Test handling timestamp with Z suffix."""
        cache = ConversationCache()

        time_with_z = datetime.now(UTC) - timedelta(minutes=5)
        # Add Z suffix instead of +00:00
        timestamp = time_with_z.isoformat().replace("+00:00", "Z")
        metadata = {"cached_at": timestamp}

        age = cache._get_cache_age(metadata)
        assert 290 <= age <= 310  # Around 5 minutes (300 seconds)

    def test_get_cache_age_invalid_timestamp(self):
        """Test handling invalid timestamp."""
        cache = ConversationCache()

        metadata = {"cached_at": "invalid-timestamp"}
        age = cache._get_cache_age(metadata)
        assert age == 0

    def test_get_cache_age_missing_field(self):
        """Test handling missing cached_at field."""
        cache = ConversationCache()

        metadata = {"message_count": 5}
        age = cache._get_cache_age(metadata)
        assert age == 0


class TestClearConversation:
    """Test clearing conversation cache."""

    @pytest.mark.asyncio
    async def test_clear_conversation_all_keys(self):
        """Test clearing all conversation-related keys."""
        cache = ConversationCache()

        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=None)  # No version history
            mock_client.delete = AsyncMock(return_value=5)
            mock_get_client.return_value = mock_client

            result = await cache.clear_conversation("1234567890.123456")

            assert result is True
            # Should delete: cache, meta, document, summary, history
            mock_client.delete.assert_called_once()
            deleted_keys = mock_client.delete.call_args[0]
            assert len(deleted_keys) == 5

    @pytest.mark.asyncio
    async def test_clear_conversation_with_versions(self):
        """Test clearing conversation with multiple summary versions."""
        cache = ConversationCache()

        history_data = {
            "current_version": 3,
            "versions": [
                {"version": 1, "token_count": 100, "created_at": "2024-01-01T00:00:00Z"},
                {"version": 2, "token_count": 120, "created_at": "2024-01-02T00:00:00Z"},
                {"version": 3, "token_count": 140, "created_at": "2024-01-03T00:00:00Z"},
            ],
        }

        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=json.dumps(history_data))
            mock_client.delete = AsyncMock(return_value=8)
            mock_get_client.return_value = mock_client

            result = await cache.clear_conversation("1234567890.123456")

            assert result is True
            # Should delete: 5 base keys + 3 versioned summaries
            deleted_keys = mock_client.delete.call_args[0]
            assert len(deleted_keys) == 8

    @pytest.mark.asyncio
    async def test_clear_conversation_redis_unavailable(self):
        """Test clearing conversation when Redis is unavailable."""
        cache = ConversationCache()

        with patch.object(cache, "_get_redis_client", return_value=None):
            result = await cache.clear_conversation("1234567890.123456")
            assert result is False

    @pytest.mark.asyncio
    async def test_clear_conversation_exception(self):
        """Test handling exception during clear."""
        cache = ConversationCache()

        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=Exception("Redis error"))
            mock_get_client.return_value = mock_client

            result = await cache.clear_conversation("1234567890.123456")
            assert result is False


class TestThreadType:
    """Test thread type metadata management."""

    @pytest.mark.asyncio
    async def test_set_thread_type_success(self):
        """Test setting thread type successfully."""
        cache = ConversationCache()

        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=None)
            mock_client.setex = AsyncMock()
            mock_get_client.return_value = mock_client

            result = await cache.set_thread_type("1234567890.123456", "profile")

            assert result is True
            mock_client.setex.assert_called_once()
            # Verify metadata contains thread_type
            call_data = json.loads(mock_client.setex.call_args[0][2])
            assert call_data["thread_type"] == "profile"

    @pytest.mark.asyncio
    async def test_set_thread_type_updates_existing(self):
        """Test updating thread type in existing metadata."""
        cache = ConversationCache()

        existing_metadata = {"cached_at": "2024-01-01T00:00:00Z", "message_count": 5}

        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=json.dumps(existing_metadata))
            mock_client.setex = AsyncMock()
            mock_get_client.return_value = mock_client

            result = await cache.set_thread_type("1234567890.123456", "meddic")

            assert result is True
            call_data = json.loads(mock_client.setex.call_args[0][2])
            assert call_data["thread_type"] == "meddic"
            assert call_data["message_count"] == 5  # Preserved

    @pytest.mark.asyncio
    async def test_set_thread_type_redis_unavailable(self):
        """Test setting thread type when Redis is unavailable."""
        cache = ConversationCache()

        with patch.object(cache, "_get_redis_client", return_value=None):
            result = await cache.set_thread_type("1234567890.123456", "profile")
            assert result is False

    @pytest.mark.asyncio
    async def test_get_thread_type_success(self):
        """Test retrieving thread type successfully."""
        cache = ConversationCache()

        metadata = {"thread_type": "profile", "cached_at": "2024-01-01T00:00:00Z"}

        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=json.dumps(metadata))
            mock_get_client.return_value = mock_client

            thread_type = await cache.get_thread_type("1234567890.123456")

            assert thread_type == "profile"

    @pytest.mark.asyncio
    async def test_get_thread_type_not_set(self):
        """Test retrieving thread type when not set."""
        cache = ConversationCache()

        metadata = {"cached_at": "2024-01-01T00:00:00Z"}

        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=json.dumps(metadata))
            mock_get_client.return_value = mock_client

            thread_type = await cache.get_thread_type("1234567890.123456")

            assert thread_type is None

    @pytest.mark.asyncio
    async def test_get_thread_type_no_metadata(self):
        """Test retrieving thread type when no metadata exists."""
        cache = ConversationCache()

        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=None)
            mock_get_client.return_value = mock_client

            thread_type = await cache.get_thread_type("1234567890.123456")

            assert thread_type is None

    @pytest.mark.asyncio
    async def test_get_thread_type_redis_unavailable(self):
        """Test retrieving thread type when Redis is unavailable."""
        cache = ConversationCache()

        with patch.object(cache, "_get_redis_client", return_value=None):
            thread_type = await cache.get_thread_type("1234567890.123456")
            assert thread_type is None


class TestCacheStats:
    """Test cache statistics."""

    @pytest.mark.asyncio
    async def test_get_cache_stats_success(self):
        """Test retrieving cache statistics successfully."""
        cache = ConversationCache(redis_url="redis://test:6379", ttl=1800)

        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.info = AsyncMock(return_value={"used_memory_human": "2.5M"})
            mock_client.keys = AsyncMock(return_value=["conversation:123", "conversation:456"])
            mock_get_client.return_value = mock_client

            stats = await cache.get_cache_stats()

            assert stats["status"] == "available"
            assert stats["memory_used"] == "2.5M"
            assert stats["cached_conversations"] == 2
            assert stats["redis_url"] == "redis://test:6379"
            assert stats["ttl"] == 1800

    @pytest.mark.asyncio
    async def test_get_cache_stats_redis_unavailable(self):
        """Test retrieving stats when Redis is unavailable."""
        cache = ConversationCache()

        with patch.object(cache, "_get_redis_client", return_value=None):
            stats = await cache.get_cache_stats()

            assert stats["status"] == "unavailable"

    @pytest.mark.asyncio
    async def test_get_cache_stats_exception(self):
        """Test handling exception when retrieving stats."""
        cache = ConversationCache()

        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.info = AsyncMock(side_effect=Exception("Connection error"))
            mock_get_client.return_value = mock_client

            stats = await cache.get_cache_stats()

            assert stats["status"] == "error"
            assert "error" in stats


class TestClose:
    """Test closing Redis connection."""

    @pytest.mark.asyncio
    async def test_close_connection(self):
        """Test closing Redis connection."""
        cache = ConversationCache()

        mock_client = AsyncMock()
        cache.redis_client = mock_client

        await cache.close()

        mock_client.aclose.assert_called_once()
        assert cache.redis_client is None

    @pytest.mark.asyncio
    async def test_close_no_connection(self):
        """Test closing when no connection exists."""
        cache = ConversationCache()

        # Should not raise
        await cache.close()

        assert cache.redis_client is None
