"""Authentication dependencies for RAG Service API endpoints.

RAG service uses service-to-service authentication for internal calls from:
- Bot service (Slack bot calling RAG)
- Control-plane (admin operations)
- Other internal services

External/user requests should go through the bot, not directly to rag-service.
"""

import logging
import sys
import time
from datetime import UTC, datetime

from fastapi import Header, HTTPException, Request

# Add shared directory to path for auth utilities
sys.path.insert(0, "/app")
from shared.utils.service_auth import verify_service_token
from shared.utils.request_signing import RequestSigningError, extract_and_verify_signature

logger = logging.getLogger(__name__)


async def require_service_auth(
    request: Request,
    x_service_token: str | None = Header(None, description="Service authentication token"),
    x_user_email: str | None = Header(None, description="User email for permissions"),
    x_librechat_token: str | None = Header(None, description="JWT token from LibreChat"),
    x_librechat_user: str | None = Header(None, description="LibreChat user ID"),
    x_request_timestamp: str | None = Header(None, description="Request timestamp for HMAC"),
    x_request_signature: str | None = Header(None, description="HMAC signature"),
    authorization: str | None = Header(None, description="Bearer token (service or JWT)"),
) -> dict:
    """
    Dependency to require authentication from services or LibreChat users.

    Supports two authentication methods:
    1. Service-to-Service (Slack bot, control-plane):
       - X-Service-Token header + HMAC signature
       - X-User-Email header for user permissions

    2. LibreChat User:
       - Authorization: Bearer <service-token> (LibreChat service token)
       - X-LibreChat-Token header (user JWT)
       - X-User-Email header for user permissions

    Returns:
        dict: Auth info with service, user_email, auth_method

    Raises:
        HTTPException: 401 if not authenticated

    Example:
        @router.post("/api/rag/generate")
        async def generate_response(
            request: RAGGenerateRequest,
            auth: dict = Depends(require_service_auth)
        ):
            # auth = {"service": "bot", "user_email": "john@example.com", "auth_method": "service"}
            # OR {"service": "librechat", "user_email": "john@example.com", "auth_method": "jwt"}
            pass
    """
    start_time = time.time()

    # Get request info for audit logging
    client_ip = request.client.host if request.client else "unknown"
    method = request.method
    path = request.url.path

    # Determine authentication method and validate service token
    auth_method = None
    service_info = {}

    # Extract service token from Authorization header (ALWAYS required)
    service_token = None
    if authorization and authorization.startswith("Bearer "):
        service_token = authorization.replace("Bearer ", "")
    elif x_service_token:
        service_token = x_service_token

    if not service_token:
        logger.warning(
            f"Auth failed: No service token provided | "
            f"IP: {client_ip} | Method: {method} | Path: {path}"
        )
        raise HTTPException(
            status_code=401,
            detail="Service authentication required. Provide Authorization: Bearer <token> or X-Service-Token header.",
        )

    # Validate service token (bot, librechat, control-plane, etc.)
    service_info = verify_service_token(service_token)
    if not service_info:
        logger.warning(
            f"Service auth failed: Invalid token | "
            f"IP: {client_ip} | Method: {method} | Path: {path}"
        )
        raise HTTPException(status_code=401, detail="Invalid service token")

    # If LibreChat service, also validate user JWT
    if service_info.get("service") == "librechat" and x_librechat_token:
        auth_method = "jwt"
        # Validate user JWT token
        try:
            from shared.utils.jwt_auth import verify_jwt_token
            jwt_payload = verify_jwt_token(x_librechat_token)
            if not jwt_payload:
                raise HTTPException(status_code=401, detail="Invalid user JWT token")
            service_info["jwt_payload"] = jwt_payload
            service_info["librechat_user"] = x_librechat_user
            logger.debug(f"LibreChat user JWT validated: {x_librechat_user}")
        except Exception as e:
            logger.warning(f"User JWT validation failed: {e}")
            raise HTTPException(status_code=401, detail=f"User JWT validation failed: {e}")
    else:
        # Service-to-service without user JWT (Slack bot, etc.)
        auth_method = "service"

    # Verify HMAC signature for POST/PUT/PATCH requests (only for service-to-service, not LibreChat)
    if method in ["POST", "PUT", "PATCH"] and auth_method == "service":
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

    # Validate X-User-Email header (REQUIRED for both auth methods)
    if not x_user_email:
        logger.warning(
            f"Auth failed: X-User-Email header missing | "
            f"Service: {service_info.get('service')} | IP: {client_ip}"
        )
        raise HTTPException(
            status_code=400,
            detail="X-User-Email header required for user permissions",
        )

    # Add user email and auth method to service info
    service_info["user_email"] = x_user_email
    service_info["auth_method"] = auth_method

    # Audit log successful authentication
    service_name = service_info.get("service", "unknown")
    elapsed = time.time() - start_time

    logger.info(
        f"Auth success: {service_name} ({auth_method}) -> {method} {path} | "
        f"User: {x_user_email} | IP: {client_ip} | "
        f"Auth time: {elapsed * 1000:.2f}ms | "
        f"Timestamp: {datetime.now(UTC).isoformat()}"
    )

    return service_info
