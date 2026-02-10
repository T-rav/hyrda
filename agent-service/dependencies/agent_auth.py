"""Centralized agent authorization logic.

Handles authentication and authorization for agent invocations.
Supports 3 auth methods: JWT tokens, service account API keys, internal service tokens.
"""

import logging
import os
from typing import Any

import httpx
from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)


class AuthResult:
    """Result of authentication/authorization check."""

    def __init__(
        self,
        auth_type: str,
        user_id: str | None = None,
        service_account_name: str | None = None,
    ):
        self.auth_type = auth_type  # "jwt", "service_account", or "service"
        self.user_id = user_id
        self.service_account_name = service_account_name


async def authorize_agent_request(
    agent_name: str, agent_info: dict[str, Any], http_request: Request
) -> AuthResult:
    """Centralized authorization for agent invocation requests.

    Handles 3 authentication methods:
    1. JWT tokens (end users) - validates with control plane for permissions
    2. Service account API keys (external integrations) - validates scopes and allowed_agents
    3. Internal service tokens (bot, librechat, tasks) - trusted services

    Args:
        agent_name: Requested agent name (may be alias)
        agent_info: Agent metadata from discovery (must include "agent_name" for primary name)
        http_request: FastAPI request with auth headers

    Returns:
        AuthResult with auth_type, user_id (if applicable), service_account_name (if applicable)

    Raises:
        HTTPException: 401 (no auth), 403 (denied), 503 (control plane unavailable)
    """
    primary_name = agent_info["agent_name"]
    user_id = None
    auth_type = None
    service_account_name = None

    # Try JWT first (end user request)
    auth_header = http_request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer ") and not auth_header[7:].startswith("sa_"):
        try:
            from dependencies.auth import get_current_user

            user_info = await get_current_user(http_request)
            user_id = user_info["user_id"]
            auth_type = "jwt"
            logger.info(f"User {user_id} authenticated via JWT")
        except HTTPException:
            logger.debug("JWT authentication failed, trying next method")

    # Try service account API key (external API integration)
    if not auth_type:
        from dependencies.service_account_auth import verify_service_account_api_key

        try:
            service_account = await verify_service_account_api_key(http_request)
            if service_account:
                auth_type = "service_account"
                service_account_name = service_account.name

                # System agents are for Slack users only, not external API integrations
                if agent_info.get("is_system", False):
                    logger.warning(
                        f"Service account '{service_account_name}' attempted to access "
                        f"system agent '{primary_name}' (forbidden)"
                    )
                    raise HTTPException(
                        status_code=403,
                        detail=f"System agent '{agent_name}' is only available to Slack users, not API keys",
                    )

                # Check if this agent is allowed for this service account
                if service_account.allowed_agents is not None:
                    # Specific agents allowed - check if current agent is in list
                    if primary_name not in service_account.allowed_agents:
                        logger.warning(
                            f"Service account '{service_account_name}' attempted to access "
                            f"unauthorized agent '{primary_name}'"
                        )
                        raise HTTPException(
                            status_code=403,
                            detail=f"Service account not authorized to access agent '{agent_name}'",
                        )

                # Check if service account has invoke scope
                if "agents:invoke" not in service_account.scopes:
                    logger.warning(
                        f"Service account '{service_account_name}' lacks agents:invoke scope"
                    )
                    raise HTTPException(
                        status_code=403,
                        detail="Service account does not have agents:invoke permission",
                    )

                logger.info(
                    f"Service account '{service_account_name}' authenticated for agent '{primary_name}'"
                )
                user_id = None
        except HTTPException:
            # Service account validation failed - re-raise
            raise

    # Try internal service token (bot, librechat, tasks)
    if not auth_type:
        from shared.utils.service_auth import verify_service_token

        service_token = http_request.headers.get("X-Service-Token")
        service_info = verify_service_token(service_token) if service_token else None

        if service_info:
            auth_type = "service"
            service_name = service_info.get("service", "unknown")
            logger.info(f"Authenticated as internal service: {service_name}")
            # Service can optionally forward user context (trusted)
            user_id = http_request.headers.get("X-User-Context")
        else:
            # No valid auth
            raise HTTPException(
                status_code=401,
                detail="Authentication required: provide JWT token, service account API key, or service token",
            )

    # Check user permissions if user_id extracted from JWT (user request)
    if user_id and auth_type == "jwt":
        await _check_user_permissions(user_id, agent_name, primary_name)

    return AuthResult(
        auth_type=auth_type, user_id=user_id, service_account_name=service_account_name
    )


async def _check_user_permissions(
    user_id: str, agent_name: str, primary_name: str
) -> None:
    """Check JWT user permissions with control plane.

    Args:
        user_id: User ID from JWT token
        agent_name: Requested agent name (may be alias)
        primary_name: Primary agent name

    Raises:
        HTTPException: 403 (denied), 503 (control plane unavailable)
    """
    control_plane_url = os.getenv("CONTROL_PLANE_URL", "http://control-plane:6001")
    permissions_url = f"{control_plane_url}/api/users/{user_id}/permissions"

    # Use service token for service-to-service auth (agent-service → control-plane)
    service_token = os.getenv("AGENT_SERVICE_TOKEN", "dev-agent-service-token")
    headers = {"X-Service-Token": service_token}

    try:
        async with httpx.AsyncClient(verify=False) as client:  # nosec B501
            perm_response = await client.get(
                permissions_url, headers=headers, timeout=5.0
            )

            if perm_response.status_code == 200:
                perm_data = perm_response.json()
                permissions = (
                    perm_data.get("permissions", [])
                    if isinstance(perm_data, dict)
                    else perm_data
                )

                # Check if user has permission for this specific agent
                # Accept EITHER the primary name OR any alias (permissions may be granted by alias)
                agent_names = [
                    p.get("agent_name") for p in permissions if isinstance(p, dict)
                ]

                logger.info(
                    f"User {user_id} permissions: {agent_names}, checking for: {primary_name}"
                )

                # Check if user has permission for the primary name OR the requested name (alias)
                has_permission = (
                    primary_name in agent_names or agent_name.lower() in agent_names
                )

                if not has_permission:
                    raise HTTPException(
                        status_code=403,
                        detail=f"User {user_id} does not have permission to invoke agent '{primary_name}'",
                    )
            else:
                # If we can't get permissions, deny access (fail closed)
                raise HTTPException(
                    status_code=403, detail="Could not verify user permissions"
                )
    except httpx.RequestError as e:
        # If control-plane is unavailable, deny access (fail closed)
        logger.error(f"Error checking permissions: {e}")
        raise HTTPException(status_code=503, detail="Permission service unavailable")
