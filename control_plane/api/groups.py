"""Group management endpoints."""

import logging
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from models import (
    AgentGroupPermission,
    AgentMetadata,
    PermissionGroup,
    User,
    UserGroup,
    get_db_session,
)
from utils.audit import AuditAction, log_permission_action
from utils.errors import error_response
from utils.pagination import build_pagination_response, get_pagination_params, paginate_query
from utils.permissions import check_admin, require_admin
from utils.validation import validate_display_name, validate_group_name

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/groups", tags=["groups"])


@router.get("")
async def list_groups(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100)
) -> dict[str, Any]:
    """List all groups with pagination."""
    try:
        with get_db_session() as session:
            # Build query
            query = session.query(PermissionGroup).order_by(PermissionGroup.group_name)

            # Paginate query
            groups, total_count = paginate_query(query, page, per_page)

            # Batch load all user memberships for these groups in ONE query
            # This prevents N+1 query problem
            group_names = [g.group_name for g in groups]
            all_memberships = session.query(UserGroup, User).join(
                User, UserGroup.slack_user_id == User.slack_user_id
            ).filter(
                UserGroup.group_name.in_(group_names)
            ).all()

            # Build lookup dictionary: group_name -> [users]
            users_by_group = defaultdict(list)
            for membership, user in all_memberships:
                users_by_group[membership.group_name].append({
                    "slack_user_id": user.slack_user_id,
                    "full_name": user.full_name,
                    "email": user.email,
                })

            # Build group data using cached user lists
            groups_data = []
            for group in groups:
                users_list = users_by_group[group.group_name]

                groups_data.append({
                    "group_name": group.group_name,
                    "display_name": group.display_name,
                    "description": group.description,
                    "user_count": len(users_list),
                    "users": users_list,
                })

            # Build paginated response
            response = build_pagination_response(groups_data, total_count, page, per_page)
            # Keep "groups" key for backward compatibility
            return {"groups": response["items"], "pagination": response["pagination"]}

    except Exception as e:
        logger.error(f"Error listing groups: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("")
async def create_group(request: Request) -> dict[str, Any]:
    """Create a new group."""
    try:
        # Admin check for group creation
        is_admin, error = check_admin()
        if not is_admin:
            raise HTTPException(status_code=error[1], detail=error[0].json)

        data = await request.json()
        group_name = data.get("group_name")
        display_name = data.get("display_name")

        # Validate group name
        is_valid, error_msg = validate_group_name(group_name)
        if not is_valid:
            raise HTTPException(status_code=400, detail=error_msg)

        # Validate display name (optional)
        is_valid, error_msg = validate_display_name(display_name)
        if not is_valid:
            raise HTTPException(status_code=400, detail=error_msg)

        with get_db_session() as session:
            new_group = PermissionGroup(
                group_name=group_name,
                display_name=display_name,
                description=data.get("description"),
                created_by=data.get("created_by", "admin"),
            )
            session.add(new_group)
            session.commit()
            return {"status": "created", "group_name": group_name}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating group: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{group_name}")
async def update_group(group_name: str, request: Request, _: None = Depends(require_admin)) -> dict[str, Any]:
    """Update group display name and description."""
    try:
        data = await request.json()

        with get_db_session() as session:
            group = session.query(PermissionGroup).filter(
                PermissionGroup.group_name == group_name
            ).first()

            if not group:
                raise HTTPException(status_code=404, detail="Group not found")

            # Update fields
            if "display_name" in data:
                group.display_name = data["display_name"]
            if "description" in data:
                group.description = data["description"]

            session.commit()

            return {
                "status": "updated",
                "group_name": group_name,
                "display_name": group.display_name,
                "description": group.description
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating group: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{group_name}")
async def delete_group(group_name: str, _: None = Depends(require_admin)) -> dict[str, Any]:
    """Delete a permission group."""
    try:
        # Prevent deletion of system groups
        if group_name == "all_users":
            raise HTTPException(status_code=403, detail="Cannot delete system group")

        with get_db_session() as session:
            # Check if group exists
            group = session.query(PermissionGroup).filter(
                PermissionGroup.group_name == group_name
            ).first()

            if not group:
                raise HTTPException(status_code=404, detail="Group not found")

            # Delete all user memberships
            session.query(UserGroup).filter(
                UserGroup.group_name == group_name
            ).delete()

            # Delete all agent permissions
            session.query(AgentGroupPermission).filter(
                AgentGroupPermission.group_name == group_name
            ).delete()

            # Delete the group itself
            session.delete(group)
            session.commit()

            return {"status": "deleted", "group_name": group_name}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting group: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{group_name}/users")
async def get_group_users(group_name: str) -> dict[str, Any]:
    """Get all users in a group."""
    try:
        with get_db_session() as session:
            memberships = session.query(UserGroup).filter(
                UserGroup.group_name == group_name
            ).all()

            # Batch load all users in one query to prevent N+1
            user_ids = [m.slack_user_id for m in memberships]
            if not user_ids:
                return {"users": []}

            all_users = session.query(User).filter(
                User.slack_user_id.in_(user_ids)
            ).all()

            # Build lookup dictionary for O(1) access
            users_by_id = {u.slack_user_id: u for u in all_users}

            # Build response using lookup dictionary
            users_data = []
            for membership in memberships:
                user = users_by_id.get(membership.slack_user_id)
                if user:
                    users_data.append({
                        "user_id": user.slack_user_id,
                        "email": user.email,
                        "full_name": user.full_name,
                        "added_at": membership.added_at.isoformat() if membership.added_at else None,
                    })

            return {"users": users_data}

    except Exception as e:
        logger.error(f"Error getting group users: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{group_name}/users")
async def add_user_to_group(group_name: str, request: Request, _: None = Depends(require_admin)) -> dict[str, Any]:
    """Add user to group."""
    try:
        # Validate request body
        data = await request.json()
        if not data:
            raise HTTPException(status_code=400, detail="Request body is required")

        user_id = data.get("user_id")
        if not user_id:
            raise HTTPException(status_code=400, detail="user_id is required")
        if not isinstance(user_id, str):
            raise HTTPException(status_code=400, detail="user_id must be a string")
        if len(user_id) > 255:
            raise HTTPException(status_code=400, detail="user_id too long (max 255 characters)")

        added_by = data.get("added_by", "admin")
        if not isinstance(added_by, str):
            raise HTTPException(status_code=400, detail="added_by must be a string")

        with get_db_session() as session:
            # Check if user exists
            user = session.query(User).filter(
                User.slack_user_id == user_id
            ).first()
            if not user:
                raise HTTPException(status_code=404, detail="User not found")

            # Check if already in group
            existing = session.query(UserGroup).filter(
                UserGroup.slack_user_id == user_id,
                UserGroup.group_name == group_name
            ).first()
            if existing:
                raise HTTPException(status_code=400, detail="User already in group")

            # Add user to group
            new_membership = UserGroup(
                slack_user_id=user_id,
                group_name=group_name,
                added_by=added_by
            )
            session.add(new_membership)
            session.commit()
            return {"status": "added"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding user to group: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{group_name}/users")
async def remove_user_from_group(
    group_name: str,
    user_id: str = Query(..., description="User ID to remove"),
    _: None = Depends(require_admin)
) -> dict[str, Any]:
    """Remove user from group."""
    try:
        if not user_id:
            raise HTTPException(status_code=400, detail="user_id is required")

        # Prevent manual removal from system groups
        if group_name == "all_users":
            raise HTTPException(status_code=403, detail="Cannot manually remove users from system group")

        with get_db_session() as session:
            membership = session.query(UserGroup).filter(
                UserGroup.slack_user_id == user_id,
                UserGroup.group_name == group_name
            ).first()

            if not membership:
                raise HTTPException(status_code=404, detail="User not in group")

            session.delete(membership)
            session.commit()
            return {"status": "removed"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing user from group: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{group_name}/agents")
async def get_group_agents(group_name: str) -> dict[str, Any]:
    """Get all agents this group has access to."""
    try:
        with get_db_session() as session:
            permissions = session.query(AgentGroupPermission).filter(
                AgentGroupPermission.group_name == group_name
            ).all()

            agent_names = [p.agent_name for p in permissions]
            return {"agent_names": agent_names}

    except Exception as e:
        logger.error(f"Error getting group agents: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{group_name}/agents")
async def grant_agent_to_group(group_name: str, request: Request, _: None = Depends(require_admin)) -> dict[str, Any]:
    """Grant agent access to group."""
    try:
        # Validate request body
        data = await request.json()
        if not data:
            raise HTTPException(status_code=400, detail="Request body is required")

        agent_name = data.get("agent_name")
        if not agent_name:
            raise HTTPException(status_code=400, detail="agent_name is required")
        if not isinstance(agent_name, str):
            raise HTTPException(status_code=400, detail="agent_name must be a string")
        if len(agent_name) > 100:
            raise HTTPException(status_code=400, detail="agent_name too long (max 100 characters)")

        granted_by = data.get("granted_by", "admin")
        if not isinstance(granted_by, str):
            raise HTTPException(status_code=400, detail="granted_by must be a string")

        with get_db_session() as session:
            # Check if agent is system agent
            agent_metadata = session.query(AgentMetadata).filter(
                AgentMetadata.agent_name == agent_name
            ).first()

            if agent_metadata and agent_metadata.is_system and group_name != "all_users":
                raise HTTPException(
                    status_code=403,
                    detail="System agents can only be granted to 'all_users' group"
                )

            # Check if group exists
            group = session.query(PermissionGroup).filter(
                PermissionGroup.group_name == group_name
            ).first()
            if not group:
                raise HTTPException(status_code=404, detail="Group not found")

            # Check if permission already exists
            existing = session.query(AgentGroupPermission).filter(
                AgentGroupPermission.agent_name == agent_name,
                AgentGroupPermission.group_name == group_name
            ).first()
            if existing:
                raise HTTPException(status_code=400, detail="Permission already granted")

            # Grant permission
            new_permission = AgentGroupPermission(
                agent_name=agent_name,
                group_name=group_name,
                granted_by=granted_by,
                permission_type="allow"
            )
            session.add(new_permission)
            session.commit()

            # Audit log
            log_permission_action(
                AuditAction.GRANT_PERMISSION,
                "agent_group_permission",
                f"{group_name}/{agent_name}",
                {"granted_by": granted_by}
            )

            return {"status": "granted"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error granting agent to group: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{group_name}/agents")
async def revoke_agent_from_group(
    group_name: str,
    agent_name: str = Query(..., description="Agent name to revoke"),
    _: None = Depends(require_admin)
) -> dict[str, Any]:
    """Revoke agent access from group."""
    try:
        if not agent_name:
            raise HTTPException(status_code=400, detail="agent_name is required")

        with get_db_session() as session:
            # Check if agent is system agent
            agent_metadata = session.query(AgentMetadata).filter(
                AgentMetadata.agent_name == agent_name
            ).first()

            if agent_metadata and agent_metadata.is_system and group_name == "all_users":
                raise HTTPException(
                    status_code=403,
                    detail="Cannot revoke system agents from 'all_users' group"
                )

            permission = session.query(AgentGroupPermission).filter(
                AgentGroupPermission.agent_name == agent_name,
                AgentGroupPermission.group_name == group_name
            ).first()

            if not permission:
                raise HTTPException(status_code=404, detail="Permission not found")

            session.delete(permission)
            session.commit()

            # Audit log
            log_permission_action(
                AuditAction.REVOKE_PERMISSION,
                "agent_group_permission",
                f"{group_name}/{agent_name}",
                {}
            )

            return {"status": "revoked"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error revoking agent from group: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
