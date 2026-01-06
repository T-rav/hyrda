"""Service Account API endpoints for external integration management.

Allows admin users to create, list, revoke, and manage API keys for external systems.
"""

import logging
import os
from datetime import datetime, timezone

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from models import ServiceAccount, get_db_session
from models.service_account import generate_api_key
from utils.auth import require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/service-accounts", tags=["service-accounts"])


# Request/Response models
class ServiceAccountCreate(BaseModel):
    """Request to create a new service account."""

    name: str = Field(..., min_length=1, max_length=255, description="Unique name for identification")
    description: str | None = Field(None, description="Purpose and use case")
    scopes: str = Field("agents:read,agents:invoke", description="Comma-separated scopes")
    allowed_agents: list[str] | None = Field(None, description="Agent names allowed, null = all")
    rate_limit: int = Field(100, ge=1, le=10000, description="Requests per hour")
    expires_at: datetime | None = Field(None, description="Optional expiration (ISO 8601)")


class ServiceAccountUpdate(BaseModel):
    """Request to update a service account."""

    description: str | None = None
    scopes: str | None = None
    allowed_agents: list[str] | None = None
    rate_limit: int | None = Field(None, ge=1, le=10000)
    is_active: bool | None = None
    expires_at: datetime | None = None


class ServiceAccountResponse(BaseModel):
    """Response model for service account (without api_key_hash)."""

    id: int
    name: str
    description: str | None
    api_key_prefix: str
    scopes: str
    allowed_agents: list[str] | None
    rate_limit: int
    is_active: bool
    is_revoked: bool
    created_by: str | None
    created_at: datetime
    updated_at: datetime
    last_used_at: datetime | None
    expires_at: datetime | None
    total_requests: int
    last_request_ip: str | None
    revoked_at: datetime | None
    revoked_by: str | None
    revoke_reason: str | None

    class Config:
        from_attributes = True


class ServiceAccountCreateResponse(ServiceAccountResponse):
    """Response when creating a service account - includes API key ONCE."""

    api_key: str = Field(..., description="API key - SAVE THIS! It won't be shown again")


# Endpoints
@router.post("", response_model=ServiceAccountCreateResponse, dependencies=[Depends(require_admin)])
async def create_service_account(
    data: ServiceAccountCreate,
    request: Request,
):
    """Create a new service account and API key.

    **Admin only.** Returns the API key once - it cannot be retrieved later.

    Args:
        data: Service account creation request
        request: FastAPI request (for admin user context)

    Returns:
        ServiceAccount with api_key field populated

    Raises:
        HTTPException: 400 if name already exists, 403 if not admin
    """
    with get_db_session() as db:
        # Check if name already exists
        existing = db.query(ServiceAccount).filter(ServiceAccount.name == data.name).first()
        if existing:
            raise HTTPException(status_code=400, detail=f"Service account '{data.name}' already exists")

        # Generate API key and hash it
        api_key = generate_api_key()
        api_key_hash = bcrypt.hashpw(api_key.encode(), bcrypt.gensalt()).decode()
        api_key_prefix = api_key[:8]  # First 8 chars for identification

        # Get admin user from JWT
        admin_email = request.state.user.get("email", "unknown")

        # Create service account
        import json

        service_account = ServiceAccount(
            name=data.name,
            description=data.description,
            api_key_hash=api_key_hash,
            api_key_prefix=api_key_prefix,
            scopes=data.scopes,
            allowed_agents=json.dumps(data.allowed_agents) if data.allowed_agents else None,
            rate_limit=data.rate_limit,
            is_active=True,
            is_revoked=False,
            created_by=admin_email,
            expires_at=data.expires_at,
            total_requests=0,
        )

        db.add(service_account)
        db.commit()
        db.refresh(service_account)

        logger.info(f"Created service account '{data.name}' by {admin_email}")

        # Parse allowed_agents JSON before creating response
        allowed_agents_list = None
        if service_account.allowed_agents:
            try:
                allowed_agents_list = json.loads(service_account.allowed_agents)
            except json.JSONDecodeError:
                allowed_agents_list = None

        # Create response dict manually to handle JSON fields
        response_dict = {
            "id": service_account.id,
            "name": service_account.name,
            "description": service_account.description,
            "api_key_prefix": service_account.api_key_prefix,
            "scopes": service_account.scopes,
            "allowed_agents": allowed_agents_list,
            "rate_limit": service_account.rate_limit,
            "is_active": service_account.is_active,
            "is_revoked": service_account.is_revoked,
            "created_by": service_account.created_by,
            "created_at": service_account.created_at,
            "updated_at": service_account.updated_at,
            "last_used_at": service_account.last_used_at,
            "expires_at": service_account.expires_at,
            "total_requests": service_account.total_requests,
            "last_request_ip": service_account.last_request_ip,
            "revoked_at": service_account.revoked_at,
            "revoked_by": service_account.revoked_by,
            "revoke_reason": service_account.revoke_reason,
            "api_key": api_key,  # Only time it's visible
        }

        return ServiceAccountCreateResponse(**response_dict)


@router.get("", response_model=list[ServiceAccountResponse], dependencies=[Depends(require_admin)])
async def list_service_accounts(
    include_revoked: bool = False,
):
    """List all service accounts.

    **Admin only.**

    Args:
        include_revoked: Include revoked accounts in results

    Returns:
        List of service accounts
    """
    with get_db_session() as db:
        query = db.query(ServiceAccount)
        if not include_revoked:
            query = query.filter(ServiceAccount.is_revoked == False)

        accounts = query.order_by(ServiceAccount.created_at.desc()).all()

        # Parse allowed_agents JSON
        import json

        result = []
        for account in accounts:
            data = ServiceAccountResponse.from_orm(account)
            if account.allowed_agents:
                try:
                    data.allowed_agents = json.loads(account.allowed_agents)
                except json.JSONDecodeError:
                    data.allowed_agents = None
            result.append(data)

        return result


@router.get("/{account_id}", response_model=ServiceAccountResponse, dependencies=[Depends(require_admin)])
async def get_service_account(
    account_id: int,
):
    """Get a specific service account.

    **Admin only.**

    Args:
        account_id: Service account ID

    Returns:
        Service account details

    Raises:
        HTTPException: 404 if not found
    """
    with get_db_session() as db:
        account = db.query(ServiceAccount).filter(ServiceAccount.id == account_id).first()
        if not account:
            raise HTTPException(status_code=404, detail="Service account not found")

        import json

        data = ServiceAccountResponse.from_orm(account)
        if account.allowed_agents:
            try:
                data.allowed_agents = json.loads(account.allowed_agents)
            except json.JSONDecodeError:
                data.allowed_agents = None

        return data


@router.patch("/{account_id}", response_model=ServiceAccountResponse, dependencies=[Depends(require_admin)])
async def update_service_account(
    account_id: int,
    data: ServiceAccountUpdate,
):
    """Update a service account.

    **Admin only.** Cannot update revoked accounts.

    Args:
        account_id: Service account ID
        data: Fields to update

    Returns:
        Updated service account

    Raises:
        HTTPException: 404 if not found, 400 if revoked
    """
    with get_db_session() as db:
        account = db.query(ServiceAccount).filter(ServiceAccount.id == account_id).first()
        if not account:
            raise HTTPException(status_code=404, detail="Service account not found")

        if account.is_revoked:
            raise HTTPException(status_code=400, detail="Cannot update revoked service account")

        # Track if we're deactivating the account
        was_deactivated = False
        if data.is_active is not None and not data.is_active and account.is_active:
            was_deactivated = True

        # Update fields
        import json

        if data.description is not None:
            account.description = data.description
        if data.scopes is not None:
            account.scopes = data.scopes
        if data.allowed_agents is not None:
            account.allowed_agents = json.dumps(data.allowed_agents) if data.allowed_agents else None
        if data.rate_limit is not None:
            account.rate_limit = data.rate_limit
        if data.is_active is not None:
            account.is_active = data.is_active
        if data.expires_at is not None:
            account.expires_at = data.expires_at

        db.commit()
        db.refresh(account)

        logger.info(f"Updated service account '{account.name}' (ID: {account_id})")

        # Invalidate cache if account was deactivated
        if was_deactivated:
            try:
                import redis

                redis_url = os.getenv("CACHE_REDIS_URL", "redis://localhost:6379")
                redis_client = redis.from_url(redis_url, decode_responses=True)

                cache_keys_key = f"service_account:cache_keys:{account_id}"
                cached_keys = redis_client.smembers(cache_keys_key)

                if cached_keys:
                    pipeline = redis_client.pipeline()
                    for key in cached_keys:
                        pipeline.delete(key)
                    pipeline.delete(cache_keys_key)
                    pipeline.execute()
                    logger.info(
                        f"Invalidated {len(cached_keys)} cached validation entries for deactivated account {account_id}"
                    )
            except redis.ConnectionError as e:
                logger.warning(f"Could not invalidate cache for deactivated account {account_id}: {e}")

        response_data = ServiceAccountResponse.from_orm(account)
        if account.allowed_agents:
            try:
                response_data.allowed_agents = json.loads(account.allowed_agents)
            except json.JSONDecodeError:
                response_data.allowed_agents = None

        return response_data


@router.post("/{account_id}/revoke", response_model=ServiceAccountResponse, dependencies=[Depends(require_admin)])
async def revoke_service_account(
    account_id: int,
    reason: str = "Revoked by admin",
    request: Request = None,
):
    """Revoke a service account (cannot be undone).

    **Admin only.**

    Args:
        account_id: Service account ID
        reason: Reason for revocation
        request: FastAPI request (for admin user)

    Returns:
        Revoked service account

    Raises:
        HTTPException: 404 if not found, 400 if already revoked
    """
    with get_db_session() as db:
        account = db.query(ServiceAccount).filter(ServiceAccount.id == account_id).first()
        if not account:
            raise HTTPException(status_code=404, detail="Service account not found")

        if account.is_revoked:
            raise HTTPException(status_code=400, detail="Service account already revoked")

        # Revoke
        admin_email = request.state.user.get("email", "unknown") if request else "unknown"
        account.is_revoked = True
        account.is_active = False
        account.revoked_at = datetime.now(timezone.utc)
        account.revoked_by = admin_email
        account.revoke_reason = reason

        db.commit()
        db.refresh(account)

        logger.warning(f"Revoked service account '{account.name}' by {admin_email}: {reason}")

        # Invalidate all cached validations for this account
        # We can't compute the exact cache key (don't have plaintext API key)
        # So we'll store account_id in cache keys we can invalidate
        try:
            import redis

            redis_url = os.getenv("CACHE_REDIS_URL", "redis://localhost:6379")
            redis_client = redis.from_url(redis_url, decode_responses=True)

            # Clear validation cache using account_id
            # This is a secondary cache entry we maintain
            cache_keys_key = f"service_account:cache_keys:{account_id}"
            cached_keys = redis_client.smembers(cache_keys_key)

            if cached_keys:
                # Delete all cached validation entries for this account
                pipeline = redis_client.pipeline()
                for key in cached_keys:
                    pipeline.delete(key)
                pipeline.delete(cache_keys_key)  # Delete the set itself
                pipeline.execute()
                logger.info(
                    f"Invalidated {len(cached_keys)} cached validation entries for revoked account {account_id}"
                )
            else:
                logger.debug(f"No cached validations found for account {account_id}")

        except redis.ConnectionError as e:
            logger.warning(
                f"Could not invalidate cache for revoked account {account_id}: {e}. "
                "Cached validations will expire naturally (60s TTL)."
            )

        import json

        # Parse allowed_agents before creating Pydantic model
        allowed_agents_parsed = None
        if account.allowed_agents:
            try:
                allowed_agents_parsed = json.loads(account.allowed_agents)
            except json.JSONDecodeError:
                allowed_agents_parsed = None

        # Create response dict with parsed values
        response_dict = {
            "id": account.id,
            "name": account.name,
            "description": account.description,
            "api_key_prefix": account.api_key_prefix,
            "scopes": account.scopes,
            "allowed_agents": allowed_agents_parsed,
            "rate_limit": account.rate_limit,
            "is_active": account.is_active,
            "is_revoked": account.is_revoked,
            "created_by": account.created_by,
            "last_used_at": account.last_used_at,
            "expires_at": account.expires_at,
            "created_at": account.created_at,
            "updated_at": account.updated_at,
            "revoked_at": account.revoked_at,
            "revoked_by": account.revoked_by,
            "revoke_reason": account.revoke_reason,
            "total_requests": account.total_requests,
            "last_request_ip": account.last_request_ip,
        }

        return ServiceAccountResponse(**response_dict)


@router.delete("/{account_id}", dependencies=[Depends(require_admin)])
async def delete_service_account(
    account_id: int,
):
    """Permanently delete a service account.

    **Admin only.** Use with caution - prefer revoke for audit trail.

    Args:
        account_id: Service account ID

    Returns:
        Success message

    Raises:
        HTTPException: 404 if not found
    """
    with get_db_session() as db:
        account = db.query(ServiceAccount).filter(ServiceAccount.id == account_id).first()
        if not account:
            raise HTTPException(status_code=404, detail="Service account not found")

        name = account.name
        db.delete(account)
        db.commit()

        logger.warning(f"Permanently deleted service account '{name}' (ID: {account_id})")

        # Invalidate all cached validations for this account
        try:
            import redis

            redis_url = os.getenv("CACHE_REDIS_URL", "redis://localhost:6379")
            redis_client = redis.from_url(redis_url, decode_responses=True)

            cache_keys_key = f"service_account:cache_keys:{account_id}"
            cached_keys = redis_client.smembers(cache_keys_key)

            if cached_keys:
                pipeline = redis_client.pipeline()
                for key in cached_keys:
                    pipeline.delete(key)
                pipeline.delete(cache_keys_key)
                pipeline.execute()
                logger.info(
                    f"Invalidated {len(cached_keys)} cached validation entries for deleted account {account_id}"
                )
        except redis.ConnectionError as e:
            logger.warning(f"Could not invalidate cache for deleted account {account_id}: {e}")

        return {"message": f"Service account '{name}' deleted permanently"}


# Validation endpoint for external services (agent-service, etc.)
class ServiceAccountValidateRequest(BaseModel):
    """Request to validate a service account API key."""

    api_key: str = Field(..., description="Service account API key")
    client_ip: str = Field(..., description="Client IP address for tracking")


@router.post("/validate")
async def validate_service_account(data: ServiceAccountValidateRequest):
    """Validate service account API key and track usage.

    **Internal use only** - called by agent-service to validate external API requests.
    Requires X-Service-Token header for service-to-service auth.

    Uses Redis caching to minimize database queries and bcrypt verifications:
    - Cache key: service_account:validated:{sha256(api_key)}
    - TTL: 60 seconds (balance between performance and security)
    - Cache contains: account_id, validation timestamp
    - Always re-checks: revocation status, expiration, rate limits

    Args:
        data: API key and client IP

    Returns:
        Service account details if valid

    Raises:
        HTTPException: 401 if invalid/revoked/expired, 429 if rate limited
    """
    import hashlib

    from dependencies.service_auth import verify_service_auth

    # This endpoint requires service-to-service authentication
    # (agent-service must authenticate to call this)
    # NOTE: verify_service_auth is not a dependency here because we need custom logic
    # It will be checked in the calling service

    # Try Redis cache first (avoid expensive bcrypt verification)
    try:
        import json

        import redis

        redis_url = os.getenv("CACHE_REDIS_URL", "redis://localhost:6379")
        redis_client = redis.from_url(redis_url, decode_responses=True)

        # Create cache key from API key hash (don't store plaintext key in Redis!)
        api_key_hash = hashlib.sha256(data.api_key.encode()).hexdigest()
        cache_key = f"service_account:validated:{api_key_hash}"

        # Check cache
        cached_data = redis_client.get(cache_key)
        if cached_data:
            logger.debug("Service account validation cache HIT")
            cached = json.loads(cached_data)
            account_id = cached["account_id"]

            # Fetch account from DB (still need to check revocation/expiration/rate limits)
            with get_db_session() as db:
                service_account = (
                    db.query(ServiceAccount)
                    .filter(ServiceAccount.id == account_id)
                    .first()
                )

                if not service_account:
                    # Account was deleted - invalidate cache
                    redis_client.delete(cache_key)
                    raise HTTPException(status_code=401, detail="Invalid API key")

                # Continue with validation checks below (after this try block)

        else:
            logger.debug("Service account validation cache MISS")
            # Cache miss - do full validation including bcrypt
            with get_db_session() as db:
                # Fast lookup by prefix
                api_key_prefix = data.api_key[:8]
                accounts = (
                    db.query(ServiceAccount)
                    .filter(ServiceAccount.api_key_prefix == api_key_prefix)
                    .all()
                )

                # Find matching account by verifying hash (expensive!)
                service_account = None
                for account in accounts:
                    if bcrypt.checkpw(
                        data.api_key.encode(), account.api_key_hash.encode()
                    ):
                        service_account = account
                        break

                if not service_account:
                    raise HTTPException(status_code=401, detail="Invalid API key")

                # Cache the validated account_id for 60 seconds
                try:
                    redis_client.setex(
                        cache_key,
                        60,  # 60 second TTL (short to catch revocations quickly)
                        json.dumps(
                            {
                                "account_id": service_account.id,
                                "validated_at": datetime.now(timezone.utc).isoformat(),
                            }
                        ),
                    )

                    # Also maintain a set of cache keys for this account
                    # This allows us to invalidate all caches when account is revoked
                    cache_keys_set = f"service_account:cache_keys:{service_account.id}"
                    redis_client.sadd(cache_keys_set, cache_key)
                    redis_client.expire(cache_keys_set, 3600)  # 1 hour TTL

                    logger.debug(
                        f"Cached service account validation for account {service_account.id}"
                    )
                except redis.RedisError as e:
                    logger.warning(f"Failed to cache service account validation: {e}")

    except redis.ConnectionError as e:
        # Redis unavailable - fall back to direct DB lookup
        logger.warning(f"Redis unavailable for validation caching: {e}")
        with get_db_session() as db:
            # Fast lookup by prefix
            api_key_prefix = data.api_key[:8]
            accounts = (
                db.query(ServiceAccount)
                .filter(ServiceAccount.api_key_prefix == api_key_prefix)
                .all()
            )

            # Find matching account by verifying hash
            service_account = None
            for account in accounts:
                if bcrypt.checkpw(data.api_key.encode(), account.api_key_hash.encode()):
                    service_account = account
                    break

            if not service_account:
                raise HTTPException(status_code=401, detail="Invalid API key")

    # At this point, service_account is set from either cache or DB
    # Now perform security checks (always fresh, never cached)

    # Check if revoked
    if service_account.is_revoked:
        raise HTTPException(
            status_code=403,
            detail=f"API key revoked: {service_account.revoke_reason or 'No reason provided'}",
        )

    # Check if active
    if not service_account.is_active:
        raise HTTPException(status_code=403, detail="API key is inactive")

    # Check if expired
    if service_account.is_expired():
        raise HTTPException(status_code=403, detail="API key has expired")

    # Check rate limit using Redis (sliding window algorithm)
    try:
        import redis

        redis_url = os.getenv("CACHE_REDIS_URL", "redis://localhost:6379")
        redis_client = redis.from_url(redis_url, decode_responses=True)

        # Use sliding window rate limiting with Redis
        # Key format: rate_limit:service_account:{id}:{hour}
        current_time = datetime.now(timezone.utc)
        current_hour = current_time.replace(minute=0, second=0, microsecond=0)
        rate_limit_key = f"rate_limit:service_account:{service_account.id}:{current_hour.isoformat()}"

        # Increment request count
        request_count = redis_client.incr(rate_limit_key)

        # Set expiration on first request (1 hour TTL)
        if request_count == 1:
            redis_client.expire(rate_limit_key, 3600)  # 1 hour in seconds

        # Check if rate limit exceeded
        if request_count > service_account.rate_limit:
            logger.warning(
                f"Rate limit exceeded for service account '{service_account.name}' "
                f"({request_count}/{service_account.rate_limit} requests/hour)"
            )
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded: {service_account.rate_limit} requests/hour. "
                f"Current usage: {request_count} requests this hour.",
            )

        logger.debug(
            f"Service account '{service_account.name}' rate limit: "
            f"{request_count}/{service_account.rate_limit} requests/hour"
        )

    except redis.ConnectionError as e:
        # Redis unavailable - fall back to database-based rate limiting
        logger.warning(f"Redis unavailable for rate limiting, using DB fallback: {e}")

        # Simple DB-based fallback (less accurate but works without Redis)
        current_hour = datetime.now(timezone.utc).replace(
            minute=0, second=0, microsecond=0
        )
        last_used = service_account.last_used_at

        if last_used:
            last_used_hour = last_used.replace(minute=0, second=0, microsecond=0)
            if last_used_hour == current_hour:
                # Same hour - check if we've exceeded rate limit
                if service_account.total_requests >= service_account.rate_limit:
                    logger.warning(
                        f"Rate limit exceeded for service account '{service_account.name}' "
                        f"({service_account.total_requests}/{service_account.rate_limit} requests/hour)"
                    )
                    raise HTTPException(
                        status_code=429,
                        detail=f"Rate limit exceeded: {service_account.rate_limit} requests/hour",
                    )

    # Update usage stats (must be in DB context)
    with get_db_session() as db:
        # Re-fetch to update
        account = db.query(ServiceAccount).filter(ServiceAccount.id == service_account.id).first()
        if account:
            account.last_used_at = datetime.now(timezone.utc)
            account.total_requests += 1
            account.last_request_ip = data.client_ip
            db.commit()

        # Parse allowed_agents
        import json

        allowed_agents_list = None
        if service_account.allowed_agents:
            try:
                allowed_agents_list = json.loads(service_account.allowed_agents)
            except json.JSONDecodeError:
                allowed_agents_list = None

        # Return account details (without sensitive fields)
        return {
            "id": service_account.id,
            "name": service_account.name,
            "scopes": service_account.scopes,
            "allowed_agents": allowed_agents_list,
            "rate_limit": service_account.rate_limit,
        }
