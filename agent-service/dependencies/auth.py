"""Authentication dependencies for Agent Service API endpoints.

Agent service uses service-to-service authentication for internal calls from:
- Bot service (Slack bot calling agents)
- Control-plane (admin operations)

External/user requests should go through the bot, not directly to agent-service.
"""

import logging
import sys
import time
from datetime import UTC, datetime

from fastapi import Header, HTTPException, Request

# Add shared directory to path for JWT utilities
sys.path.insert(0, "/app")
from shared.utils.jwt_auth import verify_service_token
from shared.utils.request_signing import RequestSigningError, extract_and_verify_signature

logger = logging.getLogger(__name__)


async def require_service_auth(
    request: Request,
    x_service_token: str | None = Header(None, description="Service authentication token"),
    x_request_timestamp: str | None = Header(None, description="Request timestamp for HMAC"),
    x_request_signature: str | None = Header(None, description="HMAC signature"),
) -> dict:
    """
    Dependency to require service-to-service authentication.

    Services must provide their token in the X-Service-Token header.
    Additionally validates HMAC signature to prevent tampering and replay attacks.
    Logs all service-to-service calls for audit purposes.

    Use with: Depends(require_service_auth)

    Returns:
        dict: Service info with service name

    Raises:
        HTTPException: 401 if not authenticated or invalid service token/signature

    Example:
        @router.post("/agents/{agent_name}/invoke")
        async def invoke_agent(
            agent_name: str,
            service: dict = Depends(require_service_auth)
        ):
            # service = {"service": "bot"} or {"service": "control-plane"}
            pass
    """
    start_time = time.time()

    # Get request info for audit logging
    client_ip = request.client.host if request.client else "unknown"
    method = request.method
    path = request.url.path

    if not x_service_token:
        logger.warning(
            f"Service auth failed: No token provided | "
            f"IP: {client_ip} | Method: {method} | Path: {path}"
        )
        raise HTTPException(
            status_code=401,
            detail="Service authentication required. Provide X-Service-Token header.",
        )

    service_info = verify_service_token(x_service_token)

    if not service_info:
        logger.warning(
            f"Service auth failed: Invalid token | "
            f"IP: {client_ip} | Method: {method} | Path: {path}"
        )
        raise HTTPException(
            status_code=401,
            detail="Invalid service token",
        )

    # Verify HMAC signature for POST/PUT/PATCH requests
    if method in ["POST", "PUT", "PATCH"]:
        try:
            # Read request body
            body_bytes = await request.body()
            body_str = body_bytes.decode("utf-8")

            # Verify signature
            extract_and_verify_signature(
                x_service_token,
                body_str,
                x_request_timestamp,
                x_request_signature,
            )

            logger.debug(f"Request signature verified for {service_info.get('service')}")

        except RequestSigningError as e:
            logger.warning(
                f"Service auth failed: Invalid signature | "
                f"IP: {client_ip} | Method: {method} | Path: {path} | "
                f"Error: {e}"
            )
            raise HTTPException(
                status_code=401,
                detail=f"Request signature validation failed: {e}",
            )

    # Audit log successful authentication
    service_name = service_info.get("service", "unknown")
    elapsed = time.time() - start_time

    logger.info(
        f"Service call: {service_name} -> {method} {path} | "
        f"IP: {client_ip} | Auth time: {elapsed*1000:.2f}ms | "
        f"Timestamp: {datetime.now(UTC).isoformat()}"
    )

    return service_info
