"""Comprehensive tests for ConversationCache service.

Tests cover:
- Redis connection and health checks
- Conversation caching and retrieval
- Document storage and retrieval
- Summary storage with versioning
- Metadata management
- Cache key generation
- Thread type management
- Error handling and fallbacks
- Cache statistics
"""

import json
import os
import sys
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.conversation_cache import ConversationCache


class TestConversationCacheInitialization:
    """Test ConversationCache initialization."""

    def test_default_initialization(self):
        """Test initialization with default parameters."""
        cache = ConversationCache()

        assert cache.redis_url == "redis://localhost:6379"
        assert cache.ttl == 1800
        assert cache.cache_key_prefix == "slack_conversation:"
        assert cache.redis_client is None
        assert cache._redis_available is None

    def test_custom_initialization(self):
        """Test initialization with custom parameters."""
        cache = ConversationCache(redis_url="redis://custom:6380", ttl=3600)

        assert cache.redis_url == "redis://custom:6380"
        assert cache.ttl == 3600


class TestCacheKeyGeneration:
    """Test cache key generation methods."""

    def test_get_cache_key(self):
        """Test conversation cache key generation."""
        cache = ConversationCache()
        key = cache._get_cache_key("1234.5678")

        assert key == "conversation:1234.5678"

    def test_get_metadata_key(self):
        """Test metadata cache key generation."""
        cache = ConversationCache()
        key = cache._get_metadata_key("1234.5678")

        assert key == "conversation_meta:1234.5678"

    def test_get_document_key(self):
        """Test document cache key generation."""
        cache = ConversationCache()
        key = cache._get_document_key("1234.5678")

        assert key == "conversation_documents:1234.5678"

    def test_get_summary_key_current(self):
        """Test summary key generation for current version."""
        cache = ConversationCache()
        key = cache._get_summary_key("1234.5678")

        assert key == "conversation_summary:1234.5678:current"

    def test_get_summary_key_versioned(self):
        """Test summary key generation for specific version."""
        cache = ConversationCache()
        key = cache._get_summary_key("1234.5678", version=3)

        assert key == "conversation_summary:1234.5678:v3"

    def test_get_summary_history_key(self):
        """Test summary history key generation."""
        cache = ConversationCache()
        key = cache._get_summary_history_key("1234.5678")

        assert key == "conversation_summary:1234.5678:history"


class TestRedisConnection:
    """Test Redis connection management."""

    @pytest.mark.asyncio
    async def test_redis_connection_success(self):
        """Test successful Redis connection."""
        cache = ConversationCache()

        # Mock Redis client
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock()

        with patch("redis.asyncio.from_url", return_value=mock_redis):
            client = await cache._get_redis_client()

            assert client == mock_redis
            assert cache._redis_available is True
            mock_redis.ping.assert_called_once()

    @pytest.mark.asyncio
    async def test_redis_connection_failure(self):
        """Test Redis connection failure handling."""
        cache = ConversationCache()

        with patch(
            "redis.asyncio.from_url", side_effect=Exception("Connection failed")
        ):
            client = await cache._get_redis_client()

            assert client is None
            assert cache._redis_available is False

    @pytest.mark.asyncio
    async def test_redis_connection_cached(self):
        """Test that Redis connection is cached after first call."""
        cache = ConversationCache()

        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock()

        with patch("redis.asyncio.from_url", return_value=mock_redis) as mock_from_url:
            # First call
            client1 = await cache._get_redis_client()
            # Second call
            client2 = await cache._get_redis_client()

            assert client1 == client2
            assert mock_from_url.call_count == 1  # Only called once

    @pytest.mark.asyncio
    async def test_redis_connection_with_config(self):
        """Test Redis connection with correct configuration."""
        cache = ConversationCache(redis_url="redis://test:6379")

        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock()

        with patch("redis.asyncio.from_url", return_value=mock_redis) as mock_from_url:
            await cache._get_redis_client()

            mock_from_url.assert_called_once_with(
                "redis://test:6379",
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
                retry_on_timeout=True,
                health_check_interval=30,
            )


class TestConversationRetrieval:
    """Test conversation retrieval from cache and Slack API."""

    @pytest.mark.asyncio
    async def test_get_conversation_cache_hit(self):
        """Test successful conversation retrieval from cache."""
        cache = ConversationCache()
        mock_redis = AsyncMock()
        mock_slack_service = AsyncMock()

        # Mock cached data
        messages = [{"role": "user", "content": "Hello"}]
        metadata = {"cached_at": datetime.now(UTC).isoformat(), "message_count": 1}

        mock_redis.get = AsyncMock(
            side_effect=[json.dumps(messages), json.dumps(metadata)]
        )
        cache.redis_client = mock_redis
        cache._redis_available = True

        result_messages, success, source = await cache.get_conversation(
            "C123", "1234.5678", mock_slack_service
        )

        assert result_messages == messages
        assert success is True
        assert source == "cache"
        assert mock_redis.get.call_count == 2

    @pytest.mark.asyncio
    async def test_get_conversation_cache_miss_slack_success(self):
        """Test conversation retrieval from Slack API on cache miss."""
        cache = ConversationCache()
        mock_redis = AsyncMock()
        mock_slack_service = AsyncMock()

        # Mock cache miss
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.setex = AsyncMock()
        cache.redis_client = mock_redis
        cache._redis_available = True

        # Mock Slack API success
        messages = [{"role": "user", "content": "Hello from Slack"}]
        mock_slack_service.get_thread_history = AsyncMock(
            return_value=(messages, True)
        )

        result_messages, success, source = await cache.get_conversation(
            "C123", "1234.5678", mock_slack_service
        )

        assert result_messages == messages
        assert success is True
        assert source == "slack_api"
        mock_slack_service.get_thread_history.assert_called_once_with(
            "C123", "1234.5678"
        )

    @pytest.mark.asyncio
    async def test_get_conversation_slack_failure(self):
        """Test conversation retrieval when Slack API fails."""
        cache = ConversationCache()
        mock_redis = AsyncMock()
        mock_slack_service = AsyncMock()

        mock_redis.get = AsyncMock(return_value=None)
        cache.redis_client = mock_redis
        cache._redis_available = True

        # Mock Slack API failure
        mock_slack_service.get_thread_history = AsyncMock(return_value=([], False))

        result_messages, success, source = await cache.get_conversation(
            "C123", "1234.5678", mock_slack_service
        )

        assert result_messages == []
        assert success is False
        assert source == "failed"

    @pytest.mark.asyncio
    async def test_get_conversation_redis_unavailable(self):
        """Test conversation retrieval when Redis is unavailable."""
        cache = ConversationCache()

        mock_slack_service = AsyncMock()
        messages = [{"role": "user", "content": "Hello"}]
        mock_slack_service.get_thread_history = AsyncMock(
            return_value=(messages, True)
        )

        # Mock _get_redis_client to return None
        with patch.object(cache, "_get_redis_client", return_value=None):
            result_messages, success, source = await cache.get_conversation(
                "C123", "1234.5678", mock_slack_service
            )

            assert result_messages == messages
            assert success is True
            assert source == "slack_api"

    @pytest.mark.asyncio
    async def test_get_conversation_cache_retrieval_error(self):
        """Test fallback to Slack API when cache retrieval fails."""
        cache = ConversationCache()
        mock_redis = AsyncMock()
        mock_slack_service = AsyncMock()

        # Mock Redis error
        mock_redis.get = AsyncMock(side_effect=Exception("Redis error"))
        cache.redis_client = mock_redis
        cache._redis_available = True

        # Mock Slack API success
        messages = [{"role": "user", "content": "Hello"}]
        mock_slack_service.get_thread_history = AsyncMock(
            return_value=(messages, True)
        )

        result_messages, success, source = await cache.get_conversation(
            "C123", "1234.5678", mock_slack_service
        )

        assert result_messages == messages
        assert success is True
        assert source == "slack_api"


class TestUpdateConversation:
    """Test conversation cache updates."""

    @pytest.mark.asyncio
    async def test_update_conversation_success(self):
        """Test successful conversation update."""
        cache = ConversationCache()
        mock_redis = AsyncMock()

        # Mock existing conversation
        existing_messages = [{"role": "user", "content": "Hello"}]
        mock_redis.get = AsyncMock(return_value=json.dumps(existing_messages))
        mock_redis.setex = AsyncMock()
        cache.redis_client = mock_redis
        cache._redis_available = True

        new_message = {"role": "assistant", "content": "Hi there"}
        result = await cache.update_conversation("1234.5678", new_message)

        assert result is True
        assert mock_redis.setex.call_count == 2  # Conversation + metadata

    @pytest.mark.asyncio
    async def test_update_conversation_new_thread(self):
        """Test updating conversation when no cache exists."""
        cache = ConversationCache()
        mock_redis = AsyncMock()

        # Mock no existing cache
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.setex = AsyncMock()
        cache.redis_client = mock_redis
        cache._redis_available = True

        new_message = {"role": "user", "content": "First message"}
        result = await cache.update_conversation("1234.5678", new_message)

        assert result is True

    @pytest.mark.asyncio
    async def test_update_conversation_redis_unavailable(self):
        """Test conversation update when Redis is unavailable."""
        cache = ConversationCache()

        # Mock _get_redis_client to return None
        with patch.object(cache, "_get_redis_client", return_value=None):
            new_message = {"role": "user", "content": "Hello"}
            result = await cache.update_conversation("1234.5678", new_message)

            assert result is False

    @pytest.mark.asyncio
    async def test_update_conversation_error(self):
        """Test conversation update error handling."""
        cache = ConversationCache()
        mock_redis = AsyncMock()

        mock_redis.get = AsyncMock(side_effect=Exception("Redis error"))
        cache.redis_client = mock_redis
        cache._redis_available = True

        new_message = {"role": "user", "content": "Hello"}
        result = await cache.update_conversation("1234.5678", new_message)

        assert result is False


class TestDocumentStorage:
    """Test document content storage and retrieval."""

    @pytest.mark.asyncio
    async def test_store_document_content_success(self):
        """Test successful document storage."""
        cache = ConversationCache()
        mock_redis = AsyncMock()
        mock_redis.setex = AsyncMock()
        cache.redis_client = mock_redis
        cache._redis_available = True

        result = await cache.store_document_content(
            "1234.5678", "Document content here", "test.pdf"
        )

        assert result is True
        mock_redis.setex.assert_called_once()

        # Verify the stored data structure
        call_args = mock_redis.setex.call_args
        stored_data = json.loads(call_args[0][2])
        assert stored_data["content"] == "Document content here"
        assert stored_data["filename"] == "test.pdf"
        assert "stored_at" in stored_data

    @pytest.mark.asyncio
    async def test_store_document_content_redis_unavailable(self):
        """Test document storage when Redis is unavailable."""
        cache = ConversationCache()

        # Mock _get_redis_client to return None
        with patch.object(cache, "_get_redis_client", return_value=None):
            result = await cache.store_document_content(
                "1234.5678", "content", "test.pdf"
            )

            assert result is False

    @pytest.mark.asyncio
    async def test_store_document_content_error(self):
        """Test document storage error handling."""
        cache = ConversationCache()
        mock_redis = AsyncMock()
        mock_redis.setex = AsyncMock(side_effect=Exception("Storage error"))
        cache.redis_client = mock_redis
        cache._redis_available = True

        result = await cache.store_document_content(
            "1234.5678", "content", "test.pdf"
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_get_document_content_success(self):
        """Test successful document retrieval."""
        cache = ConversationCache()
        mock_redis = AsyncMock()

        document_data = {
            "content": "Document content",
            "filename": "test.pdf",
            "stored_at": datetime.now(UTC).isoformat(),
        }
        mock_redis.get = AsyncMock(return_value=json.dumps(document_data))
        cache.redis_client = mock_redis
        cache._redis_available = True

        content, filename = await cache.get_document_content("1234.5678")

        assert content == "Document content"
        assert filename == "test.pdf"

    @pytest.mark.asyncio
    async def test_get_document_content_not_found(self):
        """Test document retrieval when not found."""
        cache = ConversationCache()
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        cache.redis_client = mock_redis
        cache._redis_available = True

        content, filename = await cache.get_document_content("1234.5678")

        assert content is None
        assert filename is None

    @pytest.mark.asyncio
    async def test_get_document_content_redis_unavailable(self):
        """Test document retrieval when Redis is unavailable."""
        cache = ConversationCache()

        # Mock _get_redis_client to return None
        with patch.object(cache, "_get_redis_client", return_value=None):
            content, filename = await cache.get_document_content("1234.5678")

            assert content is None
            assert filename is None

    @pytest.mark.asyncio
    async def test_get_document_content_error(self):
        """Test document retrieval error handling."""
        cache = ConversationCache()
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(side_effect=Exception("Retrieval error"))
        cache.redis_client = mock_redis
        cache._redis_available = True

        content, filename = await cache.get_document_content("1234.5678")

        assert content is None
        assert filename is None


class TestSummaryStorage:
    """Test conversation summary storage with versioning."""

    @pytest.mark.asyncio
    async def test_store_summary_first_version(self):
        """Test storing first summary version."""
        cache = ConversationCache()
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)  # No existing history
        mock_redis.setex = AsyncMock()
        cache.redis_client = mock_redis
        cache._redis_available = True

        result = await cache.store_summary(
            "1234.5678",
            "This is a summary",
            message_count=10,
            compressed_from=8,
        )

        assert result is True
        assert mock_redis.setex.call_count == 3  # Current, versioned, history

    @pytest.mark.asyncio
    async def test_store_summary_increments_version(self):
        """Test that summary storage increments version number."""
        cache = ConversationCache()
        mock_redis = AsyncMock()

        # Mock existing history with version 2
        existing_history = {
            "current_version": 2,
            "versions": [{"version": 1, "token_count": 50, "created_at": "2023-01-01"}],
            "updated_at": "2023-01-01",
        }
        mock_redis.get = AsyncMock(return_value=json.dumps(existing_history))
        mock_redis.setex = AsyncMock()
        cache.redis_client = mock_redis
        cache._redis_available = True

        await cache.store_summary("1234.5678", "New summary", message_count=15)

        # Check that version 3 was stored
        call_args_list = [call[0][0] for call in mock_redis.setex.call_args_list]
        assert any("v3" in key for key in call_args_list)

    @pytest.mark.asyncio
    async def test_store_summary_prunes_old_versions(self):
        """Test that old summary versions are pruned."""
        cache = ConversationCache()
        mock_redis = AsyncMock()

        # Mock history with max versions
        existing_versions = [
            {"version": i, "token_count": 50, "created_at": "2023-01-01"}
            for i in range(1, 6)
        ]
        existing_history = {
            "current_version": 5,
            "versions": existing_versions,
            "updated_at": "2023-01-01",
        }
        mock_redis.get = AsyncMock(return_value=json.dumps(existing_history))
        mock_redis.setex = AsyncMock()
        mock_redis.delete = AsyncMock()
        cache.redis_client = mock_redis
        cache._redis_available = True

        await cache.store_summary(
            "1234.5678", "New summary", message_count=20, max_versions=5
        )

        # Should delete oldest version (v1)
        mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_store_summary_redis_unavailable(self):
        """Test summary storage when Redis is unavailable."""
        cache = ConversationCache()

        # Mock _get_redis_client to return None
        with patch.object(cache, "_get_redis_client", return_value=None):
            result = await cache.store_summary("1234.5678", "Summary")

            assert result is False

    @pytest.mark.asyncio
    async def test_store_summary_error(self):
        """Test summary storage error handling."""
        cache = ConversationCache()
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(side_effect=Exception("Storage error"))
        cache.redis_client = mock_redis
        cache._redis_available = True

        result = await cache.store_summary("1234.5678", "Summary")

        assert result is False


class TestSummaryRetrieval:
    """Test conversation summary retrieval."""

    @pytest.mark.asyncio
    async def test_get_summary_current(self):
        """Test retrieving current summary."""
        cache = ConversationCache()
        mock_redis = AsyncMock()

        summary_data = {
            "summary": "Current summary text",
            "version": 3,
            "token_count": 100,
            "message_count": 20,
            "compressed_from_messages": 15,
            "created_at": datetime.now(UTC).isoformat(),
        }
        mock_redis.get = AsyncMock(return_value=json.dumps(summary_data))
        cache.redis_client = mock_redis
        cache._redis_available = True

        summary = await cache.get_summary("1234.5678")

        assert summary == "Current summary text"

    @pytest.mark.asyncio
    async def test_get_summary_specific_version(self):
        """Test retrieving specific summary version."""
        cache = ConversationCache()
        mock_redis = AsyncMock()

        summary_data = {
            "summary": "Version 2 summary",
            "version": 2,
            "token_count": 80,
        }
        mock_redis.get = AsyncMock(return_value=json.dumps(summary_data))
        cache.redis_client = mock_redis
        cache._redis_available = True

        summary = await cache.get_summary("1234.5678", version=2)

        assert summary == "Version 2 summary"
        # Verify correct key was used
        mock_redis.get.assert_called_once_with("conversation_summary:1234.5678:v2")

    @pytest.mark.asyncio
    async def test_get_summary_not_found(self):
        """Test summary retrieval when not found."""
        cache = ConversationCache()
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        cache.redis_client = mock_redis
        cache._redis_available = True

        summary = await cache.get_summary("1234.5678")

        assert summary is None

    @pytest.mark.asyncio
    async def test_get_summary_redis_unavailable(self):
        """Test summary retrieval when Redis is unavailable."""
        cache = ConversationCache()

        # Mock _get_redis_client to return None
        with patch.object(cache, "_get_redis_client", return_value=None):
            summary = await cache.get_summary("1234.5678")

            assert summary is None

    @pytest.mark.asyncio
    async def test_get_summary_error(self):
        """Test summary retrieval error handling."""
        cache = ConversationCache()
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(side_effect=Exception("Retrieval error"))
        cache.redis_client = mock_redis
        cache._redis_available = True

        summary = await cache.get_summary("1234.5678")

        assert summary is None


class TestSummaryMetadata:
    """Test summary metadata retrieval."""

    @pytest.mark.asyncio
    async def test_get_summary_metadata_success(self):
        """Test successful metadata retrieval."""
        cache = ConversationCache()
        mock_redis = AsyncMock()

        summary_data = {
            "summary": "Long summary text here",
            "version": 3,
            "token_count": 100,
            "message_count": 20,
            "compressed_from_messages": 15,
            "created_at": "2023-01-01T00:00:00Z",
        }
        mock_redis.get = AsyncMock(return_value=json.dumps(summary_data))
        cache.redis_client = mock_redis
        cache._redis_available = True

        metadata = await cache.get_summary_metadata("1234.5678")

        assert metadata["version"] == 3
        assert metadata["token_count"] == 100
        assert metadata["message_count"] == 20
        assert metadata["compressed_from_messages"] == 15
        assert metadata["created_at"] == "2023-01-01T00:00:00Z"
        assert metadata["summary_length"] == len("Long summary text here")
        assert "summary" not in metadata  # Summary text excluded

    @pytest.mark.asyncio
    async def test_get_summary_metadata_not_found(self):
        """Test metadata retrieval when not found."""
        cache = ConversationCache()
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        cache.redis_client = mock_redis
        cache._redis_available = True

        metadata = await cache.get_summary_metadata("1234.5678")

        assert metadata is None

    @pytest.mark.asyncio
    async def test_get_summary_metadata_redis_unavailable(self):
        """Test metadata retrieval when Redis is unavailable."""
        cache = ConversationCache()

        # Mock _get_redis_client to return None
        with patch.object(cache, "_get_redis_client", return_value=None):
            metadata = await cache.get_summary_metadata("1234.5678")

            assert metadata is None


class TestSummaryHistory:
    """Test summary version history."""

    @pytest.mark.asyncio
    async def test_get_summary_history_success(self):
        """Test successful history retrieval."""
        cache = ConversationCache()
        mock_redis = AsyncMock()

        history_data = {
            "current_version": 3,
            "versions": [
                {"version": 1, "token_count": 50, "created_at": "2023-01-01"},
                {"version": 2, "token_count": 75, "created_at": "2023-01-02"},
                {"version": 3, "token_count": 100, "created_at": "2023-01-03"},
            ],
            "updated_at": "2023-01-03T00:00:00Z",
        }
        mock_redis.get = AsyncMock(return_value=json.dumps(history_data))
        cache.redis_client = mock_redis
        cache._redis_available = True

        history = await cache.get_summary_history("1234.5678")

        assert history["current_version"] == 3
        assert len(history["versions"]) == 3
        assert history["versions"][0]["version"] == 1

    @pytest.mark.asyncio
    async def test_get_summary_history_not_found(self):
        """Test history retrieval when not found."""
        cache = ConversationCache()
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        cache.redis_client = mock_redis
        cache._redis_available = True

        history = await cache.get_summary_history("1234.5678")

        assert history is None

    @pytest.mark.asyncio
    async def test_get_summary_history_redis_unavailable(self):
        """Test history retrieval when Redis is unavailable."""
        cache = ConversationCache()

        # Mock _get_redis_client to return None
        with patch.object(cache, "_get_redis_client", return_value=None):
            history = await cache.get_summary_history("1234.5678")

            assert history is None


class TestThreadTypeManagement:
    """Test thread type metadata storage and retrieval."""

    @pytest.mark.asyncio
    async def test_set_thread_type_success(self):
        """Test successful thread type storage."""
        cache = ConversationCache()
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)  # No existing metadata
        mock_redis.setex = AsyncMock()
        cache.redis_client = mock_redis
        cache._redis_available = True

        result = await cache.set_thread_type("1234.5678", "profile")

        assert result is True
        mock_redis.setex.assert_called_once()

        # Verify stored data
        call_args = mock_redis.setex.call_args
        stored_data = json.loads(call_args[0][2])
        assert stored_data["thread_type"] == "profile"

    @pytest.mark.asyncio
    async def test_set_thread_type_preserves_existing_metadata(self):
        """Test that thread type storage preserves existing metadata."""
        cache = ConversationCache()
        mock_redis = AsyncMock()

        existing_metadata = {
            "cached_at": "2023-01-01T00:00:00Z",
            "message_count": 5,
        }
        mock_redis.get = AsyncMock(return_value=json.dumps(existing_metadata))
        mock_redis.setex = AsyncMock()
        cache.redis_client = mock_redis
        cache._redis_available = True

        await cache.set_thread_type("1234.5678", "meddic")

        # Verify both old and new data preserved
        call_args = mock_redis.setex.call_args
        stored_data = json.loads(call_args[0][2])
        assert stored_data["thread_type"] == "meddic"
        assert stored_data["cached_at"] == "2023-01-01T00:00:00Z"
        assert stored_data["message_count"] == 5

    @pytest.mark.asyncio
    async def test_set_thread_type_redis_unavailable(self):
        """Test thread type storage when Redis is unavailable."""
        cache = ConversationCache()

        # Mock _get_redis_client to return None
        with patch.object(cache, "_get_redis_client", return_value=None):
            result = await cache.set_thread_type("1234.5678", "profile")

            assert result is False

    @pytest.mark.asyncio
    async def test_set_thread_type_error(self):
        """Test thread type storage error handling."""
        cache = ConversationCache()
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(side_effect=Exception("Storage error"))
        cache.redis_client = mock_redis
        cache._redis_available = True

        result = await cache.set_thread_type("1234.5678", "profile")

        assert result is False

    @pytest.mark.asyncio
    async def test_get_thread_type_success(self):
        """Test successful thread type retrieval."""
        cache = ConversationCache()
        mock_redis = AsyncMock()

        metadata = {"thread_type": "profile", "cached_at": "2023-01-01T00:00:00Z"}
        mock_redis.get = AsyncMock(return_value=json.dumps(metadata))
        cache.redis_client = mock_redis
        cache._redis_available = True

        thread_type = await cache.get_thread_type("1234.5678")

        assert thread_type == "profile"

    @pytest.mark.asyncio
    async def test_get_thread_type_not_found(self):
        """Test thread type retrieval when not set."""
        cache = ConversationCache()
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        cache.redis_client = mock_redis
        cache._redis_available = True

        thread_type = await cache.get_thread_type("1234.5678")

        assert thread_type is None

    @pytest.mark.asyncio
    async def test_get_thread_type_redis_unavailable(self):
        """Test thread type retrieval when Redis is unavailable."""
        cache = ConversationCache()

        # Mock _get_redis_client to return None
        with patch.object(cache, "_get_redis_client", return_value=None):
            thread_type = await cache.get_thread_type("1234.5678")

            assert thread_type is None

    @pytest.mark.asyncio
    async def test_get_thread_type_error(self):
        """Test thread type retrieval error handling."""
        cache = ConversationCache()
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(side_effect=Exception("Retrieval error"))
        cache.redis_client = mock_redis
        cache._redis_available = True

        thread_type = await cache.get_thread_type("1234.5678")

        assert thread_type is None


class TestClearConversation:
    """Test clearing conversation cache."""

    @pytest.mark.asyncio
    async def test_clear_conversation_success(self):
        """Test successful cache clearing."""
        cache = ConversationCache()
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)  # No version history
        mock_redis.delete = AsyncMock(return_value=5)  # 5 keys deleted
        cache.redis_client = mock_redis
        cache._redis_available = True

        result = await cache.clear_conversation("1234.5678")

        assert result is True
        mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_clear_conversation_with_versions(self):
        """Test clearing cache including versioned summaries."""
        cache = ConversationCache()
        mock_redis = AsyncMock()

        # Mock version history
        history_data = {
            "current_version": 3,
            "versions": [
                {"version": 1, "token_count": 50, "created_at": "2023-01-01"},
                {"version": 2, "token_count": 75, "created_at": "2023-01-02"},
                {"version": 3, "token_count": 100, "created_at": "2023-01-03"},
            ],
        }
        mock_redis.get = AsyncMock(return_value=json.dumps(history_data))
        mock_redis.delete = AsyncMock(return_value=8)  # Base + 3 versions
        cache.redis_client = mock_redis
        cache._redis_available = True

        result = await cache.clear_conversation("1234.5678")

        assert result is True
        # Should delete base keys + versioned summaries
        call_args = mock_redis.delete.call_args[0]
        assert len(call_args) == 8  # 5 base keys + 3 versions

    @pytest.mark.asyncio
    async def test_clear_conversation_redis_unavailable(self):
        """Test cache clearing when Redis is unavailable."""
        cache = ConversationCache()

        # Mock _get_redis_client to return None
        with patch.object(cache, "_get_redis_client", return_value=None):
            result = await cache.clear_conversation("1234.5678")

            assert result is False

    @pytest.mark.asyncio
    async def test_clear_conversation_error(self):
        """Test cache clearing error handling."""
        cache = ConversationCache()
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(side_effect=Exception("Delete error"))
        cache.redis_client = mock_redis
        cache._redis_available = True

        result = await cache.clear_conversation("1234.5678")

        assert result is False


class TestCacheStatistics:
    """Test cache statistics retrieval."""

    @pytest.mark.asyncio
    async def test_get_cache_stats_success(self):
        """Test successful stats retrieval."""
        cache = ConversationCache()
        mock_redis = AsyncMock()

        mock_redis.info = AsyncMock(return_value={"used_memory_human": "10.5M"})
        mock_redis.keys = AsyncMock(return_value=["conv1", "conv2", "conv3"])
        cache.redis_client = mock_redis
        cache._redis_available = True

        stats = await cache.get_cache_stats()

        assert stats["status"] == "available"
        assert stats["memory_used"] == "10.5M"
        assert stats["cached_conversations"] == 3
        assert stats["redis_url"] == "redis://localhost:6379"
        assert stats["ttl"] == 1800

    @pytest.mark.asyncio
    async def test_get_cache_stats_redis_unavailable(self):
        """Test stats retrieval when Redis is unavailable."""
        cache = ConversationCache()

        # Mock _get_redis_client to return None
        with patch.object(cache, "_get_redis_client", return_value=None):
            stats = await cache.get_cache_stats()

            assert stats["status"] == "unavailable"

    @pytest.mark.asyncio
    async def test_get_cache_stats_error(self):
        """Test stats retrieval error handling."""
        cache = ConversationCache()
        mock_redis = AsyncMock()
        mock_redis.info = AsyncMock(side_effect=Exception("Stats error"))
        cache.redis_client = mock_redis
        cache._redis_available = True

        stats = await cache.get_cache_stats()

        assert stats["status"] == "error"
        assert "error" in stats


class TestCacheConversationInternal:
    """Test internal cache conversation method."""

    @pytest.mark.asyncio
    async def test_cache_conversation_new(self):
        """Test caching conversation with no existing metadata."""
        cache = ConversationCache()
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)  # No existing metadata
        mock_redis.setex = AsyncMock()

        messages = [{"role": "user", "content": "Hello"}]
        await cache._cache_conversation(mock_redis, "1234.5678", messages)

        assert mock_redis.setex.call_count == 2  # Conversation + metadata

    @pytest.mark.asyncio
    async def test_cache_conversation_preserves_thread_type(self):
        """Test that caching preserves existing thread_type."""
        cache = ConversationCache()
        mock_redis = AsyncMock()

        # Mock existing metadata with thread_type
        existing_metadata = {"thread_type": "profile", "cached_at": "2023-01-01"}
        mock_redis.get = AsyncMock(return_value=json.dumps(existing_metadata))
        mock_redis.setex = AsyncMock()

        messages = [{"role": "user", "content": "Hello"}]
        await cache._cache_conversation(mock_redis, "1234.5678", messages)

        # Verify thread_type was preserved
        meta_call = [call for call in mock_redis.setex.call_args_list if "meta" in call[0][0]][0]
        stored_metadata = json.loads(meta_call[0][2])
        assert stored_metadata["thread_type"] == "profile"

    @pytest.mark.asyncio
    async def test_cache_conversation_handles_invalid_metadata(self):
        """Test caching handles corrupted metadata gracefully."""
        cache = ConversationCache()
        mock_redis = AsyncMock()

        # Mock invalid JSON metadata
        mock_redis.get = AsyncMock(return_value="invalid json")
        mock_redis.setex = AsyncMock()

        messages = [{"role": "user", "content": "Hello"}]
        await cache._cache_conversation(mock_redis, "1234.5678", messages)

        # Should create new metadata without crashing
        assert mock_redis.setex.call_count == 2


class TestCacheAge:
    """Test cache age calculation."""

    def test_get_cache_age_success(self):
        """Test cache age calculation."""
        cache = ConversationCache()

        # Create timestamp now
        past_time = datetime.now(UTC).replace(microsecond=0)
        metadata = {"cached_at": past_time.isoformat()}

        # Calculate age using actual time difference (will be close to 0)
        age = cache._get_cache_age(metadata)

        # Age should be a small positive number (test ran quickly)
        assert isinstance(age, int)
        assert age >= 0
        assert age < 5  # Should be less than 5 seconds

    def test_get_cache_age_with_z_suffix(self):
        """Test cache age calculation with Z suffix."""
        cache = ConversationCache()

        metadata = {"cached_at": "2023-01-01T00:00:00Z"}

        age = cache._get_cache_age(metadata)

        assert isinstance(age, int)
        assert age >= 0

    def test_get_cache_age_error(self):
        """Test cache age calculation error handling."""
        cache = ConversationCache()

        metadata = {"cached_at": "invalid"}

        age = cache._get_cache_age(metadata)

        assert age == 0


class TestClose:
    """Test Redis connection cleanup."""

    @pytest.mark.asyncio
    async def test_close_connection(self):
        """Test closing Redis connection."""
        cache = ConversationCache()
        mock_redis = AsyncMock()
        mock_redis.aclose = AsyncMock()
        cache.redis_client = mock_redis

        await cache.close()

        mock_redis.aclose.assert_called_once()
        assert cache.redis_client is None

    @pytest.mark.asyncio
    async def test_close_no_connection(self):
        """Test closing when no connection exists."""
        cache = ConversationCache()
        cache.redis_client = None

        # Should not raise error
        await cache.close()

        assert cache.redis_client is None
