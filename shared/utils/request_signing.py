"""HMAC request signing utilities for service-to-service authentication.

Provides additional security layer to prevent:
- Replay attacks (via timestamp validation)
- Request tampering (via HMAC signature)
- Token theft (signature includes request body)
"""

import hashlib
import hmac
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

# Request signature window (5 minutes)
SIGNATURE_VALIDITY_SECONDS = 300


class RequestSigningError(Exception):
    """Raised when request signing or validation fails."""

    pass


def generate_signature(
    service_token: str,
    request_body: str,
    timestamp: str,
) -> str:
    """Generate HMAC signature for a request.

    Args:
        service_token: Service authentication token (used as HMAC key)
        request_body: Request body as JSON string
        timestamp: ISO timestamp of the request

    Returns:
        Hex-encoded HMAC SHA256 signature

    Example:
        >>> timestamp = str(int(time.time()))
        >>> body = '{"query": "test", "context": {}}'
        >>> signature = generate_signature("service-token-123", body, timestamp)
        >>> print(signature)  # 'a1b2c3d4...'
    """
    # Create message to sign: timestamp + body
    message = f"{timestamp}:{request_body}"

    # Generate HMAC SHA256 signature
    signature = hmac.new(
        service_token.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return signature


def verify_signature(
    service_token: str,
    request_body: str,
    timestamp: str,
    provided_signature: str,
    max_age_seconds: int = SIGNATURE_VALIDITY_SECONDS,
) -> tuple[bool, str | None]:
    """Verify HMAC signature of a request.

    Args:
        service_token: Service authentication token (used as HMAC key)
        request_body: Request body as JSON string
        timestamp: ISO timestamp from the request
        provided_signature: Signature provided in X-Request-Signature header
        max_age_seconds: Maximum age of request in seconds (default: 300 = 5 minutes)

    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if signature is valid, False otherwise
        - error_message: Explanation if invalid, None if valid

    Example:
        >>> is_valid, error = verify_signature(token, body, ts, sig)
        >>> if not is_valid:
        ...     raise RequestSigningError(error)
    """
    # Validate timestamp format and age
    try:
        request_time = int(timestamp)
    except (ValueError, TypeError):
        return False, "Invalid timestamp format"

    current_time = int(time.time())
    age = current_time - request_time

    # Check if request is too old (replay attack prevention)
    if age > max_age_seconds:
        logger.warning(f"Request signature expired (age: {age}s > {max_age_seconds}s)")
        return False, f"Request expired (age: {age}s)"

    # Check if timestamp is in the future (clock skew attack)
    if age < -30:  # Allow 30 second clock skew
        logger.warning(f"Request timestamp in the future (skew: {abs(age)}s)")
        return False, "Request timestamp in the future"

    # Generate expected signature
    expected_signature = generate_signature(service_token, request_body, timestamp)

    # Compare signatures using constant-time comparison to prevent timing attacks
    is_valid = hmac.compare_digest(expected_signature, provided_signature)

    if not is_valid:
        logger.warning("Request signature mismatch")
        return False, "Invalid signature"

    return True, None


def add_signature_headers(
    headers: dict[str, str],
    service_token: str,
    request_body: str,
) -> dict[str, str]:
    """Add signature headers to a request.

    Args:
        headers: Existing request headers
        service_token: Service authentication token
        request_body: Request body as JSON string

    Returns:
        Updated headers dictionary with signature headers

    Example:
        >>> headers = {"X-Service-Token": "token-123"}
        >>> body = '{"query": "test"}'
        >>> headers = add_signature_headers(headers, "token-123", body)
        >>> print(headers)
        {'X-Service-Token': 'token-123', 'X-Request-Timestamp': '1234567890', 'X-Request-Signature': 'a1b2c3...'}
    """
    # Generate timestamp
    timestamp = str(int(time.time()))

    # Generate signature
    signature = generate_signature(service_token, request_body, timestamp)

    # Add headers
    headers["X-Request-Timestamp"] = timestamp
    headers["X-Request-Signature"] = signature

    return headers


def extract_and_verify_signature(
    service_token: str,
    request_body: str,
    timestamp_header: str | None,
    signature_header: str | None,
    max_age_seconds: int = SIGNATURE_VALIDITY_SECONDS,
) -> None:
    """Extract signature headers and verify request.

    Convenience function that combines header extraction and verification.

    Args:
        service_token: Service authentication token
        request_body: Request body as JSON string
        timestamp_header: X-Request-Timestamp header value
        signature_header: X-Request-Signature header value
        max_age_seconds: Maximum age of request in seconds

    Raises:
        RequestSigningError: If signature is missing or invalid

    Example:
        >>> extract_and_verify_signature(
        ...     token,
        ...     body,
        ...     request.headers.get("X-Request-Timestamp"),
        ...     request.headers.get("X-Request-Signature")
        ... )
    """
    if not timestamp_header:
        raise RequestSigningError("Missing X-Request-Timestamp header")

    if not signature_header:
        raise RequestSigningError("Missing X-Request-Signature header")

    is_valid, error = verify_signature(
        service_token,
        request_body,
        timestamp_header,
        signature_header,
        max_age_seconds,
    )

    if not is_valid:
        raise RequestSigningError(f"Request signature validation failed: {error}")
