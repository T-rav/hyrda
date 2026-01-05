"""Service-to-service authentication utilities.

This module handles authentication between internal services using static tokens.
Separate from JWT auth which handles user session authentication.
"""

import logging
import os

logger = logging.getLogger(__name__)


def _get_service_token(service_name: str, env_var: str) -> str:
    """Get service token from env or generate unique dev token.

    Args:
        service_name: Name of the service (bot, rag, etc.)
        env_var: Environment variable name for the token

    Returns:
        Service token string

    Raises:
        ValueError: If token not set in production environment
    """
    token = os.getenv(env_var)
    if token:
        return token

    # Development mode - generate unique token per service
    env = os.getenv("ENVIRONMENT", "development")
    if env.lower() in ("production", "prod", "staging"):
        raise ValueError(
            f"CRITICAL SECURITY: {env_var} must be set in production! "
            "Generate with: openssl rand -hex 32"
        )

    import secrets

    return f"dev-{service_name}-{secrets.token_urlsafe(16)}"


# Service tokens for authentication
# SECURITY: Each service has a unique token, even in development
SERVICE_TOKENS = {
    "bot": _get_service_token("bot", "BOT_SERVICE_TOKEN"),
    "control-plane": _get_service_token("control-plane", "CONTROL_PLANE_SERVICE_TOKEN"),
    "rag": _get_service_token("rag", "RAG_SERVICE_TOKEN"),
    "librechat": _get_service_token("librechat", "LIBRECHAT_SERVICE_TOKEN"),
    "agent-service": _get_service_token("agent-service", "AGENT_SERVICE_TOKEN"),
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

    logger.warning("Invalid service token attempted")
    return None
