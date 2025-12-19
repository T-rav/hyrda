"""Tests for profile report caching (30-day TTL)."""

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
async def test_profile_report_cache_stores_with_30_day_ttl():
    """Test that profile reports are cached with 30-day TTL."""
    from services.conversation_cache import ConversationCache

    cache = ConversationCache()

    # Mock Redis
    mock_redis = AsyncMock()
    cache.redis_client = mock_redis
    cache._redis_available = True

    full_report = "# Company Profile\n\n" + "x" * 14000
    report_url = "https://minio/reports/profile_Costco_20240101.md"
    thread_ts = "1234567890.123456"

    # Store report
    result = await cache.store_profile_report(thread_ts, full_report, report_url)

    assert result is True

    # Should cache with 30-day TTL
    mock_redis.setex.assert_called_once()
    call_args = mock_redis.setex.call_args
    assert "conversation_profile_report:" in call_args[0][0]
    assert call_args[0][1] == 2592000  # 30 days in seconds

    # Should store full report and URL
    cached_data = json.loads(call_args[0][2])
    assert cached_data["full_report"] == full_report
    assert cached_data["report_url"] == report_url
    assert "stored_at" in cached_data


@pytest.mark.asyncio
async def test_profile_report_cache_retrieval():
    """Test that cached profile reports can be retrieved."""
    from services.conversation_cache import ConversationCache

    cache = ConversationCache()

    # Mock Redis with cached data
    mock_redis = AsyncMock()
    full_report = "# Company Profile\n\nTest report content"
    report_url = "https://minio/reports/test.md"
    cached_data = {
        "full_report": full_report,
        "report_url": report_url,
        "stored_at": datetime.now(UTC).isoformat(),
    }
    mock_redis.get.return_value = json.dumps(cached_data)
    cache.redis_client = mock_redis
    cache._redis_available = True

    thread_ts = "1234567890.123456"

    # Retrieve report
    retrieved_report, retrieved_url = await cache.get_profile_report(thread_ts)

    assert retrieved_report == full_report
    assert retrieved_url == report_url

    # Should have checked Redis
    mock_redis.get.assert_called_once()


@pytest.mark.asyncio
async def test_profile_report_cache_miss():
    """Test that cache miss returns None."""
    from services.conversation_cache import ConversationCache

    cache = ConversationCache()

    # Mock Redis miss
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None
    cache.redis_client = mock_redis
    cache._redis_available = True

    thread_ts = "1234567890.123456"

    # Retrieve report
    retrieved_report, retrieved_url = await cache.get_profile_report(thread_ts)

    assert retrieved_report is None
    assert retrieved_url is None


@pytest.mark.asyncio
async def test_profile_report_cache_supports_follow_ups():
    """Test that cached reports enable follow-up questions."""
    from services.conversation_cache import ConversationCache

    cache = ConversationCache()

    # Mock Redis with cached report
    mock_redis = AsyncMock()
    full_report = (
        "# Company Profile\n\nDetailed report about challenges, tech stack, etc."
    )
    report_url = "https://minio/reports/profile.md"
    cached_data = {
        "full_report": full_report,
        "report_url": report_url,
        "stored_at": datetime.now(UTC).isoformat(),
    }
    mock_redis.get.return_value = json.dumps(cached_data)
    cache.redis_client = mock_redis
    cache._redis_available = True

    thread_ts = "1234567890.123456"

    # Simulate follow-up: retrieve cached report
    retrieved_report, retrieved_url = await cache.get_profile_report(thread_ts)

    # Report should be available for follow-up context
    assert retrieved_report is not None
    assert len(retrieved_report) > 50  # Substantial content
    assert "challenges" in retrieved_report or "Detailed report" in retrieved_report
    assert retrieved_url == report_url

    # This cached report can now be injected into LLM context for follow-ups


@pytest.mark.asyncio
async def test_profile_report_metadata_storage():
    """Test that report metadata (URL, timestamp) is stored correctly."""
    from services.conversation_cache import ConversationCache

    cache = ConversationCache()

    # Mock Redis
    mock_redis = AsyncMock()
    cache.redis_client = mock_redis
    cache._redis_available = True

    full_report = "# Company Profile\n\nTest report"
    report_url = "https://minio/reports/test.md"
    thread_ts = "1234567890.123456"

    # Store report
    await cache.store_profile_report(thread_ts, full_report, report_url)

    # Extract cached data
    call_args = mock_redis.setex.call_args
    cached_json = call_args[0][2]
    cached_data = json.loads(cached_json)

    # Should have all metadata
    assert "full_report" in cached_data
    assert "report_url" in cached_data
    assert "stored_at" in cached_data

    # Metadata should be accurate
    assert cached_data["full_report"] == full_report
    assert cached_data["report_url"] == report_url

    # Timestamp should be recent
    stored_time = datetime.fromisoformat(cached_data["stored_at"])
    now = datetime.now(UTC)
    time_diff = (now - stored_time).total_seconds()
    assert time_diff < 5  # Within 5 seconds


@pytest.mark.asyncio
async def test_profile_report_cache_handles_large_reports():
    """Test that cache handles large reports (14k+ characters)."""
    from services.conversation_cache import ConversationCache

    cache = ConversationCache()

    # Mock Redis
    mock_redis = AsyncMock()
    cache.redis_client = mock_redis
    cache._redis_available = True

    # Create large report (14k characters)
    full_report = "# Company Profile\n\n" + "x" * 14000
    report_url = "https://minio/reports/large_report.md"
    thread_ts = "1234567890.123456"

    # Store large report
    result = await cache.store_profile_report(thread_ts, full_report, report_url)

    assert result is True

    # Should successfully cache large report
    mock_redis.setex.assert_called_once()
    call_args = mock_redis.setex.call_args
    cached_data = json.loads(call_args[0][2])
    assert len(cached_data["full_report"]) > 14000


@pytest.mark.asyncio
async def test_profile_report_cache_graceful_failure():
    """Test that cache failures don't break the application."""
    from services.conversation_cache import ConversationCache

    cache = ConversationCache()

    # Mock Redis that fails
    mock_redis = AsyncMock()
    mock_redis.setex.side_effect = Exception("Redis connection failed")
    cache.redis_client = mock_redis
    cache._redis_available = True

    full_report = "# Company Profile\n\nTest content"
    report_url = "https://minio/reports/test.md"
    thread_ts = "1234567890.123456"

    # Should handle error gracefully
    result = await cache.store_profile_report(thread_ts, full_report, report_url)

    assert result is False  # Indicates failure but doesn't crash

    # Retrieval should also handle errors
    mock_redis.get.side_effect = Exception("Redis connection failed")

    retrieved_report, retrieved_url = await cache.get_profile_report(thread_ts)

    assert retrieved_report is None
    assert retrieved_url is None
