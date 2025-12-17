"""User management endpoints - FastAPI version."""

import logging
import os
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from dependencies.auth import get_current_user, get_current_user_or_service
from models import AgentPermission, PermissionGroup, User, UserGroup, get_db_session
from pydantic import BaseModel, Field
from utils.pagination import (
    build_pagination_response,
    get_pagination_params,
    paginate_query,
)
from utils.permissions import require_admin
from utils.rate_limit import rate_limit

logger = logging.getLogger(__name__)

# Create router with authentication required for all endpoints
router = APIRouter(
    prefix="/api/users",
    tags=["users"],
    # Note: Auth is handled per-endpoint (some allow service auth)
)


# Pydantic models for request/response
class UserAdminUpdate(BaseModel):
    """UserAdminUpdate class."""

    is_admin: bool


class GrantPermissionRequest(BaseModel):
    agent_name: str = Field(..., max_length=100)
    granted_by: str = "admin"


class SyncUsersRequest(BaseModel):
    provider: str | None = None


@router.get("/me")
@rate_limit(max_requests=100, window_seconds=60)  # 100 requests per minute per IP
async def get_current_user_endpoint(request: Request) -> dict[str, Any]:
    """Get current authenticated user info.

    Supports both JWT (Authorization header) and session (cookies) auth.
    Rate limited to 100 requests per minute per IP address.
    """
    try:
        from dependencies.auth import get_current_user as get_current_user_auth

        # Use JWT-aware auth (supports both JWT and session)
        user_info = await get_current_user_auth(request)

        return {
            "email": user_info.get("email", ""),
            "name": user_info.get("name", ""),
            "picture": user_info.get("picture", ""),
            "is_admin": user_info.get("is_admin", False),
            "user_id": user_info.get("user_id", ""),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting current user: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/verify-admin")
async def verify_admin_status(email: str) -> dict[str, Any]:
    """Verify admin status from database.

    SECURITY: This endpoint re-verifies admin status from the database,
    not from JWT token. Used for defense-in-depth on critical operations.

    Args:
        email: User email to verify

    Returns:
        dict with is_admin boolean from database
    """
    try:
        with get_db_session() as session:
            user = session.query(User).filter(User.email == email).first()

            if not user:
                logger.warning(f"Admin verification failed: user {email} not found in database")
                return {"is_admin": False, "user_found": False}

            logger.info(f"Admin verification for {email}: is_admin={user.is_admin}")
            return {"is_admin": user.is_admin, "user_found": True}

    except Exception as e:
        logger.error(f"Error verifying admin status for {email}: {e}", exc_info=True)
        # Fail closed - deny access on error
        return {"is_admin": False, "error": str(e)}


@router.get("", dependencies=[Depends(get_current_user)])
async def list_users(request: Request) -> dict[str, Any]:
    """List all users from security database with their group memberships.

    Query Parameters:
        page: Page number (1-indexed, default: 1)
        per_page: Items per page (default: 50, max: 100)

    Returns:
        JSON response with paginated users and pagination metadata
    """
    try:
        # Get pagination parameters
        page, per_page = get_pagination_params(
            request, default_per_page=50, max_per_page=100
        )

        with get_db_session() as session:
            # Build query
            query = session.query(User).order_by(User.email)

            # Paginate query
            users, total_count = paginate_query(query, page, per_page)

            # Batch load all group memberships for these users in ONE query
            # This prevents N+1 query problem
            user_ids = [user.slack_user_id for user in users]
            all_memberships = (
                session.query(UserGroup, PermissionGroup)
                .join(
                    PermissionGroup, UserGroup.group_name == PermissionGroup.group_name
                )
                .filter(UserGroup.slack_user_id.in_(user_ids))
                .all()
            )

            # Build lookup dictionary: user_id -> [groups]
            memberships_by_user = defaultdict(list)
            for membership, group in all_memberships:
                memberships_by_user[membership.slack_user_id].append(
                    {
                        "group_name": group.group_name,
                        "display_name": group.display_name,
                    }
                )

            # Build user data using cached memberships
            users_data = []
            for user in users:
                groups = memberships_by_user[user.slack_user_id]

                users_data.append(
                    {
                        "id": user.id,
                        "slack_user_id": user.slack_user_id,
                        "email": user.email,
                        "full_name": user.full_name,
                        "is_active": user.is_active,
                        "is_admin": user.is_admin,
                        "last_synced_at": user.last_synced_at.isoformat()
                        if user.last_synced_at
                        else None,
                        "groups": groups,
                    }
                )

            # Build paginated response
            response = build_pagination_response(
                users_data, total_count, page, per_page
            )
            # Keep "users" key for backward compatibility
            return {"users": response["items"], "pagination": response["pagination"]}

    except Exception as e:
        logger.error(f"Error listing users: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync")
async def sync_users(
    request: Request, body: SyncUsersRequest | None = None
) -> dict[str, Any]:
    """Sync users from configured identity provider to security database.

    Provider is configured via USER_MANAGEMENT_PROVIDER environment variable
    (defaults to 'slack'). Supports: slack, google.
    """
    # Check admin permission
    await require_admin(request)

    try:
        from services.user_sync import sync_users_from_provider

        # Get provider type from request body or use configured default
        provider_type = body.provider if body else None

        stats = sync_users_from_provider(provider_type=provider_type)

        provider_name = provider_type or os.getenv("USER_MANAGEMENT_PROVIDER", "slack")
        return {
            "status": "success",
            "message": f"User sync from {provider_name} completed",
            "stats": stats,
        }

    except ValueError as e:
        # Configuration error
        logger.error(f"Configuration error during user sync: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logger.error(f"Error syncing users: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")


@router.put("/{user_id}/admin")
async def update_user_admin_status(
    request: Request, user_id: str, body: UserAdminUpdate
) -> dict[str, Any]:
    """Update user admin status.

    Special case: If no admins exist, anyone can promote the first admin.
    Otherwise, only admins can change admin status.
    """
    try:
        from dependencies.auth import get_current_user as get_current_user_auth

        new_admin_status = body.is_admin

        with get_db_session() as db_session:
            # Use explicit transaction with row-level locking to prevent race conditions
            # This ensures only ONE request can bootstrap the first admin
            with db_session.begin():
                # Lock ALL admin records to prevent concurrent bootstrap
                # This prevents TOCTOU (Time-of-Check to Time-of-Use) vulnerability
                existing_admins = (
                    db_session.query(User).filter(User.is_admin).with_for_update().all()
                )

                admin_count = len(existing_admins)

                # If no admins exist, allow bootstrap (first admin creation)
                if admin_count == 0:
                    logger.info("No admins exist - allowing bootstrap admin creation")
                else:
                    # Otherwise, require current user to be admin (JWT-aware)
                    current_user_info = await get_current_user_auth(request)
                    current_user_email = current_user_info.get("email")

                    if not current_user_email:
                        raise HTTPException(status_code=401, detail="Not authenticated")

                    current_user = (
                        db_session.query(User)
                        .filter(User.email == current_user_email)
                        .first()
                    )
                    if not current_user or not current_user.is_admin:
                        raise HTTPException(
                            status_code=403,
                            detail="Only admins can manage admin status",
                        )

                # Update the target user by Slack user ID (also with lock)
                user = (
                    db_session.query(User)
                    .filter(User.slack_user_id == user_id)
                    .with_for_update()
                    .first()
                )
                if not user:
                    raise HTTPException(status_code=404, detail="User not found")

                user.is_admin = new_admin_status
                db_session.commit()

            logger.info(f"User {user.email} admin status changed to {new_admin_status}")

            return {
                "status": "success",
                "message": "User admin status updated",
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "is_admin": user.is_admin,
                },
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user admin status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/{user_id}/permissions", dependencies=[Depends(get_current_user_or_service)]
)
async def get_user_permissions(user_id: str) -> dict:
    """Get user's agent permissions (direct + inherited from groups)."""
    try:
        with get_db_session() as session:
            # Get user's direct permissions
            direct_permissions = (
                session.query(AgentPermission)
                .filter(AgentPermission.slack_user_id == user_id)
                .all()
            )

            # Get user's group memberships
            user_groups = (
                session.query(UserGroup.group_name)
                .filter(UserGroup.slack_user_id == user_id)
                .all()
            )
            group_names = [g.group_name for g in user_groups]

            # Get permissions from all groups the user belongs to
            from models import AgentGroupPermission

            group_permissions = []
            if group_names:
                group_permissions = (
                    session.query(AgentGroupPermission)
                    .filter(AgentGroupPermission.group_name.in_(group_names))
                    .all()
                )

            # Combine direct and inherited permissions (deduplicate by agent_name)
            all_agent_names = set()
            permissions_list = []

            # Add direct permissions
            for p in direct_permissions:
                if p.agent_name not in all_agent_names:
                    all_agent_names.add(p.agent_name)
                    permissions_list.append(
                        {
                            "agent_name": p.agent_name,
                            "granted_by": p.granted_by,
                            "granted_at": str(p.granted_at),
                            "source": "direct",
                        }
                    )

            # Add inherited group permissions
            for p in group_permissions:
                if p.agent_name not in all_agent_names:
                    all_agent_names.add(p.agent_name)
                    permissions_list.append(
                        {
                            "agent_name": p.agent_name,
                            "granted_by": p.granted_by or "group",
                            "granted_at": str(p.granted_at) if p.granted_at else "",
                            "source": f"group:{p.group_name}",
                        }
                    )

            return {"permissions": permissions_list}

    except Exception as e:
        logger.error(f"Error getting user permissions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{user_id}/permissions", dependencies=[Depends(get_current_user)])
async def grant_user_permission(
    request: Request, user_id: str, body: GrantPermissionRequest
) -> dict[str, str]:
    """Grant direct agent permission to user."""
    # Check admin permission
    await require_admin(request)

    try:
        agent_name = body.agent_name
        granted_by = body.granted_by

        with get_db_session() as session:
            # Check if user exists
            user = session.query(User).filter(User.slack_user_id == user_id).first()
            if not user:
                raise HTTPException(status_code=404, detail="User not found")

            # Check if permission already exists
            existing = (
                session.query(AgentPermission)
                .filter(
                    AgentPermission.slack_user_id == user_id,
                    AgentPermission.agent_name == agent_name,
                )
                .first()
            )
            if existing:
                raise HTTPException(
                    status_code=400, detail="Permission already granted"
                )

            # Grant permission
            new_permission = AgentPermission(
                agent_name=agent_name,
                slack_user_id=user_id,
                granted_by=granted_by,
                permission_type="allow",
            )
            session.add(new_permission)
            session.commit()
            return {"status": "granted"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error granting user permission: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{user_id}/permissions")
async def revoke_user_permission(
    request: Request, user_id: str, agent_name: str | None = None
) -> dict[str, str]:
    """Revoke direct agent permission from user."""
    # Check admin permission
    await require_admin(request)

    try:
        if not agent_name:
            raise HTTPException(status_code=400, detail="agent_name is required")

        with get_db_session() as session:
            permission = (
                session.query(AgentPermission)
                .filter(
                    AgentPermission.slack_user_id == user_id,
                    AgentPermission.agent_name == agent_name,
                )
                .first()
            )

            if not permission:
                raise HTTPException(status_code=404, detail="Permission not found")

            session.delete(permission)
            session.commit()
            return {"status": "revoked"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error revoking user permission: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
