"""Audit logging for admin actions."""

import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import Request

logger = logging.getLogger(__name__)


def log_admin_action(
    action: str,
    resource_type: str,
    resource_id: str,
    details: dict[str, Any] | None = None,
    success: bool = True,
    request: Request | None = None,
    user_email: str | None = None,
) -> None:
    """Log an admin action for audit trail.

    Args:
        action: The action performed (e.g., "delete", "grant_permission", "revoke_permission")
        resource_type: Type of resource affected (e.g., "agent", "user", "group")
        resource_id: Identifier of the resource (e.g., agent name, user email, group name)
        details: Optional additional details about the action
        success: Whether the action succeeded (default: True)
        request: Optional FastAPI Request object for getting user context
        user_email: Optional user email (if not provided, extracted from request session)

    Example:
        >>> log_admin_action("delete", "agent", "profile", {"reason": "deprecated"})
        >>> log_admin_action("grant_permission", "agent_group", "engineering/profile")
    """
    # Get user email from parameter, request session, or default to unknown
    if not user_email and request:
        user_email = request.session.get("user_email", "unknown")
    elif not user_email:
        user_email = "unknown"

    timestamp = datetime.now(UTC).isoformat()

    # Get request information
    ip_address = "unknown"
    user_agent = "unknown"
    if request:
        ip_address = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("User-Agent", "unknown")

    audit_entry = {
        "timestamp": timestamp,
        "user": user_email,
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "success": success,
        "ip_address": ip_address,
        "user_agent": user_agent,
    }

    if details:
        audit_entry["details"] = details

    # Log as structured JSON for easy parsing
    if success:
        logger.info(f"AUDIT: {audit_entry}")
    else:
        logger.warning(f"AUDIT_FAILED: {audit_entry}")


def log_agent_action(
    action: str,
    agent_name: str,
    details: dict[str, Any] | None = None,
    request: Request | None = None,
    user_email: str | None = None,
) -> None:
    """Log an agent-related action.

    Args:
        action: The action performed (e.g., "delete", "toggle", "register")
        agent_name: Name of the agent
        details: Optional additional details
        request: Optional FastAPI Request object
        user_email: Optional user email
    """
    log_admin_action(
        action, "agent", agent_name, details, request=request, user_email=user_email
    )


def log_permission_action(
    action: str,
    resource_type: str,
    resource_id: str,
    details: dict[str, Any] | None = None,
    request: Request | None = None,
    user_email: str | None = None,
) -> None:
    """Log a permission-related action.

    Args:
        action: The action performed (e.g., "grant", "revoke")
        resource_type: Type of permission (e.g., "agent_permission", "agent_group_permission")
        resource_id: Identifier (e.g., "user@example.com/profile", "engineering/profile")
        details: Optional additional details
        request: Optional FastAPI Request object
        user_email: Optional user email
    """
    log_admin_action(
        action,
        resource_type,
        resource_id,
        details,
        request=request,
        user_email=user_email,
    )


def log_user_action(
    action: str,
    user_email_param: str,
    details: dict[str, Any] | None = None,
    request: Request | None = None,
    user_email: str | None = None,
) -> None:
    """Log a user management action.

    Args:
        action: The action performed (e.g., "set_admin", "add_to_group", "remove_from_group")
        user_email_param: Email of the user being acted upon
        details: Optional additional details
        request: Optional FastAPI Request object
        user_email: Optional email of the user performing the action
    """
    log_admin_action(
        action,
        "user",
        user_email_param,
        details,
        request=request,
        user_email=user_email,
    )


def log_group_action(
    action: str,
    group_name: str,
    details: dict[str, Any] | None = None,
    request: Request | None = None,
    user_email: str | None = None,
) -> None:
    """Log a group management action.

    Args:
        action: The action performed (e.g., "create", "delete", "update")
        group_name: Name of the group
        details: Optional additional details
        request: Optional FastAPI Request object
        user_email: Optional user email
    """
    log_admin_action(
        action, "group", group_name, details, request=request, user_email=user_email
    )


# Audit action constants for consistency
class AuditAction:
    """Standard audit action names."""

    # Agent actions
    AGENT_DELETE = "delete_agent"
    AGENT_TOGGLE = "toggle_agent"
    AGENT_REGISTER = "register_agent"

    # Permission actions
    GRANT_PERMISSION = "grant_permission"
    REVOKE_PERMISSION = "revoke_permission"

    # User actions
    SET_ADMIN = "set_admin"
    ADD_TO_GROUP = "add_to_group"
    REMOVE_FROM_GROUP = "remove_from_group"

    # Group actions
    CREATE_GROUP = "create_group"
    DELETE_GROUP = "delete_group"
    UPDATE_GROUP = "update_group"
