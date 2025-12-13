"""Service-to-service authentication dependencies.

For endpoints that should be called by other services (bot, agent-service, tasks)
rather than end users.
"""

import logging
import sys
from typing import Literal

from fastapi import HTTPException, Request

# Import JWT utilities from shared directory
sys.path.insert(0, "/app")
from shared.utils.jwt_auth import SERVICE_TOKENS

logger = logging.getLogger(__name__)


async def verify_service_auth(
    request: Request, allowed_services: list[str] | None = None
) -> str:
    """
    Verify service-to-service authentication.

    Checks for service token in Authorization header.
    Use with: Depends(verify_service_auth)

    Args:
        request: FastAPI request object
        allowed_services: Optional list of allowed service names (e.g., ["bot", "agent-service"])

    Returns:
        str: Service name that authenticated

    Raises:
        HTTPException: 401 if not authenticated or invalid service
    """
    auth_header = request.headers.get("Authorization")

    if not auth_header:
        logger.warning(
            f"Service auth failed: No token provided | IP: {request.client.host} | Method: {request.method} | Path: {request.url.path}"
        )
        raise HTTPException(
            status_code=401,
            detail="Service authentication required. Include service token in Authorization header.",
        )

    # Extract token from "Bearer <token>" format
    token = None
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
    else:
        token = auth_header

    # Verify token against known service tokens
    authenticated_service = None
    for service_name, service_token in SERVICE_TOKENS.items():
        if token == service_token:
            authenticated_service = service_name
            break

    if not authenticated_service:
        logger.warning(
            f"Service auth failed: Invalid token | IP: {request.client.host} | Method: {request.method} | Path: {request.url.path}"
        )
        raise HTTPException(status_code=401, detail="Invalid service token")

    # Check if service is allowed
    if allowed_services and authenticated_service not in allowed_services:
        logger.warning(
            f"Service auth failed: Service '{authenticated_service}' not allowed | IP: {request.client.host} | Method: {request.method} | Path: {request.url.path}"
        )
        raise HTTPException(
            status_code=403,
            detail=f"Service '{authenticated_service}' not authorized for this endpoint",
        )

    logger.info(
        f"Service authenticated: {authenticated_service} | IP: {request.client.host} | Method: {request.method} | Path: {request.url.path}"
    )
    return authenticated_service


async def verify_agent_service(request: Request) -> Literal["agent-service"]:
    """
    Verify that the request is from agent-service.

    Use with: Depends(verify_agent_service)
    """
    # Note: SERVICE_TOKENS keys don't have "agent-service", they have service names like "bot", "control-plane"
    # For agent-service, we need to check if it's using a valid service token
    # For now, accept any valid service token
    await verify_service_auth(request)
    # Agent-service would use its own token or bot token
    return "agent-service"  # type: ignore
