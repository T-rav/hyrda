"""Tests for idempotency key support."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import Request
from fastapi.responses import JSONResponse

from utils.idempotency import (
    MAX_IDEMPOTENCY_KEYS,
    _cleanup_expired_keys,
    _idempotency_cache,
    check_idempotency,
    generate_request_hash,
    get_idempotency_key,
    require_idempotency,
    store_idempotency,
)


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear idempotency cache before each test."""
    _idempotency_cache.clear()
    yield
    _idempotency_cache.clear()


class TestGetIdempotencyKey:
    """Test getting idempotency key from request."""

    @pytest.mark.asyncio
    async def test_get_idempotency_key_present(self):
        """Test getting idempotency key when present."""
        mock_request = Mock(spec=Request)
        mock_request.headers = {"Idempotency-Key": "test-key-123"}

        result = await get_idempotency_key(mock_request)
        assert result == "test-key-123"

    @pytest.mark.asyncio
    async def test_get_idempotency_key_missing(self):
        """Test getting idempotency key when not present."""
        mock_request = Mock(spec=Request)
        mock_request.headers = {}

        result = await get_idempotency_key(mock_request)
        assert result is None


class TestGenerateRequestHash:
    """Test request hash generation."""

    @pytest.mark.asyncio
    async def test_generate_request_hash(self):
        """Test generating hash from request details."""
        mock_request = Mock(spec=Request)
        mock_request.method = "POST"
        mock_request.url = Mock()
        mock_request.url.path = "/api/test"
        mock_request.body = AsyncMock(return_value=b'{"key": "value"}')

        hash_result = await generate_request_hash(mock_request)

        # Verify it's a valid SHA256 hash (64 hex characters)
        assert len(hash_result) == 64
        assert all(c in "0123456789abcdef" for c in hash_result)

    @pytest.mark.asyncio
    async def test_generate_request_hash_empty_body(self):
        """Test generating hash with empty body."""
        mock_request = Mock(spec=Request)
        mock_request.method = "GET"
        mock_request.url = Mock()
        mock_request.url.path = "/api/test"
        mock_request.body = AsyncMock(return_value=b"")

        hash_result = await generate_request_hash(mock_request)
        assert len(hash_result) == 64

    @pytest.mark.asyncio
    async def test_generate_request_hash_consistent(self):
        """Test that same request generates same hash."""
        mock_request = Mock(spec=Request)
        mock_request.method = "POST"
        mock_request.url = Mock()
        mock_request.url.path = "/api/test"
        mock_request.body = AsyncMock(return_value=b'{"key": "value"}')

        hash1 = await generate_request_hash(mock_request)

        # Reset mock for second call
        mock_request.body = AsyncMock(return_value=b'{"key": "value"}')
        hash2 = await generate_request_hash(mock_request)

        assert hash1 == hash2


class TestCheckIdempotency:
    """Test checking for duplicate requests."""

    @pytest.mark.asyncio
    async def test_check_idempotency_no_key(self):
        """Test when no idempotency key provided."""
        mock_request = Mock(spec=Request)
        mock_request.headers = {}

        is_duplicate, response = await check_idempotency(mock_request)
        assert is_duplicate is False
        assert response is None

    @pytest.mark.asyncio
    async def test_check_idempotency_cache_miss(self):
        """Test when idempotency key not in cache."""
        mock_request = Mock(spec=Request)
        mock_request.headers = {"Idempotency-Key": "new-key"}
        mock_request.method = "POST"
        mock_request.url = Mock()
        mock_request.url.path = "/api/test"
        mock_request.body = AsyncMock(return_value=b'{"data": "test"}')

        is_duplicate, response = await check_idempotency(mock_request)
        assert is_duplicate is False
        assert response is None

    @pytest.mark.asyncio
    async def test_check_idempotency_cache_hit(self):
        """Test when idempotency key found in cache."""
        # Setup: Store a response in cache
        mock_request = Mock(spec=Request)
        mock_request.headers = {"Idempotency-Key": "cached-key"}
        mock_request.method = "POST"
        mock_request.url = Mock()
        mock_request.url.path = "/api/test"
        mock_request.body = AsyncMock(return_value=b'{"data": "test"}')

        # Store first
        await store_idempotency(mock_request, {"status": "success", "id": 123}, 201)

        # Reset body mock for second call
        mock_request.body = AsyncMock(return_value=b'{"data": "test"}')

        # Check again (should hit cache)
        is_duplicate, response = await check_idempotency(mock_request)

        assert is_duplicate is True
        assert isinstance(response, JSONResponse)
        assert response.status_code == 201


class TestStoreIdempotency:
    """Test storing idempotency responses."""

    @pytest.mark.asyncio
    async def test_store_idempotency_no_key(self):
        """Test storing without idempotency key."""
        mock_request = Mock(spec=Request)
        mock_request.headers = {}

        await store_idempotency(mock_request, {"result": "test"}, 200)

        # Cache should be empty
        assert len(_idempotency_cache) == 0

    @pytest.mark.asyncio
    async def test_store_idempotency_success(self):
        """Test successful storage of idempotency response."""
        mock_request = Mock(spec=Request)
        mock_request.headers = {"Idempotency-Key": "store-key"}
        mock_request.method = "POST"
        mock_request.url = Mock()
        mock_request.url.path = "/api/test"
        mock_request.body = AsyncMock(return_value=b'{"data": "test"}')

        response_body = {"status": "created", "id": 456}
        await store_idempotency(mock_request, response_body, 201)

        # Verify cache has entry
        assert len(_idempotency_cache) == 1

        # Verify stored data
        cache_key = list(_idempotency_cache.keys())[0]
        cached_response, expires_at = _idempotency_cache[cache_key]

        assert cached_response["body"] == response_body
        assert cached_response["status"] == 201
        assert expires_at > datetime.now(timezone.utc)

    @pytest.mark.asyncio
    async def test_store_idempotency_update_existing(self):
        """Test updating existing idempotency key moves to end (LRU)."""
        mock_request = Mock(spec=Request)
        mock_request.headers = {"Idempotency-Key": "update-key"}
        mock_request.method = "POST"
        mock_request.url = Mock()
        mock_request.url.path = "/api/test"
        mock_request.body = AsyncMock(return_value=b'{"data": "test"}')

        # Store first time
        await store_idempotency(mock_request, {"attempt": 1}, 200)

        # Reset body mock
        mock_request.body = AsyncMock(return_value=b'{"data": "test"}')

        # Store again (should move to end)
        await store_idempotency(mock_request, {"attempt": 2}, 200)

        # Should still have only one entry (not duplicate)
        assert len(_idempotency_cache) == 1

    @pytest.mark.asyncio
    async def test_store_idempotency_lru_eviction(self):
        """Test LRU eviction when cache exceeds max size."""
        # Fill cache to max
        for i in range(MAX_IDEMPOTENCY_KEYS + 5):
            mock_request = Mock(spec=Request)
            mock_request.headers = {"Idempotency-Key": f"key-{i}"}
            mock_request.method = "POST"
            mock_request.url = Mock()
            mock_request.url.path = "/api/test"
            mock_request.body = AsyncMock(return_value=f'{{"index": {i}}}'.encode())

            await store_idempotency(mock_request, {"index": i}, 200)

        # Cache should not exceed max size
        assert len(_idempotency_cache) == MAX_IDEMPOTENCY_KEYS


class TestCleanupExpiredKeys:
    """Test cleanup of expired idempotency keys."""

    def test_cleanup_expired_keys_no_expired(self):
        """Test cleanup when no keys are expired."""
        # Add a fresh key
        future_time = datetime.now(timezone.utc) + timedelta(hours=24)
        _idempotency_cache["fresh-key"] = ({"data": "test"}, future_time)

        _cleanup_expired_keys()

        # Key should still be there
        assert "fresh-key" in _idempotency_cache

    def test_cleanup_expired_keys_with_expired(self):
        """Test cleanup removes expired keys."""
        # Add expired key
        past_time = datetime.now(timezone.utc) - timedelta(hours=1)
        _idempotency_cache["expired-key"] = ({"data": "old"}, past_time)

        # Add fresh key
        future_time = datetime.now(timezone.utc) + timedelta(hours=24)
        _idempotency_cache["fresh-key"] = ({"data": "new"}, future_time)

        _cleanup_expired_keys()

        # Expired should be removed, fresh should remain
        assert "expired-key" not in _idempotency_cache
        assert "fresh-key" in _idempotency_cache


class TestRequireIdempotencyDecorator:
    """Test the require_idempotency decorator."""

    @pytest.mark.asyncio
    async def test_decorator_without_request(self):
        """Test decorator when no Request object found."""

        @require_idempotency()
        async def test_endpoint():
            return {"result": "no request"}

        result = await test_endpoint()
        assert result == {"result": "no request"}

    @pytest.mark.asyncio
    async def test_decorator_with_request_no_idempotency_key(self):
        """Test decorator with request but no idempotency key."""
        mock_request = Mock(spec=Request)
        mock_request.headers = {}

        @require_idempotency()
        async def test_endpoint(request: Request):
            return {"result": "processed"}

        result = await test_endpoint(mock_request)
        assert result == {"result": "processed"}

    @pytest.mark.asyncio
    async def test_decorator_stores_dict_response(self):
        """Test decorator stores dict response."""
        mock_request = Mock(spec=Request)
        mock_request.headers = {"Idempotency-Key": "decorator-key"}
        mock_request.method = "POST"
        mock_request.url = Mock()
        mock_request.url.path = "/api/test"
        mock_request.body = AsyncMock(return_value=b'{"input": "data"}')

        @require_idempotency()
        async def test_endpoint(request: Request):
            return {"result": "created", "id": 789}

        result = await test_endpoint(mock_request)
        assert result == {"result": "created", "id": 789}

        # Verify stored in cache
        assert len(_idempotency_cache) == 1

    @pytest.mark.asyncio
    async def test_decorator_returns_cached_response(self):
        """Test decorator returns cached response on duplicate."""
        mock_request = Mock(spec=Request)
        mock_request.headers = {"Idempotency-Key": "duplicate-key"}
        mock_request.method = "POST"
        mock_request.url = Mock()
        mock_request.url.path = "/api/test"
        mock_request.body = AsyncMock(return_value=b'{"input": "data"}')

        call_count = 0

        @require_idempotency()
        async def test_endpoint(request: Request):
            nonlocal call_count
            call_count += 1
            return {"result": f"call-{call_count}"}

        # First call
        result1 = await test_endpoint(mock_request)
        assert result1 == {"result": "call-1"}
        assert call_count == 1

        # Second call (should return cached, not call function again)
        mock_request.body = AsyncMock(return_value=b'{"input": "data"}')
        result2 = await test_endpoint(mock_request)

        # Function should not be called again
        assert call_count == 1
        # Should return cached response
        assert isinstance(result2, JSONResponse)

    @pytest.mark.asyncio
    async def test_decorator_with_json_response(self):
        """Test decorator handles JSONResponse return type."""
        mock_request = Mock(spec=Request)
        mock_request.headers = {"Idempotency-Key": "json-response-key"}
        mock_request.method = "POST"
        mock_request.url = Mock()
        mock_request.url.path = "/api/test"
        mock_request.body = AsyncMock(return_value=b'{"input": "data"}')

        @require_idempotency()
        async def test_endpoint(request: Request):
            return JSONResponse(content={"result": "json response"}, status_code=201)

        result = await test_endpoint(mock_request)
        assert isinstance(result, JSONResponse)
        assert result.status_code == 201
