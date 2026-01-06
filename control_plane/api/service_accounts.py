"""Service Account API endpoints for external integration management.

Allows admin users to create, list, revoke, and manage API keys for external systems.
"""

import logging
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
    db: Session = Depends(get_db_session),
):
    """Create a new service account and API key.

    **Admin only.** Returns the API key once - it cannot be retrieved later.

    Args:
        data: Service account creation request
        request: FastAPI request (for admin user context)
        db: Database session

    Returns:
        ServiceAccount with api_key field populated

    Raises:
        HTTPException: 400 if name already exists, 403 if not admin
    """
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

    # Return response with API key (only time it's visible)
    response_data = ServiceAccountResponse.from_orm(service_account)
    return ServiceAccountCreateResponse(**response_data.dict(), api_key=api_key)


@router.get("", response_model=list[ServiceAccountResponse], dependencies=[Depends(require_admin)])
async def list_service_accounts(
    include_revoked: bool = False,
    db: Session = Depends(get_db_session),
):
    """List all service accounts.

    **Admin only.**

    Args:
        include_revoked: Include revoked accounts in results
        db: Database session

    Returns:
        List of service accounts
    """
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
    db: Session = Depends(get_db_session),
):
    """Get a specific service account.

    **Admin only.**

    Args:
        account_id: Service account ID
        db: Database session

    Returns:
        Service account details

    Raises:
        HTTPException: 404 if not found
    """
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
    db: Session = Depends(get_db_session),
):
    """Update a service account.

    **Admin only.** Cannot update revoked accounts.

    Args:
        account_id: Service account ID
        data: Fields to update
        db: Database session

    Returns:
        Updated service account

    Raises:
        HTTPException: 404 if not found, 400 if revoked
    """
    account = db.query(ServiceAccount).filter(ServiceAccount.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Service account not found")

    if account.is_revoked:
        raise HTTPException(status_code=400, detail="Cannot update revoked service account")

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
    db: Session = Depends(get_db_session),
):
    """Revoke a service account (cannot be undone).

    **Admin only.**

    Args:
        account_id: Service account ID
        reason: Reason for revocation
        request: FastAPI request (for admin user)
        db: Database session

    Returns:
        Revoked service account

    Raises:
        HTTPException: 404 if not found, 400 if already revoked
    """
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

    import json

    response_data = ServiceAccountResponse.from_orm(account)
    if account.allowed_agents:
        try:
            response_data.allowed_agents = json.loads(account.allowed_agents)
        except json.JSONDecodeError:
            response_data.allowed_agents = None

    return response_data


@router.delete("/{account_id}", dependencies=[Depends(require_admin)])
async def delete_service_account(
    account_id: int,
    db: Session = Depends(get_db_session),
):
    """Permanently delete a service account.

    **Admin only.** Use with caution - prefer revoke for audit trail.

    Args:
        account_id: Service account ID
        db: Database session

    Returns:
        Success message

    Raises:
        HTTPException: 404 if not found
    """
    account = db.query(ServiceAccount).filter(ServiceAccount.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Service account not found")

    name = account.name
    db.delete(account)
    db.commit()

    logger.warning(f"Permanently deleted service account '{name}' (ID: {account_id})")

    return {"message": f"Service account '{name}' deleted permanently"}
