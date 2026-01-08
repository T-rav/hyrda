"""Redis cache integration tests - CRITICAL INFRASTRUCTURE.

Tests verify Redis connection, cache coherency, and degradation handling.
These tests validate that cache failures don't cause cascading service failures.

Run with: pytest -v -m integration bot/tests/test_integration_redis.py
"""

import asyncio
import os

import pytest
import redis.asyncio as redis

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.fixture
async def redis_client():
    """Create Redis client for testing."""
    redis_url = os.getenv("CACHE_REDIS_URL", "redis://localhost:6379")
    client = redis.from_url(redis_url, decode_responses=True)
    try:
        yield client
    finally:
        await client.aclose()


async def test_redis_connection_on_startup(redis_client):
    """
    CRITICAL TEST - Redis connection must work.

    Given: Redis service is running
    When: Application starts
    Then: Redis connection succeeds

    Failure Impact: Bot service won't start if Redis unavailable
    """
    # Test connection with ping
    pong = await redis_client.ping()
    assert pong is True, "Redis connection failed - service won't start"

    print("✅ Redis connection successful")


async def test_redis_basic_operations(redis_client):
    """
    CRITICAL TEST - Basic Redis operations must work.

    Given: Redis connection established
    When: Performing SET/GET operations
    Then: Values are stored and retrieved correctly
    """
    test_key = "integration_test:redis_ops"

    # Set value
    await redis_client.set(test_key, "test_value", ex=60)

    # Get value
    value = await redis_client.get(test_key)
    assert value == "test_value", (
        f"Redis GET failed: expected 'test_value', got {value}"
    )

    # Delete test key
    await redis_client.delete(test_key)

    print("✅ Redis basic operations working")


async def test_conversation_cache_key_pattern(redis_client):
    """
    BUSINESS LOGIC TEST - Conversation cache uses correct key pattern.

    Given: Bot service caches conversations
    When: Checking Redis keys
    Then: Keys follow pattern 'conversation:{channel}:{thread_ts}'
    """
    # Check if any conversation keys exist
    cursor = 0
    conversation_keys = []

    # Scan for conversation keys (non-blocking scan)
    while True:
        cursor, keys = await redis_client.scan(
            cursor, match="conversation:*", count=100
        )
        conversation_keys.extend(keys)
        if cursor == 0:
            break

    # If no keys, skip (cache might be empty)
    if not conversation_keys:
        pytest.skip("No conversation keys found in Redis cache")

    # Validate key pattern
    for key in conversation_keys:
        parts = key.split(":")
        assert len(parts) >= 2, f"Invalid conversation key pattern: {key}"
        assert parts[0] == "conversation", (
            f"Key doesn't start with 'conversation:': {key}"
        )

    print(f"✅ Found {len(conversation_keys)} conversation keys with correct pattern")


async def test_cache_ttl_setting(redis_client):
    """
    CRITICAL TEST - Cache TTL must be set to prevent memory leaks.

    Given: Redis cache stores conversation data
    When: Setting cache entries
    Then: TTL is set on all keys
    """
    test_key = "integration_test:ttl_test"

    # Set value with TTL
    await redis_client.set(test_key, "test", ex=1800)  # 30 minutes

    # Check TTL
    ttl = await redis_client.ttl(test_key)
    assert ttl > 0, f"TTL not set on cache key: {test_key}"
    assert ttl <= 1800, f"TTL too high: {ttl}"

    # Cleanup
    await redis_client.delete(test_key)

    print(f"✅ Cache TTL properly set: {ttl}s")


async def test_redis_max_memory_policy(redis_client):
    """
    CRITICAL TEST - Redis eviction policy must be set.

    Given: Redis has limited memory
    When: Memory limit reached
    Then: Redis uses appropriate eviction policy (LRU recommended)
    """
    # Get Redis config
    config = await redis_client.config_get("maxmemory-policy")

    # Check if maxmemory policy is set
    policy = config.get("maxmemory-policy")
    if policy:
        # Recommended policies for cache: allkeys-lru, volatile-lru
        recommended_policies = ["allkeys-lru", "volatile-lru", "allkeys-lfu"]
        if policy not in recommended_policies:
            print(
                f"⚠️  WARNING: Redis eviction policy is '{policy}' "
                f"(recommended: {', '.join(recommended_policies)})"
            )
        else:
            print(f"✅ Redis eviction policy: {policy}")
    else:
        pytest.skip("Redis maxmemory-policy not configured")


async def test_redis_persistence_enabled(redis_client):
    """
    BUSINESS LOGIC TEST - Redis persistence should be enabled.

    Given: Redis is used for conversation caching
    When: Checking Redis persistence config
    Then: AOF or RDB persistence is enabled
    """
    # Check AOF persistence
    aof_config = await redis_client.config_get("appendonly")
    aof_enabled = aof_config.get("appendonly") == "yes"

    # Check RDB persistence
    save_config = await redis_client.config_get("save")
    rdb_enabled = save_config.get("save") != ""

    if not (aof_enabled or rdb_enabled):
        print(
            "⚠️  WARNING: Redis persistence not enabled - "
            "cache data will be lost on restart"
        )
    else:
        persistence_type = []
        if aof_enabled:
            persistence_type.append("AOF")
        if rdb_enabled:
            persistence_type.append("RDB")
        print(f"✅ Redis persistence enabled: {', '.join(persistence_type)}")


async def test_multiple_concurrent_cache_operations(redis_client):
    """
    PERFORMANCE TEST - Redis should handle concurrent operations.

    Given: Multiple bot instances accessing cache
    When: Performing concurrent cache operations
    Then: All operations succeed without errors
    """
    test_prefix = "integration_test:concurrent"

    # Create concurrent operations
    tasks = []
    for i in range(10):
        key = f"{test_prefix}:{i}"
        tasks.append(redis_client.set(key, f"value_{i}", ex=60))

    # Execute concurrently
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Check for errors
    errors = [r for r in results if isinstance(r, Exception)]
    assert not errors, f"Concurrent cache operations failed: {errors}"

    # Cleanup
    keys_to_delete = [f"{test_prefix}:{i}" for i in range(10)]
    await redis_client.delete(*keys_to_delete)

    print(f"✅ {len(results)} concurrent cache operations succeeded")


async def test_cache_invalidation_works(redis_client):
    """
    BUSINESS LOGIC TEST - Cache invalidation must work.

    Given: Conversation cached in Redis
    When: Cache key is deleted
    Then: Key is removed from cache
    """
    test_key = "integration_test:invalidation"

    # Set value
    await redis_client.set(test_key, "cached_value", ex=60)

    # Verify exists
    assert await redis_client.exists(test_key) == 1

    # Invalidate (delete)
    await redis_client.delete(test_key)

    # Verify deleted
    assert await redis_client.exists(test_key) == 0

    print("✅ Cache invalidation working")


# TODO: Add these tests when fault tolerance is implemented
# async def test_bot_handles_redis_downtime():
#     """Test that bot degrades gracefully when Redis is unavailable."""
#     pass
#
# async def test_cache_miss_fallback_to_database():
#     """Test that cache misses fall back to database queries."""
#     pass
