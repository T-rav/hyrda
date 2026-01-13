"""Service Account Authentication middleware.

Validates API keys from external integrations and enforces:
- API key format and validity
- Rate limiting
- Scope permissions
- Agent access control
- Expiration
- Active/revoked status
"""

import logging
from datetime import datetime, timezone

import bcrypt
from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from models import ServiceAccount, get_db_session

logger = logging.getLogger(__name__)


# Rate limiting (simple in-memory counter - use Redis in production)
_rate_limit_cache: dict[int, dict] = {}


def _check_rate_limit(service_account: ServiceAccount) -> bool:
    """Check if service account is within rate limit.

    Args:
        service_account: Service account to check

    Returns:
        True if within limit, False if exceeded
    """
    import time

    now = time.time()
    account_id = service_account.id
    rate_limit = service_account.rate_limit

    # Get or create rate limit entry
    if account_id not in _rate_limit_cache:
        _rate_limit_cache[account_id] = {"count": 0, "window_start": now}

    entry = _rate_limit_cache[account_id]

    # Reset window if hour has passed
    if now - entry["window_start"] >= 3600:
        entry["count"] = 0
        entry["window_start"] = now

    # Check limit
    if entry["count"] >= rate_limit:
        return False

    # Increment counter
    entry["count"] += 1
    return True


async def verify_service_account_api_key(
    x_api_key: str | None = Header(None),
    authorization: str | None = Header(None),
    request: Request = None,
    db: Session = Depends(get_db_session),
) -> ServiceAccount:
    """Verify service account API key from header.

    Accepts API key from either:
    - X-API-Key header
    - Authorization: Bearer {api_key} header

    Validates:
    - API key format (sa_*)
    - Key exists and matches hash
    - Account is active and not revoked
    - Account is not expired
    - Rate limit not exceeded

    Args:
        x_api_key: API key from X-API-Key header
        authorization: Bearer token from Authorization header
        request: FastAPI request (for IP tracking)
        db: Database session

    Returns:
        ServiceAccount if valid

    Raises:
        HTTPException: 401 if invalid, 403 if revoked/inactive, 429 if rate limited
    """
    # Extract API key from headers
    api_key = None
    if x_api_key:
        api_key = x_api_key
    elif authorization and authorization.startswith("Bearer "):
        api_key = authorization.replace("Bearer ", "").strip()

    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="Missing API key. Provide via X-API-Key or Authorization: Bearer header",
        )

    # Validate format
    if not api_key.startswith("sa_"):
        raise HTTPException(status_code=401, detail="Invalid API key format")

    # Get prefix for fast lookup
    api_key_prefix = api_key[:8]

    # Find service account by prefix (fast lookup)
    accounts = (
        db.query(ServiceAccount).filter(ServiceAccount.api_key_prefix == api_key_prefix).all()
    )

    if not accounts:
        logger.warning(f"API key not found: {api_key_prefix}...")
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Check hash for matching account
    service_account = None
    for account in accounts:
        if bcrypt.checkpw(api_key.encode(), account.api_key_hash.encode()):
            service_account = account
            break

    if not service_account:
        logger.warning(f"API key hash mismatch: {api_key_prefix}...")
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Check revoked
    if service_account.is_revoked:
        logger.warning(
            f"Revoked service account access attempt: {service_account.name} ({service_account.id})"
        )
        raise HTTPException(
            status_code=403,
            detail=f"Service account revoked: {service_account.revoke_reason or 'No reason provided'}",
        )

    # Check active
    if not service_account.is_active:
        logger.warning(f"Inactive service account access attempt: {service_account.name}")
        raise HTTPException(status_code=403, detail="Service account is inactive")

    # Check expiration
    if service_account.is_expired():
        logger.warning(f"Expired service account access attempt: {service_account.name}")
        raise HTTPException(
            status_code=403,
            detail=f"Service account expired on {service_account.expires_at.isoformat()}",
        )

    # Check rate limit
    if not _check_rate_limit(service_account):
        logger.warning(
            f"Rate limit exceeded for service account: {service_account.name} "
            f"({service_account.rate_limit}/hour)"
        )
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded: {service_account.rate_limit} requests per hour",
        )

    # Update usage tracking
    service_account.last_used_at = datetime.now(timezone.utc)
    service_account.total_requests += 1
    if request:
        service_account.last_request_ip = request.client.host if request.client else None
    db.commit()

    logger.info(f"Service account authenticated: {service_account.name} ({service_account.id})")

    return service_account


def require_service_account_scope(required_scope: str):
    """Dependency to require a specific scope for service account.

    Usage:
        @router.post("/agents/{name}/invoke", dependencies=[Depends(require_service_account_scope("agents:invoke"))])

    Args:
        required_scope: Scope required (e.g., "agents:invoke")

    Returns:
        Dependency function

    Raises:
        HTTPException: 403 if scope not present
    """

    async def check_scope(
        service_account: ServiceAccount = Depends(verify_service_account_api_key),
    ) -> ServiceAccount:
        if not service_account.has_scope(required_scope):
            logger.warning(
                f"Scope '{required_scope}' denied for service account: {service_account.name}"
            )
            raise HTTPException(
                status_code=403,
                detail=f"Service account missing required scope: {required_scope}",
            )
        return service_account

    return check_scope


def require_agent_access(agent_name: str):
    """Dependency to require access to a specific agent.

    Usage:
        service_account = Depends(require_agent_access(agent_name))

    Args:
        agent_name: Name of agent to check access for

    Returns:
        Dependency function

    Raises:
        HTTPException: 403 if agent access denied
    """

    async def check_agent_access(
        service_account: ServiceAccount = Depends(verify_service_account_api_key),
    ) -> ServiceAccount:
        if not service_account.can_access_agent(agent_name):
            logger.warning(
                f"Agent '{agent_name}' access denied for service account: {service_account.name}"
            )
            raise HTTPException(
                status_code=403,
                detail=f"Service account not authorized to access agent: {agent_name}",
            )
        return service_account

    return check_agent_access
