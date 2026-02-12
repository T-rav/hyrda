"""Centralized JWT authentication utilities.

This module provides JWT token generation and validation for cross-service authentication.
All services (tasks, control-plane, dashboard, agent-service) can use these utilities
to implement a unified authentication system.
"""

import logging
import os
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError

logger = logging.getLogger(__name__)

# Redis connection for token revocation (optional)
_redis_client = None


def _get_redis():
    """Get Redis client for token revocation."""
    global _redis_client
    if _redis_client is None:
        try:
            import redis

            redis_url = os.getenv("CACHE_REDIS_URL", "redis://localhost:6379")
            _redis_client = redis.from_url(redis_url, decode_responses=True)
        except Exception as e:
            logger.warning(f"Redis not available for token revocation: {e}")
            _redis_client = False  # Mark as unavailable
    return _redis_client if _redis_client is not False else None


# JWT Configuration
# SECURITY: Fail fast if JWT_SECRET_KEY not set in production
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not JWT_SECRET_KEY:
    env = os.getenv("ENVIRONMENT", "development")
    if env.lower() in ("production", "prod", "staging"):
        raise ValueError(
            "CRITICAL SECURITY: JWT_SECRET_KEY must be set in production! "
            "Generate with: openssl rand -hex 32"
        )
    # Development only - use insecure default
    import secrets

    JWT_SECRET_KEY = secrets.token_urlsafe(32)
    logger.warning(
        f"⚠️  Using randomly generated JWT secret for development: {JWT_SECRET_KEY[:10]}... "
        "Set JWT_SECRET_KEY in .env for persistence"
    )

JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_MINUTES = int(os.getenv("JWT_EXPIRATION_MINUTES", "15"))  # 15 minutes for access tokens
REFRESH_TOKEN_DAYS = int(os.getenv("REFRESH_TOKEN_DAYS", "7"))  # 7 days for refresh tokens
JWT_ISSUER = "insightmesh"



class JWTAuthError(Exception):
    """JWT authentication error."""

    ...


def create_access_token(
    user_email: str,
    user_name: str | None = None,
    user_picture: str | None = None,
    additional_claims: dict[str, Any] | None = None,
) -> str:
    """Create a JWT access token for a user.

    Args:
        user_email: User's email address
        user_name: User's display name
        user_picture: User's profile picture URL
        additional_claims: Additional claims to include in the token

    Returns:
        JWT token string

    Example:
        token = create_access_token("user@8thlight.com", "John Doe")
    """
    now = datetime.now(UTC)
    expiration = now + timedelta(minutes=JWT_EXPIRATION_MINUTES)

    payload = {
        "sub": user_email,  # Subject (user identifier)
        "email": user_email,
        "name": user_name,
        "picture": user_picture,
        "iat": now,  # Issued at
        "exp": expiration,  # Expiration
        "iss": JWT_ISSUER,  # Issuer
        "token_type": "access",  # Token type
    }

    # Add any additional claims
    if additional_claims:
        payload.update(additional_claims)

    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    logger.info(f"Created access token for {user_email}, expires at {expiration}")

    return token


def create_refresh_token(
    user_email: str,
    additional_claims: dict[str, Any] | None = None,
) -> str:
    """Create a JWT refresh token for a user.

    Refresh tokens are longer-lived and used to obtain new access tokens
    without requiring the user to log in again.

    Args:
        user_email: User's email address
        additional_claims: Additional claims to include in the token

    Returns:
        JWT refresh token string

    Example:
        refresh_token = create_refresh_token("user@8thlight.com")
    """
    now = datetime.now(UTC)
    expiration = now + timedelta(days=REFRESH_TOKEN_DAYS)

    payload = {
        "sub": user_email,  # Subject (user identifier)
        "email": user_email,
        "iat": now,  # Issued at
        "exp": expiration,  # Expiration
        "iss": JWT_ISSUER,  # Issuer
        "token_type": "refresh",  # Token type
    }

    # Add any additional claims
    if additional_claims:
        payload.update(additional_claims)

    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    logger.info(f"Created refresh token for {user_email}, expires at {expiration}")

    return token


def revoke_token(token: str) -> bool:
    """Revoke a JWT token by adding it to the blacklist.

    Args:
        token: JWT token string to revoke

    Returns:
        True if revoked successfully, False if Redis unavailable
    """
    redis = _get_redis()
    if not redis:
        logger.warning("Token revocation skipped - Redis not available")
        return False

    try:
        # Decode without verification to get expiration (for TTL calculation only)
        # nosemgrep: python.jwt.security.unverified-jwt-decode.unverified-jwt-decode
        payload = jwt.decode(token, options={"verify_signature": False})
        exp = payload.get("exp")

        if exp:
            # Store in Redis with TTL matching token expiration
            ttl = max(0, exp - int(datetime.now(UTC).timestamp()))
            redis.setex(f"revoked_token:{token}", ttl, "1")
            logger.info(f"Revoked token for {payload.get('email')}")
            return True
    except Exception as e:
        logger.error(f"Failed to revoke token: {e}")

    return False


def is_token_revoked(token: str) -> bool:
    """Check if a token has been revoked.

    Args:
        token: JWT token string

    Returns:
        True if revoked, False otherwise
    """
    redis = _get_redis()
    if not redis:
        return False  # If Redis unavailable, can't check revocation

    try:
        return redis.exists(f"revoked_token:{token}") > 0
    except Exception as e:
        logger.error(f"Failed to check token revocation: {e}")
        return False


def store_refresh_token(user_email: str, refresh_token: str) -> bool:
    """Store a refresh token in Redis for later validation.

    Args:
        user_email: User's email address
        refresh_token: The refresh token to store

    Returns:
        True if stored successfully, False if Redis unavailable
    """
    redis = _get_redis()
    if not redis:
        logger.warning("Refresh token storage skipped - Redis not available")
        return False

    try:
        # Store with TTL matching token expiration (7 days)
        ttl = REFRESH_TOKEN_DAYS * 24 * 60 * 60  # Convert days to seconds
        redis.setex(f"refresh_token:{user_email}", ttl, refresh_token)
        logger.info(f"Stored refresh token for {user_email}")
        return True
    except Exception as e:
        logger.error(f"Failed to store refresh token: {e}")
        return False


def revoke_refresh_token(user_email: str) -> bool:
    """Revoke a user's refresh token by removing it from Redis.

    Args:
        user_email: User's email address

    Returns:
        True if revoked successfully, False if Redis unavailable
    """
    redis = _get_redis()
    if not redis:
        logger.warning("Refresh token revocation skipped - Redis not available")
        return False

    try:
        redis.delete(f"refresh_token:{user_email}")
        logger.info(f"Revoked refresh token for {user_email}")
        return True
    except Exception as e:
        logger.error(f"Failed to revoke refresh token: {e}")
        return False


def validate_refresh_token(user_email: str, refresh_token: str) -> bool:
    """Validate a refresh token against stored token in Redis.

    Args:
        user_email: User's email address
        refresh_token: The refresh token to validate

    Returns:
        True if valid, False otherwise
    """
    redis = _get_redis()
    if not redis:
        # If Redis unavailable, verify token signature only
        try:
            payload = jwt.decode(
                refresh_token,
                JWT_SECRET_KEY,
                algorithms=[JWT_ALGORITHM],
                issuer=JWT_ISSUER,
            )
            return (
                payload.get("email") == user_email
                and payload.get("token_type") == "refresh"
            )
        except Exception:
            return False

    try:
        stored_token = redis.get(f"refresh_token:{user_email}")
        return stored_token == refresh_token
    except Exception as e:
        logger.error(f"Failed to validate refresh token: {e}")
        return False


def verify_token(token: str, expected_type: str | None = None) -> dict[str, Any]:
    """Verify and decode a JWT token.

    Args:
        token: JWT token string
        expected_type: Expected token type ("access" or "refresh"), None for any type

    Returns:
        Decoded token payload with user information

    Raises:
        JWTAuthError: If token is invalid, expired, revoked, or wrong type

    Example:
        try:
            user_info = verify_token(token, expected_type="access")
            email = user_info["email"]
        except JWTAuthError as e:
            # Handle invalid token
            pass
    """
    try:
        # Check if token is revoked (if Redis available)
        if is_token_revoked(token):
            raise JWTAuthError("Token has been revoked")

        payload = jwt.decode(
            token,
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
            issuer=JWT_ISSUER,
        )

        # Ensure required fields are present
        if "email" not in payload:
            raise JWTAuthError("Token missing required 'email' field")

        # Verify token type if expected_type is specified
        if expected_type:
            token_type = payload.get("token_type")
            if token_type != expected_type:
                raise JWTAuthError(
                    f"Invalid token type: expected '{expected_type}', got '{token_type}'"
                )

        logger.debug(f"Verified JWT token for {payload.get('email')}")
        return payload

    except ExpiredSignatureError:
        raise JWTAuthError("Token has expired") from None
    except InvalidTokenError as e:
        raise JWTAuthError(f"Invalid token: {e}") from e


def extract_token_from_request(authorization_header: str | None) -> str | None:
    """Extract JWT token from Authorization header.

    Args:
        authorization_header: Authorization header value (e.g., "Bearer <token>")

    Returns:
        JWT token string or None if not found

    Example:
        token = extract_token_from_request(request.headers.get("Authorization"))
    """
    if not authorization_header:
        return None

    parts = authorization_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None

    return parts[1]


def get_user_from_token(token: str) -> dict[str, Any]:
    """Get user information from a JWT token.

    Args:
        token: JWT token string

    Returns:
        Dictionary with user information (email, name, picture)

    Raises:
        JWTAuthError: If token is invalid

    Example:
        user_info = get_user_from_token(token)
        print(f"Logged in as: {user_info['email']}")
    """
    payload = verify_token(token)

    return {
        "email": payload.get("email"),
        "name": payload.get("name"),
        "picture": payload.get("picture"),
    }


def refresh_access_token_with_refresh(
    refresh_token: str, rotate_refresh: bool = True
) -> tuple[str, str | None]:
    """Exchange a refresh token for a new access token.

    Args:
        refresh_token: The refresh token to exchange
        rotate_refresh: Whether to rotate the refresh token (recommended for security)

    Returns:
        Tuple of (new_access_token, new_refresh_token)
        If rotate_refresh is False, new_refresh_token will be None

    Raises:
        JWTAuthError: If refresh token is invalid or expired

    Example:
        try:
            new_access, new_refresh = refresh_access_token_with_refresh(old_refresh)
        except JWTAuthError as e:
            # Refresh token invalid - redirect to login
            pass
    """
    # Verify refresh token (must be type "refresh")
    payload = verify_token(refresh_token, expected_type="refresh")

    user_email = payload.get("email")
    if not user_email:
        raise JWTAuthError("Refresh token missing email")

    # Validate against stored refresh token in Redis
    if not validate_refresh_token(user_email, refresh_token):
        raise JWTAuthError("Refresh token not valid or has been revoked")

    # Create new access token with same claims
    new_access_token = create_access_token(
        user_email=user_email,
        user_name=payload.get("name"),
        user_picture=payload.get("picture"),
        additional_claims={
            k: v
            for k, v in payload.items()
            if k not in ("sub", "email", "name", "picture", "iat", "exp", "iss", "token_type")
        },
    )

    # Optionally rotate refresh token for security
    new_refresh_token = None
    if rotate_refresh:
        new_refresh_token = create_refresh_token(user_email)
        store_refresh_token(user_email, new_refresh_token)
        logger.info(f"Rotated refresh token for {user_email}")

    return new_access_token, new_refresh_token
