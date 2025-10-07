"""Tests for user service caching functionality."""

import json
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_redis():
    """Create a mock Redis client."""
    return MagicMock()


@pytest.fixture
def mock_user_data():
    """Sample user data."""
    return {
        "slack_user_id": "U01234567",
        "real_name": "Travis Frisinger",
        "email_address": "travis@example.com",
        "display_name": "Travis",
        "is_admin": False,
        "is_bot": False,
    }


def test_get_user_info_from_cache_hit(mock_redis, mock_user_data):
    """Test that cached data is returned on cache hit."""
    from services.user_service import UserService

    # Setup cache to return data
    mock_redis.get.return_value = json.dumps(mock_user_data)

    service = UserService(redis_client=mock_redis)
    result = service.get_user_info("U01234567")

    # Should return cached data
    assert result == mock_user_data

    # Should have checked cache
    mock_redis.get.assert_called_once_with("user_info:U01234567")

    # Should NOT have set cache (already cached)
    mock_redis.setex.assert_not_called()


def test_get_user_info_from_cache_miss_returns_none(mock_redis):
    """Test that cache miss returns None (database lookup not implemented)."""
    from services.user_service import UserService

    # Setup cache miss
    mock_redis.get.return_value = None

    service = UserService(redis_client=mock_redis)
    result = service.get_user_info("U01234567")

    # Should return None when not in cache (database lookup not implemented)
    assert result is None

    # Should have checked cache
    mock_redis.get.assert_called_once_with("user_info:U01234567")


def test_cache_invalidation(mock_redis):
    """Test that cache can be invalidated."""
    from services.user_service import UserService

    service = UserService(redis_client=mock_redis)
    service.invalidate_cache("U01234567")

    # Should delete the cache key
    mock_redis.delete.assert_called_once_with("user_info:U01234567")
