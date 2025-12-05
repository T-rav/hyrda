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

# JWT Configuration
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-this-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = int(os.getenv("JWT_EXPIRATION_HOURS", "24"))
JWT_ISSUER = "insightmesh"

# Service-to-service authentication tokens
# These are pre-shared keys for internal service communication
SERVICE_TOKENS = {
    "bot": os.getenv("BOT_SERVICE_TOKEN", "bot-service-token-change-in-production"),
    "control-plane": os.getenv("CONTROL_PLANE_SERVICE_TOKEN", "control-plane-token-change-in-production"),
}


class JWTAuthError(Exception):
    """JWT authentication error."""

    pass


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
    expiration = now + timedelta(hours=JWT_EXPIRATION_HOURS)

    payload = {
        "sub": user_email,  # Subject (user identifier)
        "email": user_email,
        "name": user_name,
        "picture": user_picture,
        "iat": now,  # Issued at
        "exp": expiration,  # Expiration
        "iss": JWT_ISSUER,  # Issuer
    }

    # Add any additional claims
    if additional_claims:
        payload.update(additional_claims)

    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    logger.info(f"Created JWT token for {user_email}, expires at {expiration}")

    return token


def verify_token(token: str) -> dict[str, Any]:
    """Verify and decode a JWT token.

    Args:
        token: JWT token string

    Returns:
        Decoded token payload with user information

    Raises:
        JWTAuthError: If token is invalid or expired

    Example:
        try:
            user_info = verify_token(token)
            email = user_info["email"]
        except JWTAuthError as e:
            # Handle invalid token
            pass
    """
    try:
        payload = jwt.decode(
            token,
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
            issuer=JWT_ISSUER,
        )

        # Ensure required fields are present
        if "email" not in payload:
            raise JWTAuthError("Token missing required 'email' field")

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


def verify_service_token(token: str) -> dict[str, str] | None:
    """Verify a service-to-service authentication token.

    Args:
        token: Service token string (from X-Service-Token header)

    Returns:
        Dictionary with service info {"service": "bot"} if valid, None otherwise

    Example:
        service_info = verify_service_token(request.headers.get("X-Service-Token"))
        if service_info:
            print(f"Request from service: {service_info['service']}")
    """
    if not token:
        return None

    # Check if token matches any known service
    for service_name, service_token in SERVICE_TOKENS.items():
        if token == service_token:
            logger.debug(f"Valid service token for: {service_name}")
            return {"service": service_name}

    logger.warning(f"Invalid service token attempted")
    return None
