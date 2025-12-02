"""Rate limiting for API endpoints."""

import logging
import time
from collections import OrderedDict
from functools import wraps
from typing import Any, Callable

from flask import jsonify, request

logger = logging.getLogger(__name__)

# Maximum number of keys to store (prevents unbounded memory growth)
MAX_RATE_LIMIT_KEYS = 10000

# In-memory storage for rate limiting with LRU eviction
# Format: {key: [(timestamp1, timestamp2, ...)]}
_rate_limit_storage: OrderedDict[str, list[float]] = OrderedDict()


def get_rate_limit_key(identifier: str | None = None) -> str:
    """Generate rate limit key for the current request.

    Args:
        identifier: Optional custom identifier (e.g., user email, API key)
                   If not provided, uses IP address

    Returns:
        Rate limit key string
    """
    if identifier:
        return f"rate_limit:{identifier}"

    # Use IP address as default identifier
    ip = request.remote_addr or "unknown"
    return f"rate_limit:ip:{ip}"


def check_rate_limit(
    key: str,
    max_requests: int,
    window_seconds: int
) -> tuple[bool, dict[str, Any]]:
    """Check if request is within rate limit.

    Uses sliding window algorithm.

    Args:
        key: Rate limit key
        max_requests: Maximum requests allowed in window
        window_seconds: Time window in seconds

    Returns:
        Tuple of (is_allowed, headers) where:
        - is_allowed: True if request is allowed, False if rate limited
        - headers: Dictionary of rate limit headers to include in response

    Example:
        >>> is_allowed, headers = check_rate_limit("user:alice", 100, 3600)
        >>> if not is_allowed:
        ...     return jsonify({"error": "Rate limit exceeded"}), 429, headers
    """
    now = time.time()
    window_start = now - window_seconds

    # Use constant-time operations to prevent timing attacks
    # Always get the list (empty list if key doesn't exist)
    timestamps = _rate_limit_storage.get(key, [])

    # Always perform cleanup regardless of key existence
    cleaned_timestamps = [t for t in timestamps if t > window_start]

    # Update or create entry (same operation for both cases)
    _rate_limit_storage[key] = cleaned_timestamps

    # Move to end for LRU (if key exists, this is constant time)
    if key in _rate_limit_storage:
        _rate_limit_storage.move_to_end(key)

    # Enforce max size with LRU eviction
    if len(_rate_limit_storage) > MAX_RATE_LIMIT_KEYS:
        # Remove least recently used key
        _rate_limit_storage.popitem(last=False)
        logger.debug(f"Evicted LRU rate limit key (cache size: {MAX_RATE_LIMIT_KEYS})")

    # Count requests in current window
    request_count = len(_rate_limit_storage[key])

    # Check if limit exceeded
    is_allowed = request_count < max_requests

    if is_allowed:
        # Record this request
        _rate_limit_storage[key].append(now)
        remaining = max_requests - request_count - 1
    else:
        remaining = 0

    # Calculate reset time (when oldest request expires)
    if _rate_limit_storage[key]:
        oldest_request = min(_rate_limit_storage[key])
        reset_time = int(oldest_request + window_seconds)
    else:
        reset_time = int(now + window_seconds)

    # Build rate limit headers (standard HTTP headers)
    headers = {
        "X-RateLimit-Limit": str(max_requests),
        "X-RateLimit-Remaining": str(remaining),
        "X-RateLimit-Reset": str(reset_time),
    }

    return is_allowed, headers


def rate_limit(
    max_requests: int = 100,
    window_seconds: int = 3600,
    identifier_func: Callable[[],  str] | None = None
):
    """Decorator to add rate limiting to an endpoint.

    Args:
        max_requests: Maximum requests allowed in window (default: 100)
        window_seconds: Time window in seconds (default: 3600 = 1 hour)
        identifier_func: Optional function to generate custom identifier
                        (e.g., lambda: session.get("user_email"))
                        If not provided, uses IP address

    Usage:
        # IP-based rate limiting
        @app.route("/api/resource")
        @rate_limit(max_requests=10, window_seconds=60)
        def my_endpoint():
            return jsonify({"data": "..."}

)

        # User-based rate limiting
        @app.route("/api/resource")
        @rate_limit(
            max_requests=100,
            window_seconds=3600,
            identifier_func=lambda: session.get("user_email")
        )
        def my_endpoint():
            return jsonify({"data": "..."})

    Returns:
        429 Too Many Requests if rate limit exceeded
        Otherwise proceeds with normal request handling
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapper(*args, **kwargs):
            # Get identifier for this request
            identifier = identifier_func() if identifier_func else None
            key = get_rate_limit_key(identifier)

            # Check rate limit
            is_allowed, headers = check_rate_limit(key, max_requests, window_seconds)

            if not is_allowed:
                logger.warning(f"Rate limit exceeded for {key}")
                response = jsonify({
                    "error": "Rate limit exceeded",
                    "message": f"Maximum {max_requests} requests per {window_seconds} seconds",
                })
                return response, 429, headers

            # Process request normally and add rate limit headers
            result = f(*args, **kwargs)

            # Add rate limit headers to response
            if isinstance(result, tuple):
                # Response with status code and possibly headers
                if len(result) == 2:
                    response, status = result
                    return response, status, headers
                elif len(result) == 3:
                    response, status, existing_headers = result
                    existing_headers.update(headers)
                    return response, status, existing_headers
                return result
            else:
                # Just response, add headers
                return result, 200, headers

        return wrapper
    return decorator


def clear_rate_limits() -> int:
    """Clear all rate limit data.

    Used for testing or manual cleanup.

    Returns:
        Number of keys cleared
    """
    count = len(_rate_limit_storage)
    _rate_limit_storage.clear()
    logger.info(f"Cleared {count} rate limit entries")
    return count


def get_rate_limit_info(identifier: str | None = None) -> dict[str, Any]:
    """Get current rate limit information.

    Args:
        identifier: Optional custom identifier

    Returns:
        Dictionary with request_count and timestamps
    """
    key = get_rate_limit_key(identifier)
    timestamps = _rate_limit_storage.get(key, [])

    return {
        "key": key,
        "request_count": len(timestamps),
        "timestamps": timestamps,
    }
