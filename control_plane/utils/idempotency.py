"""Idempotency key support for preventing duplicate requests - FastAPI version."""

import hashlib
import json
import logging
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Any, Callable

from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

# Maximum number of idempotency keys to store (prevents unbounded memory growth)
MAX_IDEMPOTENCY_KEYS = 1000

# In-memory cache for idempotency keys with LRU eviction
# In production, use Redis or database for distributed systems
_idempotency_cache: OrderedDict[str, tuple[dict[str, Any], datetime]] = OrderedDict()

# Default TTL for idempotency keys (24 hours)
DEFAULT_TTL_HOURS = 24


async def get_idempotency_key(request: Request) -> str | None:
    """Get idempotency key from request headers.

    Args:
        request: FastAPI Request object

    Returns:
        Idempotency key if present, None otherwise

    Headers:
        Idempotency-Key: Unique identifier for this request
    """
    return request.headers.get("Idempotency-Key")


async def generate_request_hash(request: Request) -> str:
    """Generate a hash of the request for additional safety.

    Combines method, path, and body to ensure the same idempotency key
    isn't used for different requests.

    Args:
        request: FastAPI Request object

    Returns:
        SHA256 hash of request details
    """
    body = await request.body()
    request_data = {
        "method": request.method,
        "path": request.url.path,
        "body": body.decode("utf-8") if body else "",
    }
    request_str = json.dumps(request_data, sort_keys=True)
    return hashlib.sha256(request_str.encode()).hexdigest()


async def check_idempotency(request: Request) -> tuple[bool, JSONResponse | None]:
    """Check if request has already been processed.

    Args:
        request: FastAPI Request object

    Returns:
        Tuple of (is_duplicate, cached_response):
        - (False, None) if this is a new request
        - (True, JSONResponse) if this is a duplicate with cached response

    Example:
        >>> is_duplicate, cached_response = await check_idempotency(request)
        >>> if is_duplicate:
        ...     return cached_response
        >>> # Process request normally
        >>> result = process_request()
        >>> await store_idempotency(request, result, 201)
    """
    idempotency_key = await get_idempotency_key(request)
    if not idempotency_key:
        # No idempotency key provided, process normally
        return False, None

    # Clean up expired keys
    _cleanup_expired_keys()

    # Check if key exists in cache
    request_hash = await generate_request_hash(request)
    cache_key = f"{idempotency_key}:{request_hash}"

    if cache_key in _idempotency_cache:
        cached_response, timestamp = _idempotency_cache[cache_key]
        logger.info(f"Idempotency key hit: {idempotency_key}")

        # Return cached response as JSONResponse
        return True, JSONResponse(
            content=cached_response["body"],
            status_code=cached_response["status"]
        )

    return False, None


async def store_idempotency(
    request: Request,
    response_body: dict[str, Any],
    status_code: int,
    ttl_hours: int = DEFAULT_TTL_HOURS
) -> None:
    """Store response for future idempotency checks.

    Args:
        request: FastAPI Request object
        response_body: Response data to cache
        status_code: HTTP status code
        ttl_hours: Time to live in hours (default: 24)

    Example:
        >>> result = {"status": "created", "agent_name": "profile"}
        >>> await store_idempotency(request, result, 201)
    """
    idempotency_key = await get_idempotency_key(request)
    if not idempotency_key:
        return

    request_hash = await generate_request_hash(request)
    cache_key = f"{idempotency_key}:{request_hash}"
    expires_at = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)

    cached_response = {
        "body": response_body,
        "status": status_code,
    }

    # If key exists, move to end (mark as recently used)
    if cache_key in _idempotency_cache:
        _idempotency_cache.move_to_end(cache_key)

    _idempotency_cache[cache_key] = (cached_response, expires_at)

    # Enforce max size with LRU eviction
    if len(_idempotency_cache) > MAX_IDEMPOTENCY_KEYS:
        # Remove least recently used key
        _idempotency_cache.popitem(last=False)
        logger.debug(f"Evicted LRU idempotency key (cache size: {MAX_IDEMPOTENCY_KEYS})")

    logger.info(f"Stored idempotency key: {idempotency_key}, expires: {expires_at}")


def _cleanup_expired_keys() -> None:
    """Remove expired idempotency keys from cache."""
    now = datetime.now(timezone.utc)
    expired_keys = [
        key for key, (_, expires_at) in _idempotency_cache.items()
        if expires_at < now
    ]

    for key in expired_keys:
        del _idempotency_cache[key]

    if expired_keys:
        logger.debug(f"Cleaned up {len(expired_keys)} expired idempotency keys")


def require_idempotency(ttl_hours: int = DEFAULT_TTL_HOURS):
    """Decorator to add idempotency support to a FastAPI endpoint.

    Usage:
        @router.post("/api/resource")
        @require_idempotency(ttl_hours=24)
        async def create_resource(request: Request):
            # Your endpoint logic
            return {"status": "created"}

    Args:
        ttl_hours: Time to live for idempotency keys (default: 24)

    Note:
        The decorated function must be async and accept a Request parameter.
        The function should return a dict that will be cached.
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        async def wrapper(*args, **kwargs):
            # Extract request from args/kwargs
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            if not request:
                request = kwargs.get('request')

            if not request:
                # No request found, proceed without idempotency
                logger.warning(f"No Request object found in {f.__name__}, skipping idempotency")
                return await f(*args, **kwargs)

            # Check if this is a duplicate request
            is_duplicate, cached_response = await check_idempotency(request)
            if is_duplicate:
                return cached_response

            # Process request normally
            result = await f(*args, **kwargs)

            # Store response for future idempotency checks
            if isinstance(result, dict):
                await store_idempotency(request, result, 200, ttl_hours)
            elif isinstance(result, JSONResponse):
                # Extract body from JSONResponse
                if hasattr(result, 'body'):
                    try:
                        body_dict = json.loads(result.body)
                        await store_idempotency(request, body_dict, result.status_code, ttl_hours)
                    except (json.JSONDecodeError, AttributeError):
                        pass

            return result

        return wrapper
    return decorator
