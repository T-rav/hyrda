"""
Tests for conversation summary storage with metadata and versioning.

Tests the new structured summary storage features added to ConversationCache.
"""

import json
import os
import sys
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

# Add the parent directory to sys.path to allow importing the module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.conversation_cache import ConversationCache


class TestConversationSummaryStorage:
    """Tests for structured summary storage with metadata"""

    @pytest.fixture
    def cache(self):
        """Create real ConversationCache instance for testing"""
        return ConversationCache(redis_url="redis://localhost:6379", ttl=1800)

    @pytest.fixture
    def mock_redis(self):
        """Create a mock Redis client"""
        mock_redis = AsyncMock()
        mock_redis.ping.return_value = "PONG"
        mock_redis.get.return_value = None
        mock_redis.setex.return_value = True
        mock_redis.delete.return_value = 1
        return mock_redis

    @pytest.mark.asyncio
    async def test_store_summary_with_metadata(self, cache, mock_redis):
        """Test storing summary with structured metadata"""
        thread_ts = "1234567890.123"
        summary = "This is a test summary of the conversation"
        message_count = 5
        compressed_from = 20

        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_get_client.return_value = mock_redis
            mock_redis.get.return_value = None  # No existing history

            with patch("services.conversation_cache.datetime") as mock_datetime:
                mock_datetime.now.return_value = datetime(
                    2023, 1, 1, 12, 0, 0, tzinfo=UTC
                )
                mock_datetime.UTC = UTC

                result = await cache.store_summary(
                    thread_ts=thread_ts,
                    summary=summary,
                    message_count=message_count,
                    compressed_from=compressed_from,
                )

        assert result is True
        # Should store both current summary and versioned summary and history
        assert mock_redis.setex.call_count == 3

        # Verify the stored data structure
        calls = mock_redis.setex.call_args_list
        for call in calls:
            key, ttl, data_str = call[0]
            data = json.loads(data_str)

            if "current" in key:
                # Current summary should have all metadata
                assert data["summary"] == summary
                assert data["version"] == 1
                assert data["token_count"] == len(summary) // 4
                assert data["message_count"] == message_count
                assert data["compressed_from_messages"] == compressed_from
                assert "created_at" in data

    @pytest.mark.asyncio
    async def test_store_summary_no_redis(self, cache):
        """Test storing summary when Redis is unavailable"""
        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_get_client.return_value = None

            result = await cache.store_summary(
                thread_ts="1234567890.123", summary="test summary"
            )

        assert result is False

    @pytest.mark.asyncio
    async def test_get_summary_with_metadata(self, cache, mock_redis):
        """Test retrieving summary returns correct text"""
        thread_ts = "1234567890.123"
        summary_text = "This is a test summary"
        summary_data = {
            "summary": summary_text,
            "version": 1,
            "token_count": 100,
            "message_count": 5,
            "compressed_from_messages": 20,
            "created_at": "2023-01-01T12:00:00Z",
        }

        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_redis.get.return_value = json.dumps(summary_data)
            mock_get_client.return_value = mock_redis

            result = await cache.get_summary(thread_ts)

        assert result == summary_text
        mock_redis.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_summary_not_found(self, cache, mock_redis):
        """Test retrieving non-existent summary returns None"""
        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_redis.get.return_value = None
            mock_get_client.return_value = mock_redis

            result = await cache.get_summary("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_summary_no_redis(self, cache):
        """Test retrieving summary when Redis is unavailable"""
        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_get_client.return_value = None

            result = await cache.get_summary("1234567890.123")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_summary_metadata(self, cache, mock_redis):
        """Test retrieving summary metadata without full text"""
        thread_ts = "1234567890.123"
        summary_data = {
            "summary": "This is a long summary that we don't want to return",
            "version": 2,
            "token_count": 150,
            "message_count": 7,
            "compressed_from_messages": 25,
            "created_at": "2023-01-01T12:00:00Z",
        }

        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_redis.get.return_value = json.dumps(summary_data)
            mock_get_client.return_value = mock_redis

            metadata = await cache.get_summary_metadata(thread_ts)

        assert metadata is not None
        assert metadata["version"] == 2
        assert metadata["token_count"] == 150
        assert metadata["message_count"] == 7
        assert metadata["compressed_from_messages"] == 25
        assert metadata["created_at"] == "2023-01-01T12:00:00Z"
        assert metadata["summary_length"] == len(summary_data["summary"])
        # Verify summary text is NOT included
        assert "summary" not in metadata

    @pytest.mark.asyncio
    async def test_get_summary_metadata_not_found(self, cache, mock_redis):
        """Test retrieving metadata for non-existent summary"""
        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_redis.get.return_value = None
            mock_get_client.return_value = mock_redis

            metadata = await cache.get_summary_metadata("nonexistent")

        assert metadata is None


class TestConversationSummaryVersioning:
    """Tests for summary versioning and history"""

    @pytest.fixture
    def cache(self):
        """Create real ConversationCache instance for testing"""
        return ConversationCache(redis_url="redis://localhost:6379", ttl=1800)

    @pytest.fixture
    def mock_redis(self):
        """Create a mock Redis client"""
        mock_redis = AsyncMock()
        mock_redis.ping.return_value = "PONG"
        mock_redis.get.return_value = None
        mock_redis.setex.return_value = True
        mock_redis.delete.return_value = 1
        return mock_redis

    @pytest.mark.asyncio
    async def test_store_multiple_versions(self, cache, mock_redis):
        """Test storing multiple summary versions"""
        thread_ts = "1234567890.123"

        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_get_client.return_value = mock_redis

            with patch("services.conversation_cache.datetime") as mock_datetime:
                mock_datetime.UTC = UTC

                # Store first version
                mock_redis.get.return_value = None  # No existing history
                mock_datetime.now.return_value = datetime(
                    2023, 1, 1, 12, 0, 0, tzinfo=UTC
                )
                await cache.store_summary(thread_ts, "Summary version 1", 5, 20)

                # Store second version
                history_v1 = {
                    "current_version": 1,
                    "versions": [
                        {
                            "version": 1,
                            "token_count": 5,
                            "created_at": "2023-01-01T12:00:00+00:00",
                        }
                    ],
                    "updated_at": "2023-01-01T12:00:00+00:00",
                }
                # Mock get to return None for first call (summary lookup), then history for second call
                mock_redis.get.side_effect = [None, json.dumps(history_v1)]
                mock_datetime.now.return_value = datetime(
                    2023, 1, 1, 13, 0, 0, tzinfo=UTC
                )
                await cache.store_summary(thread_ts, "Summary version 2", 6, 22)

        # Each store_summary makes 3 setex calls (current, versioned, history)
        assert mock_redis.setex.call_count == 6  # 3 calls per version

    @pytest.mark.asyncio
    async def test_get_specific_version(self, cache, mock_redis):
        """Test retrieving a specific summary version"""
        thread_ts = "1234567890.123"
        version = 2
        summary_data = {
            "summary": "This is version 2",
            "version": 2,
            "token_count": 50,
            "message_count": 10,
            "compressed_from_messages": 30,
            "created_at": "2023-01-01T13:00:00Z",
        }

        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_redis.get.return_value = json.dumps(summary_data)
            mock_get_client.return_value = mock_redis

            result = await cache.get_summary(thread_ts, version=version)

        assert result == "This is version 2"
        # Verify correct key was requested
        expected_key = f"conversation_summary:{thread_ts}:v{version}"
        mock_redis.get.assert_called_once_with(expected_key)

    @pytest.mark.asyncio
    async def test_version_limit_cleanup(self, cache, mock_redis):
        """Test that old versions are cleaned up when exceeding max_versions"""
        thread_ts = "1234567890.123"
        max_versions = 3

        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_get_client.return_value = mock_redis

            with patch("services.conversation_cache.datetime") as mock_datetime:
                mock_datetime.UTC = UTC

                # Create history with 3 existing versions
                existing_history = {
                    "current_version": 3,
                    "versions": [
                        {
                            "version": 1,
                            "token_count": 10,
                            "created_at": "2023-01-01T10:00:00+00:00",
                        },
                        {
                            "version": 2,
                            "token_count": 20,
                            "created_at": "2023-01-01T11:00:00+00:00",
                        },
                        {
                            "version": 3,
                            "token_count": 30,
                            "created_at": "2023-01-01T12:00:00+00:00",
                        },
                    ],
                    "updated_at": "2023-01-01T12:00:00+00:00",
                }

                mock_redis.get.return_value = json.dumps(existing_history)
                mock_datetime.now.return_value = datetime(
                    2023, 1, 1, 13, 0, 0, tzinfo=UTC
                )

                # Store 4th version (should trigger cleanup)
                await cache.store_summary(
                    thread_ts, "Summary version 4", 8, 28, max_versions=max_versions
                )

        # Should delete old version 1
        mock_redis.delete.assert_called_once()
        delete_key = mock_redis.delete.call_args[0][0]
        assert delete_key == f"conversation_summary:{thread_ts}:v1"

    @pytest.mark.asyncio
    async def test_get_summary_history(self, cache, mock_redis):
        """Test retrieving summary version history"""
        thread_ts = "1234567890.123"
        history_data = {
            "current_version": 3,
            "versions": [
                {
                    "version": 1,
                    "token_count": 100,
                    "created_at": "2023-01-01T10:00:00Z",
                },
                {
                    "version": 2,
                    "token_count": 120,
                    "created_at": "2023-01-01T11:00:00Z",
                },
                {
                    "version": 3,
                    "token_count": 110,
                    "created_at": "2023-01-01T12:00:00Z",
                },
            ],
            "updated_at": "2023-01-01T12:00:00Z",
        }

        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_redis.get.return_value = json.dumps(history_data)
            mock_get_client.return_value = mock_redis

            history = await cache.get_summary_history(thread_ts)

        assert history is not None
        assert history["current_version"] == 3
        assert len(history["versions"]) == 3
        assert history["versions"][0]["version"] == 1
        assert history["versions"][2]["version"] == 3

    @pytest.mark.asyncio
    async def test_get_summary_history_not_found(self, cache, mock_redis):
        """Test retrieving history for thread with no summaries"""
        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_redis.get.return_value = None
            mock_get_client.return_value = mock_redis

            history = await cache.get_summary_history("nonexistent")

        assert history is None

    @pytest.mark.asyncio
    async def test_clear_conversation_removes_all_versions(self, cache, mock_redis):
        """Test that clearing conversation deletes all summary versions"""
        thread_ts = "1234567890.123"
        history_data = {
            "current_version": 3,
            "versions": [
                {
                    "version": 1,
                    "token_count": 100,
                    "created_at": "2023-01-01T10:00:00Z",
                },
                {
                    "version": 2,
                    "token_count": 120,
                    "created_at": "2023-01-01T11:00:00Z",
                },
                {
                    "version": 3,
                    "token_count": 110,
                    "created_at": "2023-01-01T12:00:00Z",
                },
            ],
        }

        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_redis.get.return_value = json.dumps(history_data)
            mock_get_client.return_value = mock_redis

            result = await cache.clear_conversation(thread_ts)

        assert result is True
        # Should delete base keys (5) + versioned summaries (3) = 8 keys total
        delete_call = mock_redis.delete.call_args[0]
        assert len(delete_call) == 8  # 5 base + 3 versions

    @pytest.mark.asyncio
    async def test_clear_conversation_no_versions(self, cache, mock_redis):
        """Test clearing conversation with no summary versions"""
        thread_ts = "1234567890.123"

        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_redis.get.return_value = None  # No history
            mock_redis.delete.return_value = 5
            mock_get_client.return_value = mock_redis

            result = await cache.clear_conversation(thread_ts)

        assert result is True
        # Should delete only base keys (no versioned summaries)
        delete_call = mock_redis.delete.call_args[0]
        assert len(delete_call) == 5


class TestConversationSummaryEdgeCases:
    """Edge case tests for summary storage"""

    @pytest.fixture
    def cache(self):
        return ConversationCache(redis_url="redis://localhost:6379", ttl=1800)

    @pytest.fixture
    def mock_redis(self):
        mock_redis = AsyncMock()
        mock_redis.ping.return_value = "PONG"
        mock_redis.get.return_value = None
        mock_redis.setex.return_value = True
        mock_redis.delete.return_value = 1
        return mock_redis

    @pytest.mark.asyncio
    async def test_store_summary_error_handling(self, cache, mock_redis):
        """Test error handling during summary storage"""
        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_redis.setex.side_effect = Exception("Redis error")
            mock_get_client.return_value = mock_redis

            result = await cache.store_summary(
                thread_ts="1234567890.123", summary="test summary"
            )

        assert result is False

    @pytest.mark.asyncio
    async def test_get_summary_error_handling(self, cache, mock_redis):
        """Test error handling during summary retrieval"""
        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_redis.get.side_effect = Exception("Redis error")
            mock_get_client.return_value = mock_redis

            result = await cache.get_summary("1234567890.123")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_summary_metadata_error_handling(self, cache, mock_redis):
        """Test error handling during metadata retrieval"""
        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_redis.get.side_effect = Exception("Redis error")
            mock_get_client.return_value = mock_redis

            result = await cache.get_summary_metadata("1234567890.123")

        assert result is None

    @pytest.mark.asyncio
    async def test_store_empty_summary(self, cache, mock_redis):
        """Test storing an empty summary"""
        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_get_client.return_value = mock_redis
            mock_redis.get.return_value = None

            with patch("services.conversation_cache.datetime") as mock_datetime:
                mock_datetime.now.return_value = datetime(
                    2023, 1, 1, 12, 0, 0, tzinfo=UTC
                )
                mock_datetime.UTC = UTC

                result = await cache.store_summary(
                    thread_ts="1234567890.123", summary=""
                )

        # Should still succeed
        assert result is True

    @pytest.mark.asyncio
    async def test_store_very_long_summary(self, cache, mock_redis):
        """Test storing a very long summary"""
        long_summary = "x" * 50000  # 50K characters

        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_get_client.return_value = mock_redis
            mock_redis.get.return_value = None

            with patch("services.conversation_cache.datetime") as mock_datetime:
                mock_datetime.now.return_value = datetime(
                    2023, 1, 1, 12, 0, 0, tzinfo=UTC
                )
                mock_datetime.UTC = UTC

                result = await cache.store_summary(
                    thread_ts="1234567890.123", summary=long_summary
                )

        assert result is True
        # Verify token count is calculated correctly
        expected_token_count = len(long_summary) // 4
        calls = mock_redis.setex.call_args_list
        stored_data = json.loads(calls[0][0][2])  # First setex call
        assert stored_data["token_count"] == expected_token_count

    @pytest.mark.asyncio
    async def test_token_count_estimation(self, cache, mock_redis):
        """Test token count estimation is accurate"""
        summary = "This is a test summary with exactly 50 characters!"  # 50 chars
        expected_tokens = 12  # 50 // 4 = 12

        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_get_client.return_value = mock_redis
            mock_redis.get.return_value = None

            with patch("services.conversation_cache.datetime") as mock_datetime:
                mock_datetime.now.return_value = datetime(
                    2023, 1, 1, 12, 0, 0, tzinfo=UTC
                )
                mock_datetime.UTC = UTC

                await cache.store_summary(thread_ts="1234567890.123", summary=summary)

        # Verify stored token count
        calls = mock_redis.setex.call_args_list
        stored_data = json.loads(calls[0][0][2])
        assert stored_data["token_count"] == expected_tokens

    @pytest.mark.asyncio
    async def test_version_number_increments_correctly(self, cache, mock_redis):
        """Test that version numbers increment correctly"""
        thread_ts = "1234567890.123"

        with patch.object(cache, "_get_redis_client") as mock_get_client:
            mock_get_client.return_value = mock_redis

            with patch("services.conversation_cache.datetime") as mock_datetime:
                mock_datetime.UTC = UTC
                mock_datetime.now.return_value = datetime(
                    2023, 1, 1, 12, 0, 0, tzinfo=UTC
                )

                # First version - no existing history
                mock_redis.get.return_value = None
                await cache.store_summary(thread_ts, "Version 1")

                # Get the stored data from first call
                first_call_data = json.loads(mock_redis.setex.call_args_list[0][0][2])
                assert first_call_data["version"] == 1

                # Second version - mock the history lookup to return v1 data
                history_v1 = {
                    "current_version": 1,
                    "versions": [
                        {
                            "version": 1,
                            "token_count": 2,
                            "created_at": "2023-01-01T12:00:00+00:00",
                        }
                    ],
                }
                # Reset mock to clear previous calls
                mock_redis.reset_mock()
                # Set up the get to return the history data
                mock_redis.get.return_value = json.dumps(history_v1)

                await cache.store_summary(thread_ts, "Version 2")

                # Get the stored data from the first setex call (current key)
                second_call_data = json.loads(mock_redis.setex.call_args_list[0][0][2])
                assert second_call_data["version"] == 2
