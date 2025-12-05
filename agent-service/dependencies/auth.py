"""Authentication dependencies for Agent Service API endpoints.

Agent service uses service-to-service authentication for internal calls from:
- Bot service (Slack bot calling agents)
- Control-plane (admin operations)

External/user requests should go through the bot, not directly to agent-service.
"""

import sys

from fastapi import Header, HTTPException

# Add shared directory to path for JWT utilities
sys.path.insert(0, "/app")
from shared.utils.jwt_auth import verify_service_token


async def require_service_auth(
    x_service_token: str | None = Header(None, description="Service authentication token")
) -> dict:
    """
    Dependency to require service-to-service authentication.

    Services must provide their token in the X-Service-Token header.

    Use with: Depends(require_service_auth)

    Returns:
        dict: Service info with service name

    Raises:
        HTTPException: 401 if not authenticated or invalid service token

    Example:
        @router.post("/agents/{agent_name}/invoke")
        async def invoke_agent(
            agent_name: str,
            service: dict = Depends(require_service_auth)
        ):
            # service = {"service": "bot"} or {"service": "control-plane"}
            pass
    """
    if not x_service_token:
        raise HTTPException(
            status_code=401,
            detail="Service authentication required. Provide X-Service-Token header.",
        )

    service_info = verify_service_token(x_service_token)

    if not service_info:
        raise HTTPException(
            status_code=401,
            detail="Invalid service token",
        )

    return service_info
