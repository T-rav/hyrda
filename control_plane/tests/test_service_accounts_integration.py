"""Integration tests for service account authentication flow.

These tests require Redis to be running.
Run with: pytest tests/test_service_accounts_integration.py -v

Mark with @pytest.mark.integration for CI filtering.
"""

import os
import pytest
import redis
from datetime import datetime, timezone

# All database setup is in conftest.py
from models.base import get_db_session
from models import ServiceAccount


# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def redis_client():
    """Get Redis client for integration tests."""
    redis_url = os.getenv("CACHE_REDIS_URL", "redis://localhost:6379")
    client = redis.from_url(redis_url, decode_responses=True)

    try:
        client.ping()
    except redis.ConnectionError:
        pytest.skip("Redis not available for integration tests")

    # Clean up any test data before tests
    for key in client.scan_iter("service_account:*"):
        client.delete(key)
    for key in client.scan_iter("rate_limit:service_account:*"):
        client.delete(key)

    yield client

    # Clean up after tests
    for key in client.scan_iter("service_account:*"):
        client.delete(key)
    for key in client.scan_iter("rate_limit:service_account:*"):
        client.delete(key)


@pytest.fixture(autouse=True)
def clean_database():
    """Clean database before each test."""
    with get_db_session() as session:
        session.query(ServiceAccount).delete()
        session.commit()
    yield


@pytest.fixture(scope="function", autouse=True)
def clean_redis(redis_client):
    """Clean Redis before each test."""
    for key in redis_client.scan_iter("service_account:*"):
        redis_client.delete(key)
    for key in redis_client.scan_iter("rate_limit:service_account:*"):
        redis_client.delete(key)
    yield


@pytest.fixture
def test_service_account(authenticated_client):
    """Create a test service account for integration tests."""
    response = authenticated_client.post(
        "/api/service-accounts",
        json={
            "name": "Integration Test Account",
            "scopes": "agents:read,agents:invoke",
            "rate_limit": 10,  # Low limit for testing
        },
    )
    assert response.status_code == 200
    data = response.json()
    return {
        "id": data["id"],
        "api_key": data["api_key"],
        "name": data["name"],
        "rate_limit": data["rate_limit"],
    }


class TestEndToEndAuthenticationFlow:
    """Test the complete authentication flow from creation to validation."""

    def test_full_lifecycle(self, authenticated_client, redis_client):
        """Test complete service account lifecycle: create -> validate -> revoke."""
        # Step 1: Create service account
        create_response = authenticated_client.post(
            "/api/service-accounts",
            json={
                "name": "Lifecycle Test",
                "scopes": "agents:invoke",
                "allowed_agents": ["help"],
            },
        )
        assert create_response.status_code == 200
        api_key = create_response.json()["api_key"]
        account_id = create_response.json()["id"]

        # Step 2: Validate (cold - no cache)
        validate_response = authenticated_client.post(
            "/api/service-accounts/validate",
            json={"api_key": api_key, "client_ip": "10.0.0.1"},
        )
        assert validate_response.status_code == 200
        assert validate_response.json()["name"] == "Lifecycle Test"

        # Step 3: Validate again (warm - from cache)
        validate_response2 = authenticated_client.post(
            "/api/service-accounts/validate",
            json={"api_key": api_key, "client_ip": "10.0.0.2"},
        )
        assert validate_response2.status_code == 200

        # Step 4: Revoke account
        revoke_response = authenticated_client.post(
            f"/api/service-accounts/{account_id}/revoke",
            params={"reason": "Test revocation"},
        )
        assert revoke_response.status_code == 200

        # Step 5: Validate after revoke (should fail)
        validate_response3 = authenticated_client.post(
            "/api/service-accounts/validate",
            json={"api_key": api_key, "client_ip": "10.0.0.3"},
        )
        assert validate_response3.status_code == 403
        assert "revoked" in validate_response3.json()["detail"].lower()


class TestRedisCachingBehavior:
    """Test Redis caching for service account validation."""

    def test_cache_hit_miss(
        self, authenticated_client, redis_client, test_service_account
    ):
        """Test cache hit and miss behavior."""
        api_key = test_service_account["api_key"]

        # First validation - cache MISS
        response1 = authenticated_client.post(
            "/api/service-accounts/validate",
            json={"api_key": api_key, "client_ip": "10.0.0.1"},
        )
        assert response1.status_code == 200

        # Check cache was populated
        import hashlib

        api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        cache_key = f"service_account:validated:{api_key_hash}"
        cached_data = redis_client.get(cache_key)
        assert cached_data is not None

        # Second validation - cache HIT
        response2 = authenticated_client.post(
            "/api/service-accounts/validate",
            json={"api_key": api_key, "client_ip": "10.0.0.2"},
        )
        assert response2.status_code == 200

    def test_cache_ttl(self, authenticated_client, redis_client, test_service_account):
        """Test cache TTL is set correctly (60 seconds)."""
        api_key = test_service_account["api_key"]

        # Validate to populate cache
        authenticated_client.post(
            "/api/service-accounts/validate",
            json={"api_key": api_key, "client_ip": "10.0.0.1"},
        )

        # Check TTL
        import hashlib

        api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        cache_key = f"service_account:validated:{api_key_hash}"
        ttl = redis_client.ttl(cache_key)

        # TTL should be around 60 seconds (allow some margin)
        assert 55 <= ttl <= 60

    def test_cache_invalidation_on_revoke(
        self, authenticated_client, redis_client, test_service_account
    ):
        """Test that cache is invalidated when account is revoked."""
        api_key = test_service_account["api_key"]
        account_id = test_service_account["id"]

        # Validate to populate cache
        authenticated_client.post(
            "/api/service-accounts/validate",
            json={"api_key": api_key, "client_ip": "10.0.0.1"},
        )

        # Verify cache exists
        cache_keys_set = f"service_account:cache_keys:{account_id}"
        cached_keys = redis_client.smembers(cache_keys_set)
        assert len(cached_keys) > 0

        # Revoke account
        authenticated_client.post(
            f"/api/service-accounts/{account_id}/revoke",
            params={"reason": "Cache invalidation test"},
        )

        # Verify cache was cleared
        cached_keys_after = redis_client.smembers(cache_keys_set)
        assert len(cached_keys_after) == 0

    def test_cache_invalidation_on_deactivate(
        self, authenticated_client, redis_client, test_service_account
    ):
        """Test that cache is invalidated when account is deactivated."""
        api_key = test_service_account["api_key"]
        account_id = test_service_account["id"]

        # Validate to populate cache
        authenticated_client.post(
            "/api/service-accounts/validate",
            json={"api_key": api_key, "client_ip": "10.0.0.1"},
        )

        # Verify cache exists
        cache_keys_set = f"service_account:cache_keys:{account_id}"
        cached_keys = redis_client.smembers(cache_keys_set)
        assert len(cached_keys) > 0

        # Deactivate account
        authenticated_client.patch(
            f"/api/service-accounts/{account_id}",
            json={"is_active": False},
        )

        # Verify cache was cleared
        cached_keys_after = redis_client.smembers(cache_keys_set)
        assert len(cached_keys_after) == 0

    def test_cache_invalidation_on_delete(
        self, authenticated_client, redis_client, test_service_account
    ):
        """Test that cache is invalidated when account is deleted."""
        api_key = test_service_account["api_key"]
        account_id = test_service_account["id"]

        # Validate to populate cache
        authenticated_client.post(
            "/api/service-accounts/validate",
            json={"api_key": api_key, "client_ip": "10.0.0.1"},
        )

        # Verify cache exists
        cache_keys_set = f"service_account:cache_keys:{account_id}"
        cached_keys = redis_client.smembers(cache_keys_set)
        assert len(cached_keys) > 0

        # Delete account
        authenticated_client.delete(f"/api/service-accounts/{account_id}")

        # Verify cache was cleared
        cached_keys_after = redis_client.smembers(cache_keys_set)
        assert len(cached_keys_after) == 0


class TestRateLimitingEnforcement:
    """Test rate limiting with Redis."""

    def test_rate_limit_enforced(
        self, authenticated_client, redis_client, test_service_account
    ):
        """Test that rate limits are enforced."""
        api_key = test_service_account["api_key"]
        rate_limit = test_service_account["rate_limit"]  # Should be 10

        # Make requests up to the limit
        for i in range(rate_limit):
            response = authenticated_client.post(
                "/api/service-accounts/validate",
                json={"api_key": api_key, "client_ip": f"10.0.0.{i}"},
            )
            assert response.status_code == 200, f"Request {i + 1} failed"

        # Next request should be rate limited
        response = authenticated_client.post(
            "/api/service-accounts/validate",
            json={"api_key": api_key, "client_ip": "10.0.0.99"},
        )
        assert response.status_code == 429
        assert "rate limit" in response.json()["detail"].lower()

    def test_rate_limit_counter_in_redis(
        self, authenticated_client, redis_client, test_service_account
    ):
        """Test that rate limit counters are stored in Redis."""
        api_key = test_service_account["api_key"]
        account_id = test_service_account["id"]

        # Make 3 requests
        for i in range(3):
            authenticated_client.post(
                "/api/service-accounts/validate",
                json={"api_key": api_key, "client_ip": f"10.0.0.{i}"},
            )

        # Check Redis counter
        current_hour = datetime.now(timezone.utc).replace(
            minute=0, second=0, microsecond=0
        )
        rate_limit_key = (
            f"rate_limit:service_account:{account_id}:{current_hour.isoformat()}"
        )
        count = redis_client.get(rate_limit_key)

        assert count is not None
        assert int(count) == 3

    def test_rate_limit_resets_hourly(
        self, authenticated_client, redis_client, test_service_account
    ):
        """Test that rate limit TTL is set to 1 hour."""
        api_key = test_service_account["api_key"]
        account_id = test_service_account["id"]

        # Make one request
        authenticated_client.post(
            "/api/service-accounts/validate",
            json={"api_key": api_key, "client_ip": "10.0.0.1"},
        )

        # Check TTL
        current_hour = datetime.now(timezone.utc).replace(
            minute=0, second=0, microsecond=0
        )
        rate_limit_key = (
            f"rate_limit:service_account:{account_id}:{current_hour.isoformat()}"
        )
        ttl = redis_client.ttl(rate_limit_key)

        # TTL should be around 3600 seconds (1 hour)
        assert 3595 <= ttl <= 3600

    def test_different_accounts_have_separate_limits(
        self, authenticated_client, redis_client
    ):
        """Test that different service accounts have independent rate limits."""
        # Create two accounts
        response1 = authenticated_client.post(
            "/api/service-accounts",
            json={"name": "Account 1", "scopes": "agents:invoke", "rate_limit": 5},
        )
        api_key1 = response1.json()["api_key"]

        response2 = authenticated_client.post(
            "/api/service-accounts",
            json={"name": "Account 2", "scopes": "agents:invoke", "rate_limit": 5},
        )
        api_key2 = response2.json()["api_key"]

        # Use both accounts up to their limits
        for i in range(5):
            resp1 = authenticated_client.post(
                "/api/service-accounts/validate",
                json={"api_key": api_key1, "client_ip": "10.0.1.1"},
            )
            resp2 = authenticated_client.post(
                "/api/service-accounts/validate",
                json={"api_key": api_key2, "client_ip": "10.0.2.1"},
            )
            assert resp1.status_code == 200
            assert resp2.status_code == 200

        # Both should be rate limited independently
        resp1 = authenticated_client.post(
            "/api/service-accounts/validate",
            json={"api_key": api_key1, "client_ip": "10.0.1.2"},
        )
        resp2 = authenticated_client.post(
            "/api/service-accounts/validate",
            json={"api_key": api_key2, "client_ip": "10.0.2.2"},
        )

        assert resp1.status_code == 429
        assert resp2.status_code == 429


class TestUsageTracking:
    """Test usage statistics tracking."""

    def test_usage_stats_updated(self, authenticated_client, test_service_account):
        """Test that usage stats are updated after validation."""
        api_key = test_service_account["api_key"]
        account_id = test_service_account["id"]

        # Get initial stats
        initial_response = authenticated_client.get(
            f"/api/service-accounts/{account_id}"
        )
        initial_requests = initial_response.json()["total_requests"]

        # Validate 5 times
        for i in range(5):
            authenticated_client.post(
                "/api/service-accounts/validate",
                json={"api_key": api_key, "client_ip": f"10.0.0.{i}"},
            )

        # Check updated stats
        final_response = authenticated_client.get(f"/api/service-accounts/{account_id}")
        final_data = final_response.json()

        assert final_data["total_requests"] == initial_requests + 5
        assert final_data["last_used_at"] is not None
        assert final_data["last_request_ip"] is not None
