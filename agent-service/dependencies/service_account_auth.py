"""Service Account authentication for external API integrations.

Validates API keys from external systems (HubSpot, Salesforce, etc.)
by delegating to control-plane's service account validation endpoint.
"""

import logging
import os
from typing import Any

import httpx
from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)


class ServiceAccountAuth:
    """Service account authentication result."""

    def __init__(self, account_data: dict[str, Any]):
        self.id = account_data["id"]
        self.name = account_data["name"]
        self.scopes = account_data["scopes"].split(",")
        self.allowed_agents = account_data.get("allowed_agents")  # None = all agents
        self.rate_limit = account_data["rate_limit"]


async def verify_service_account_api_key(
    request: Request,
) -> ServiceAccountAuth | None:
    """Verify service account API key by calling control-plane.

    Checks for API key in:
    - X-API-Key header
    - Authorization: Bearer header

    Args:
        request: FastAPI request object

    Returns:
        ServiceAccountAuth if valid API key, None otherwise

    Raises:
        HTTPException: If API key is invalid, revoked, or rate limited
    """
    # Extract API key from headers
    api_key = request.headers.get("X-API-Key")
    if not api_key:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            # Check if it's a service account key (starts with sa_)
            if token.startswith("sa_"):
                api_key = token

    if not api_key:
        return None  # No service account key provided

    if not api_key.startswith("sa_"):
        return None  # Not a service account key format

    # Validate API key with control-plane
    control_plane_url = os.getenv("CONTROL_PLANE_URL")
    if not control_plane_url:
        logger.error("CONTROL_PLANE_URL not configured")
        raise HTTPException(
            status_code=500,
            detail="Service account authentication not configured",
        )

    # Use internal service token for agent-service → control-plane auth
    service_token = os.getenv("AGENT_SERVICE_TOKEN")
    if not service_token:
        logger.error("AGENT_SERVICE_TOKEN not configured")
        raise HTTPException(
            status_code=500,
            detail="Service authentication not configured",
        )

    # Get client IP for tracking
    client_ip = request.client.host if request.client else "unknown"

    try:
        async with httpx.AsyncClient(verify=False) as client:  # nosec B501 - Internal Docker network with self-signed certs
            response = await client.post(
                f"{control_plane_url}/api/service-accounts/validate",
                headers={
                    "X-Service-Token": service_token,
                    "Content-Type": "application/json",
                },
                json={
                    "api_key": api_key,
                    "client_ip": client_ip,
                },
                timeout=5.0,
            )

            if response.status_code == 200:
                account_data = response.json()
                logger.info(
                    f"Service account authenticated: {account_data['name']} (ID: {account_data['id']})"
                )
                return ServiceAccountAuth(account_data)

            elif response.status_code == 401:
                error_detail = response.json().get("detail", "Invalid API key")
                logger.warning(f"Service account auth failed: {error_detail}")
                raise HTTPException(status_code=401, detail=error_detail)

            elif response.status_code == 403:
                error_detail = response.json().get("detail", "Access forbidden")
                logger.warning(f"Service account forbidden: {error_detail}")
                raise HTTPException(status_code=403, detail=error_detail)

            elif response.status_code == 429:
                error_detail = response.json().get("detail", "Rate limit exceeded")
                logger.warning(f"Service account rate limited: {error_detail}")
                raise HTTPException(status_code=429, detail=error_detail)

            else:
                logger.error(
                    f"Service account validation failed: {response.status_code}"
                )
                raise HTTPException(
                    status_code=503,
                    detail="Service account validation service unavailable",
                )

    except httpx.RequestError as e:
        logger.error(f"Failed to validate service account: {e}", exc_info=True)
        raise HTTPException(
            status_code=503,
            detail="Service account validation service unavailable",
        )
