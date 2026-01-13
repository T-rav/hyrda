"""Tests for SEC filings dual cache (Redis + MinIO)."""

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest


@pytest.mark.asyncio
async def test_sec_cache_stores_to_both_redis_and_minio():
    """Test that SEC filings are cached to both Redis and MinIO."""
    from external_agents.profile.services.sec_cache import SECFilingsCache

    # Mock Redis and MinIO clients
    mock_redis = AsyncMock()
    mock_s3 = MagicMock()

    cache = SECFilingsCache()
    cache.redis_client = mock_redis
    cache._redis_available = True
    cache.s3_client = mock_s3
    cache._minio_available = True

    # Test data
    filings = [{"form": "10-K", "date": "2024-01-01"}]
    chunks = ["Chunk 1", "Chunk 2"]
    metadata = [{"page": 1}, {"page": 2}]
    embeddings = np.array([[0.1, 0.2], [0.3, 0.4]])

    # Cache the filings
    result = await cache.cache_filings(
        "COST", "Costco", filings, chunks, metadata, embeddings
    )

    # Should succeed
    assert result is True

    # Should cache to Redis
    mock_redis.setex.assert_called_once()
    redis_call = mock_redis.setex.call_args
    assert "sec_filings:COST" in redis_call[0][0]
    assert redis_call[0][1] == 3600  # 1 hour TTL

    # Should cache to MinIO
    mock_s3.put_object.assert_called_once()
    s3_call = mock_s3.put_object.call_args
    assert s3_call[1]["Bucket"] == "research-sec-filings"
    assert "COST_" in s3_call[1]["Key"]
    assert s3_call[1]["ContentType"] == "application/json"


@pytest.mark.asyncio
async def test_sec_cache_redis_hit():
    """Test that Redis cache is checked first and returns cached data."""
    from external_agents.profile.services.sec_cache import SECFilingsCache

    cache = SECFilingsCache()

    # Mock Redis with cached data
    mock_redis = AsyncMock()
    cached_data = {
        "company_name": "Costco",
        "chunks": ["Chunk 1"],
        "total_chunks": 1,
    }
    mock_redis.get.return_value = json.dumps(cached_data).encode("utf-8")
    cache.redis_client = mock_redis
    cache._redis_available = True

    # Should not check MinIO
    cache.s3_client = None
    cache._minio_available = False

    result = await cache.get_cached_filings("COST")

    # Should return cached data
    assert result is not None
    assert result["company_name"] == "Costco"
    assert result["total_chunks"] == 1

    # Should have checked Redis
    mock_redis.get.assert_called_once()


@pytest.mark.asyncio
async def test_sec_cache_minio_fallback():
    """Test that MinIO is used as fallback when Redis misses."""
    from external_agents.profile.services.sec_cache import SECFilingsCache

    cache = SECFilingsCache()

    # Mock Redis miss
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None
    cache.redis_client = mock_redis
    cache._redis_available = True

    # Mock MinIO hit
    mock_s3 = MagicMock()
    cached_data = {
        "company_name": "Costco",
        "chunks": ["Chunk 1"],
        "total_chunks": 1,
    }
    mock_response = {"Body": MagicMock()}
    mock_response["Body"].read.return_value = json.dumps(cached_data).encode("utf-8")
    mock_s3.get_object.return_value = mock_response
    cache.s3_client = mock_s3
    cache._minio_available = True

    result = await cache.get_cached_filings("COST")

    # Should return cached data from MinIO
    assert result is not None
    assert result["company_name"] == "Costco"

    # Should have checked Redis first
    mock_redis.get.assert_called_once()

    # Should have checked MinIO
    mock_s3.get_object.assert_called_once()

    # Should re-cache in Redis
    mock_redis.setex.assert_called_once()


@pytest.mark.asyncio
async def test_sec_cache_dual_miss():
    """Test that both caches miss returns None."""
    from external_agents.profile.services.sec_cache import SECFilingsCache

    cache = SECFilingsCache()

    # Mock Redis miss
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None
    cache.redis_client = mock_redis
    cache._redis_available = True

    # Mock MinIO miss
    mock_s3 = MagicMock()
    mock_s3.get_object.side_effect = Exception("NoSuchKey")
    cache.s3_client = mock_s3
    cache._minio_available = True

    result = await cache.get_cached_filings("COST")

    # Should return None
    assert result is None

    # Should have checked both caches
    mock_redis.get.assert_called_once()
    mock_s3.get_object.assert_called_once()


@pytest.mark.asyncio
async def test_sec_cache_handles_embeddings():
    """Test that embeddings are serialized and deserialized correctly."""
    from external_agents.profile.services.sec_cache import SECFilingsCache

    cache = SECFilingsCache()

    # Mock Redis
    mock_redis = AsyncMock()
    cache.redis_client = mock_redis
    cache._redis_available = True

    # Mock MinIO
    mock_s3 = MagicMock()
    cache.s3_client = mock_s3
    cache._minio_available = True

    # Test data with embeddings
    filings = [{"form": "10-K"}]
    chunks = ["Chunk 1"]
    metadata = [{"page": 1}]
    embeddings = np.array([[0.1, 0.2, 0.3]])

    # Cache with embeddings
    await cache.cache_filings("COST", "Costco", filings, chunks, metadata, embeddings)

    # Get cached data
    redis_call = mock_redis.setex.call_args
    cached_json = redis_call[0][2]
    cached_data = json.loads(cached_json)

    # Should have serialized embeddings
    assert "embeddings" in cached_data
    assert "data" in cached_data["embeddings"]
    assert "shape" in cached_data["embeddings"]
    assert "dtype" in cached_data["embeddings"]
    assert cached_data["embeddings"]["shape"] == [1, 3]


@pytest.mark.asyncio
async def test_sec_cache_graceful_degradation():
    """Test that cache works with only one layer available."""
    from external_agents.profile.services.sec_cache import SECFilingsCache

    cache = SECFilingsCache()

    # Only Redis available
    mock_redis = AsyncMock()
    cache.redis_client = mock_redis
    cache._redis_available = True
    cache.s3_client = None
    cache._minio_available = False

    filings = [{"form": "10-K"}]
    chunks = ["Chunk 1"]
    metadata = [{"page": 1}]

    # Should still cache to Redis
    result = await cache.cache_filings("COST", "Costco", filings, chunks, metadata)
    assert result is True
    mock_redis.setex.assert_called_once()

    # Only MinIO available
    cache2 = SECFilingsCache()
    cache2.redis_client = None
    cache2._redis_available = False
    mock_s3 = MagicMock()
    cache2.s3_client = mock_s3
    cache2._minio_available = True

    # Should still cache to MinIO
    result = await cache2.cache_filings("COST", "Costco", filings, chunks, metadata)
    assert result is True
    mock_s3.put_object.assert_called_once()
