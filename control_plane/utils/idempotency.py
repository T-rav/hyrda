"""Idempotency key support for preventing duplicate requests."""

import hashlib
import json
import logging
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from typing import Any

from flask import Response, jsonify, request

logger = logging.getLogger(__name__)

# Maximum number of idempotency keys to store (prevents unbounded memory growth)
MAX_IDEMPOTENCY_KEYS = 1000

# In-memory cache for idempotency keys with LRU eviction
# In production, use Redis or database for distributed systems
_idempotency_cache: OrderedDict[str, tuple[dict[str, Any], datetime]] = OrderedDict()

# Default TTL for idempotency keys (24 hours)
DEFAULT_TTL_HOURS = 24


def get_idempotency_key() -> str | None:
    """Get idempotency key from request headers.

    Returns:
        Idempotency key if present, None otherwise

    Headers:
        Idempotency-Key: Unique identifier for this request
    """
    return request.headers.get("Idempotency-Key")


def generate_request_hash() -> str:
    """Generate a hash of the request for additional safety.

    Combines method, path, and body to ensure the same idempotency key
    isn't used for different requests.

    Returns:
        SHA256 hash of request details
    """
    request_data = {
        "method": request.method,
        "path": request.path,
        "body": request.get_data(as_text=True),
    }
    request_str = json.dumps(request_data, sort_keys=True)
    return hashlib.sha256(request_str.encode()).hexdigest()


def check_idempotency() -> tuple[bool, Response | None]:
    """Check if request has already been processed.

    Returns:
        Tuple of (is_duplicate, cached_response):
        - (False, None) if this is a new request
        - (True, Response) if this is a duplicate with cached response

    Example:
        >>> is_duplicate, cached_response = check_idempotency()
        >>> if is_duplicate:
        ...     return cached_response
        >>> # Process request normally
        >>> result = process_request()
        >>> store_idempotency(result, 201)
    """
    idempotency_key = get_idempotency_key()
    if not idempotency_key:
        # No idempotency key provided, process normally
        return False, None

    # Clean up expired keys
    _cleanup_expired_keys()

    # Check if key exists in cache
    cache_key = f"{idempotency_key}:{generate_request_hash()}"
    if cache_key in _idempotency_cache:
        cached_response, timestamp = _idempotency_cache[cache_key]
        logger.info(f"Idempotency key hit: {idempotency_key}")

        # Return cached response
        return True, jsonify(cached_response["body"]), cached_response["status"]

    return False, None


def store_idempotency(
    response_body: dict[str, Any],
    status_code: int,
    ttl_hours: int = DEFAULT_TTL_HOURS
) -> None:
    """Store response for future idempotency checks.

    Args:
        response_body: Response data to cache
        status_code: HTTP status code
        ttl_hours: Time to live in hours (default: 24)

    Example:
        >>> result = {"status": "created", "agent_name": "profile"}
        >>> store_idempotency(result, 201)
    """
    idempotency_key = get_idempotency_key()
    if not idempotency_key:
        return

    cache_key = f"{idempotency_key}:{generate_request_hash()}"
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
    """Decorator to add idempotency support to an endpoint.

    Usage:
        @app.route("/api/resource", methods=["POST"])
        @require_idempotency()
        def create_resource():
            # Your endpoint logic
            return jsonify({"status": "created"}), 201

    Args:
        ttl_hours: Time to live for idempotency keys (default: 24)

    Note:
        The decorated function must return a tuple of (jsonify(data), status_code)
        for proper idempotency caching.
    """
    def decorator(f):
        from functools import wraps

        @wraps(f)
        def wrapper(*args, **kwargs):
            # Check if this is a duplicate request
            is_duplicate, cached_response = check_idempotency()
            if is_duplicate:
                return cached_response

            # Process request normally
            result = f(*args, **kwargs)

            # Store response for future idempotency checks
            if isinstance(result, tuple) and len(result) >= 2:
                response, status_code = result[0], result[1]
                if hasattr(response, 'get_json'):
                    # Flask Response object
                    response_data = response.get_json()
                    if response_data:
                        store_idempotency(response_data, status_code, ttl_hours)
                elif isinstance(response, dict):
                    # Plain dict
                    store_idempotency(response, status_code, ttl_hours)

            return result

        return wrapper
    return decorator


def clear_idempotency_cache() -> int:
    """Clear all idempotency keys from cache.

    Used for testing or manual cleanup.

    Returns:
        Number of keys cleared
    """
    count = len(_idempotency_cache)
    _idempotency_cache.clear()
    logger.info(f"Cleared {count} idempotency keys from cache")
    return count
