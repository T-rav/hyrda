"""Tests for user service Redis caching."""

import json
from unittest.mock import MagicMock, patch

import pytest

from services.user_service import UserService


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    redis = MagicMock()
    return redis


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


def test_get_user_info_from_cache_miss_then_db(mock_redis, mock_user_data):
    """Test that database is queried on cache miss and result is cached."""
    # Setup cache miss
    mock_redis.get.return_value = None

    # Mock database query
    with patch("models.base.get_db_session") as mock_db:
        mock_session = MagicMock()
        mock_db.return_value.__enter__.return_value = mock_session

        mock_user = MagicMock()
        mock_user.slack_user_id = mock_user_data["slack_user_id"]
        mock_user.real_name = mock_user_data["real_name"]
        mock_user.email_address = mock_user_data["email_address"]
        mock_user.display_name = mock_user_data["display_name"]
        mock_user.is_admin = mock_user_data["is_admin"]
        mock_user.is_bot = mock_user_data["is_bot"]

        mock_session.query.return_value.filter.return_value.first.return_value = (
            mock_user
        )

        service = UserService(redis_client=mock_redis)
        result = service.get_user_info("U01234567")

        # Should return database data
        assert result == mock_user_data

        # Should have checked cache
        mock_redis.get.assert_called_once_with("user_info:U01234567")

        # Should have cached the result
        mock_redis.setex.assert_called_once()
        cache_key, ttl, cached_data = mock_redis.setex.call_args[0]
        assert cache_key == "user_info:U01234567"
        assert ttl == 3600  # 1 hour TTL
        assert json.loads(cached_data) == mock_user_data


def test_get_user_info_without_redis(mock_user_data):
    """Test that service works without Redis (no caching)."""
    with patch("models.base.get_db_session") as mock_db:
        mock_session = MagicMock()
        mock_db.return_value.__enter__.return_value = mock_session

        mock_user = MagicMock()
        mock_user.slack_user_id = mock_user_data["slack_user_id"]
        mock_user.real_name = mock_user_data["real_name"]
        mock_user.email_address = mock_user_data["email_address"]
        mock_user.display_name = mock_user_data["display_name"]
        mock_user.is_admin = mock_user_data["is_admin"]
        mock_user.is_bot = mock_user_data["is_bot"]

        mock_session.query.return_value.filter.return_value.first.return_value = (
            mock_user
        )

        # Initialize without Redis
        service = UserService(redis_client=None)
        result = service.get_user_info("U01234567")

        # Should still return database data
        assert result == mock_user_data


def test_cache_invalidation(mock_redis):
    """Test cache invalidation."""
    service = UserService(redis_client=mock_redis)
    service.invalidate_cache("U01234567")

    # Should delete the cache key
    mock_redis.delete.assert_called_once_with("user_info:U01234567")


def test_cache_error_handling(mock_redis, mock_user_data):
    """Test that cache errors don't break the service."""
    # Setup cache to raise error
    mock_redis.get.side_effect = Exception("Redis connection error")

    with patch("models.base.get_db_session") as mock_db:
        mock_session = MagicMock()
        mock_db.return_value.__enter__.return_value = mock_session

        mock_user = MagicMock()
        mock_user.slack_user_id = mock_user_data["slack_user_id"]
        mock_user.real_name = mock_user_data["real_name"]
        mock_user.email_address = mock_user_data["email_address"]
        mock_user.display_name = mock_user_data["display_name"]
        mock_user.is_admin = mock_user_data["is_admin"]
        mock_user.is_bot = mock_user_data["is_bot"]

        mock_session.query.return_value.filter.return_value.first.return_value = (
            mock_user
        )

        service = UserService(redis_client=mock_redis)
        result = service.get_user_info("U01234567")

        # Should still return database data despite cache error
        assert result == mock_user_data
